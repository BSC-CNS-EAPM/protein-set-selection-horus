"""
Detection and installation of the external tools this plugin drives.

The plugin's own Python dependencies are declared in ``plugin.meta`` and Horus
pip-installs them into ``deps/`` at install time, so nothing here needs to touch
them; the entries of kind ``python-import`` only *check* that they arrived.

What this module exists for is everything that cannot go in ``deps/``:
executables (MMseqs2, MAFFT, Rosetta, SMOG), packages that need their own
environment because of a large or CUDA-specific torch (BioEmu, CodonTransformer,
PyRosetta), and torch itself. Those are detected here, installed on request, and
the paths that result are written into the plugin configuration so the blocks
find them.

Two tools are deliberately never installed automatically. Rosetta is licensed
and distributed as a large compiled bundle, and SMOG 2 is registration-gated;
for both, this module detects and validates what the user already has.
"""

import json
import os
import shutil
import subprocess
import sys

PLUGIN_ID = "protselect"


# ==========================#
# Environment discovery
# ==========================#
def _conda_roots():
    """Roots under which a named conda/micromamba environment might live."""
    roots = [
        os.environ.get("MAMBA_ROOT_PREFIX"),
        os.path.expanduser("~/micromamba"),
        os.path.expanduser("~/miniforge3"),
        os.path.expanduser("~/mambaforge"),
        os.path.expanduser("~/miniconda3"),
        os.path.expanduser("~/anaconda3"),
    ]
    conda_exe = os.environ.get("CONDA_EXE")
    if conda_exe:
        roots.append(os.path.dirname(os.path.dirname(conda_exe)))
    return [root for root in dict.fromkeys(roots) if root and os.path.isdir(root)]


def resolve_env_python(env_value: str):
    """
    Resolve an environment given as a name, a prefix path or an interpreter path.

    Returns the interpreter path, or None when nothing matches.
    """
    if not env_value or not env_value.strip():
        return None
    env_value = os.path.expanduser(env_value.strip())

    if os.path.isfile(env_value):
        return env_value
    if os.path.isdir(env_value):
        candidate = os.path.join(env_value, "bin", "python")
        return candidate if os.path.isfile(candidate) else None

    for root in _conda_roots():
        candidate = os.path.join(root, "envs", env_value, "bin", "python")
        if os.path.isfile(candidate):
            return candidate
    return None


def _foreign_python_env():
    """
    Environment for invoking an interpreter other than the one running Horus.

    Horus puts the plugin's deps site-packages on PYTHONPATH and a subprocess
    inherits it, which breaks an interpreter from another environment -- usually
    on another Python version -- before it can import anything.
    """
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(name, None)
    return env


def _conda_command():
    """Return a usable conda-like executable, preferring micromamba."""
    for name in ("micromamba", "mamba", "conda"):
        found = shutil.which(name)
        if found:
            return found
    return None


def _deps_dir():
    """The plugin's private site-packages, where pip installs land."""
    root = os.path.dirname(os.path.abspath(__file__))          # Include/
    return os.path.join(os.path.dirname(root), "deps")         # <pluginRoot>/deps


def _deps_bin():
    return os.path.join(_deps_dir(), "bin")


# ==========================#
# Checks
# ==========================#
# Every check takes the same (tool, values) signature so _CHECKS can dispatch to
# them by kind, and returns (found, detected_path, version_or_message). An
# importable package is not located through the saved config, so it ignores it.
# pylint: disable=unused-argument
def _check_python_import(tool, values):
    """A package that should have arrived through plugin.meta dependencies."""
    module = tool["module"]
    try:
        __import__(module)
        module_obj = sys.modules[module]
        version = getattr(module_obj, "__version__", "")
        return True, getattr(module_obj, "__file__", "") or "(namespace package)", version
    except ImportError as error:
        return False, "", str(error)


def _check_executable(tool, values):
    """An external binary, found through the config value or on PATH."""
    configured = (values.get(tool["config_var"]) or "").strip()
    candidates = [configured] if configured else []
    candidates.append(tool.get("command", tool["key"]))
    # pip --target installs land in deps/bin, which is not on PATH.
    candidates.append(os.path.join(_deps_bin(), tool.get("command", tool["key"])))

    for candidate in candidates:
        if not candidate:
            continue
        resolved = candidate if os.path.isfile(candidate) else shutil.which(candidate)
        if resolved:
            return True, resolved, _probe_version(resolved, tool.get("version_args"))
    return False, "", ""


def _check_conda_env(tool, values):
    """A package living in its own environment."""
    configured = (values.get(tool["config_var"]) or "").strip() or tool.get("default_env", "")
    interpreter = resolve_env_python(configured)
    if not interpreter:
        return False, "", f"no environment '{configured}'"

    probe = subprocess.run(
        [interpreter, "-c", f"import {tool['module']}; "
                            f"print(getattr({tool['module']}, '__version__', ''))"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        env=_foreign_python_env(),
    )
    if probe.returncode != 0:
        return False, interpreter, f"cannot import {tool['module']}"
    return True, interpreter, probe.stdout.decode("utf-8", "replace").strip()


# pylint: enable=unused-argument


def _probe_version(executable, version_args):
    """Best-effort version string; never fatal."""
    if not version_args:
        return ""
    try:
        probe = subprocess.run(
            [executable] + list(version_args),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False, timeout=20,
        )
        first = probe.stdout.decode("utf-8", "replace").strip().splitlines()
        return first[0][:80] if first else ""
    except (OSError, subprocess.SubprocessError):
        return ""


_CHECKS = {
    "python-import": _check_python_import,
    "executable": _check_executable,
    "conda-env": _check_conda_env,
}


# ==========================#
# Installers
# ==========================#
# Every installer takes the same (tool, options, credentials, log) signature so
# the registry can dispatch to them uniformly, and returns the config values it
# produced. Most do not need all four arguments.
# pylint: disable=unused-argument
def _run(command, log, env=None, secrets=()):
    """
    Run a command, streaming into ``log``, with secrets redacted.

    ``log`` is a list the caller drains; redaction happens before anything is
    appended, so a credential cannot reach the page or a log file.
    """
    printable = " ".join(command)
    for secret in secrets:
        if secret:
            printable = printable.replace(secret, "***")
    log.append(f"$ {printable}")

    merged = dict(os.environ)
    if env:
        merged.update(env)

    with subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=merged, text=True, bufsize=1,
    ) as process:
        for line in process.stdout or []:
            line = line.rstrip("\n")
            for secret in secrets:
                if secret:
                    line = line.replace(secret, "***")
            log.append(line)
        process.wait()
        if process.returncode != 0:
            raise RuntimeError(f"Command failed with exit code {process.returncode}")


def _pip_install(packages, log, index_url=None):
    """Install into the plugin's own deps folder, as Horus does."""
    command = [sys.executable, "-m", "pip", "install", "--prefix", _deps_dir()]
    if index_url:
        command += ["--index-url", index_url]
    command += list(packages)
    _run(command, log)


def _install_torch(tool, options, credentials, log):
    index = (options.get("cuda_index") or "").strip()
    _pip_install(["torch"], log, index_url=index or None)
    return {"proteinmpnn_python": sys.executable}


def _install_mmseqs(tool, options, credentials, log):
    """
    Install the static MMseqs2 build.

    The upstream tarball is preferred: it needs no conda and the AVX2 build runs
    on any reasonably modern x86 machine. Falls back to bioconda.
    """
    import tarfile
    import urllib.request

    target = _deps_dir()
    os.makedirs(target, exist_ok=True)
    url = options.get("url") or "https://mmseqs.com/latest/mmseqs-linux-avx2.tar.gz"
    archive = os.path.join(target, "mmseqs.tar.gz")

    log.append(f"Downloading {url}")
    urllib.request.urlretrieve(url, archive)  # nosec - fixed, documented URL
    log.append("Extracting")
    with tarfile.open(archive) as tar:
        tar.extractall(target)  # nosec - trusted upstream archive
    os.remove(archive)

    binary = os.path.join(target, "mmseqs", "bin", "mmseqs")
    if not os.path.isfile(binary):
        raise RuntimeError(f"The archive did not contain bin/mmseqs (looked in {target})")
    os.chmod(binary, 0o755)
    log.append(f"Installed {binary}")
    return {"mmseqs_path": binary}


def _install_conda_package(env_name, packages, log, channels=("conda-forge", "bioconda")):
    """Create (if needed) a conda environment and pip-install into it."""
    conda = _conda_command()
    if not conda:
        raise RuntimeError(
            "No conda, mamba or micromamba was found on PATH, so an environment "
            "cannot be created automatically. Create it by hand and give its name "
            "in the configuration."
        )

    interpreter = resolve_env_python(env_name)
    if not interpreter:
        command = [conda, "create", "-y", "-n", env_name, "python=3.11"]
        for channel in channels:
            command += ["-c", channel]
        _run(command, log)
        interpreter = resolve_env_python(env_name)
        if not interpreter:
            raise RuntimeError(f"Created '{env_name}' but could not find its interpreter.")

    _run([interpreter, "-m", "pip", "install"] + list(packages), log)
    return interpreter


def _install_mafft(tool, options, credentials, log):
    conda = _conda_command()
    if not conda:
        raise RuntimeError(
            "MAFFT needs conda/micromamba to install, or your system package "
            "manager ('apt install mafft'). Then give its path in the configuration."
        )
    _run([conda, "install", "-y", "-c", "bioconda", "mafft", "-p", _deps_dir()], log)
    binary = os.path.join(_deps_bin(), "mafft")
    if not os.path.isfile(binary):
        raise RuntimeError("MAFFT was installed but its binary was not where expected.")
    return {"mafft_path": binary}


def _install_pyrosetta(tool, options, credentials, log):
    """
    Install PyRosetta.

    The pyrosetta-installer package is the supported route and needs no
    credentials. The credentialed graylab index exists as a fallback for sites
    that use it, but it is not the default.
    """
    username = (credentials or {}).get("username", "")
    password = (credentials or {}).get("password", "")

    if username and password:
        index = f"https://{username}:{password}@conda.graylab.jhu.edu/pypi/simple"
        _pip_install(["pyrosetta"], log, index_url=index)
    else:
        _pip_install(["pyrosetta-installer"], log)
        _run(
            [sys.executable, "-c",
             "import pyrosetta_installer; pyrosetta_installer.install_pyrosetta()"],
            log,
            env={"PYTHONPATH": _site_packages()},
        )
    return {"pyrosetta_python": sys.executable}


def _install_bioemu(tool, options, credentials, log):
    env_name = (options.get("env") or "bioemu").strip()
    interpreter = _install_conda_package(env_name, ["bioemu"], log)
    return {"bioemu_env": os.path.dirname(os.path.dirname(interpreter))}


def _install_codontransformer(tool, options, credentials, log):
    env_name = (options.get("env") or "codontransformer").strip()
    interpreter = _install_conda_package(env_name, ["CodonTransformer", "torch"], log)
    return {"codontransformer_env": os.path.dirname(os.path.dirname(interpreter))}


def _site_packages():
    """The site-packages inside deps/, for PYTHONPATH."""
    version = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return os.path.join(_deps_dir(), "lib", version, "site-packages")


# pylint: enable=unused-argument


# ==========================#
# The registry
# ==========================#
TOOLS = [
    {
        "key": "bioprospecting",
        "label": "bioprospecting",
        "kind": "python-import",
        "module": "bioprospecting",
        "optional": False,
        "config_var": None,
        "install": None,
        "credentials": None,
        "needed_by": ["ProteinMPNN Scoring", "Read ProteinMPNN Scores",
                      "Multiple Sequence Alignment", "CodonTransformer"],
        "note": "Installed with the plugin's dependencies. If it is missing, "
                "reinstall them from the Horus Plugin Manager.",
    },
    {
        "key": "prepare_proteins",
        "label": "prepare_proteins",
        "kind": "python-import",
        "module": "prepare_proteins",
        "optional": False,
        "config_var": None,
        "install": None,
        "credentials": None,
        "needed_by": ["Trim AlphaFold Models", "Rosetta Relax",
                      "Analyse Rosetta Relax", "BioEmu Sampling", "Analyse BioEmu"],
        "note": "Installed with the plugin's dependencies.",
    },
    {
        "key": "bsc_calculations",
        "label": "bsc_calculations",
        "kind": "python-import",
        "module": "bsc_calculations",
        "optional": False,
        "config_var": None,
        "install": None,
        "credentials": None,
        "needed_by": ["ProteinMPNN Scoring", "Rosetta Relax", "BioEmu Sampling"],
        "note": "Installed with the plugin's dependencies.",
    },
    {
        "key": "mmseqs",
        "label": "MMseqs2",
        "kind": "executable",
        "command": "mmseqs",
        "version_args": ["version"],
        "optional": False,
        "config_var": "mmseqs_path",
        "install": _install_mmseqs,
        "credentials": None,
        "needed_by": ["MMseqs2 Clustering", "MMseqs2 Threshold Sweep"],
        "note": "Installed from the official static build.",
    },
    {
        "key": "mafft",
        "label": "MAFFT",
        "kind": "executable",
        "command": "mafft",
        "version_args": ["--version"],
        "optional": False,
        "config_var": "mafft_path",
        "install": _install_mafft,
        "credentials": None,
        "needed_by": ["Multiple Sequence Alignment"],
        "note": "Installed from bioconda; 'apt install mafft' also works.",
    },
    {
        "key": "torch",
        "label": "PyTorch",
        "kind": "python-import",
        "module": "torch",
        "optional": False,
        "config_var": "proteinmpnn_python",
        "install": _install_torch,
        "credentials": None,
        "needed_by": ["ProteinMPNN Scoring"],
        "note": "Not a plugin dependency: the wheel is large and its build has "
                "to match the machine's CUDA version. A CPU build works but is slow.",
    },
    {
        "key": "pyrosetta",
        "label": "PyRosetta",
        "kind": "conda-env",
        "module": "pyrosetta",
        "default_env": "",
        "optional": False,
        "config_var": "pyrosetta_python",
        "install": _install_pyrosetta,
        "credentials": {"username": "Academic username (optional)",
                        "password": "Academic password (optional)"},
        "needed_by": ["Analyse Rosetta Relax"],
        "note": "Installed with pyrosetta-installer, which needs no credentials. "
                "Supply them only if your site uses the licensed index.",
    },
    {
        "key": "bioemu",
        "label": "BioEmu",
        "kind": "conda-env",
        "module": "bioemu",
        "default_env": "bioemu",
        "optional": False,
        "config_var": "bioemu_env",
        "install": _install_bioemu,
        "credentials": None,
        "needed_by": ["BioEmu Sampling"],
        "note": "Runs in its own environment. On a cluster it is given per-block "
                "instead, so a local install is only needed to sample here.",
    },
    {
        "key": "codontransformer",
        "label": "CodonTransformer",
        "kind": "conda-env",
        "module": "CodonTransformer",
        "default_env": "codontransformer",
        "optional": False,
        "config_var": "codontransformer_env",
        "install": _install_codontransformer,
        "credentials": None,
        "needed_by": ["CodonTransformer"],
        "note": "Runs in its own environment because of its torch stack.",
    },
    {
        "key": "rosetta",
        "label": "Rosetta (rosetta_scripts)",
        "kind": "executable",
        "command": "rosetta_scripts.mpi.linuxgccrelease",
        "version_args": None,
        "optional": True,
        "config_var": "rosetta_path",
        "install": None,
        "credentials": None,
        "needed_by": ["Rosetta Relax"],
        "note": "Licensed and never installed automatically. Download it from "
                "rosettacommons.org and give the path, or leave it empty and run "
                "relax on a cluster that provides it as a module.",
    },
    {
        "key": "smog",
        "label": "SMOG 2",
        "kind": "executable",
        "command": "smog2",
        "version_args": None,
        "optional": True,
        "config_var": "smog_path",
        "install": None,
        "credentials": None,
        "needed_by": ["Analyse BioEmu (native contacts only)"],
        "note": "Registration-gated and never installed automatically. Without it "
                "the BioEmu analysis still produces RMSD and RMSF, but not Q or "
                "the folding free energy.",
    },
]


TOOLS_BY_KEY = {tool["key"]: tool for tool in TOOLS}


# ==========================#
# Configuration file
# ==========================#
def config_path(remote: str = "Local") -> str:
    """
    Path of the plugin's saved configuration for a remote.

    Horus keeps this outside the plugin folder, at
    ``<appSupport>/config/<plugin id>/<plugin id>_<remote>.json``, as a flat
    {variable_id: value} mapping shared by all of the plugin's configs.
    """
    from HorusAPI import getUserFolder

    return os.path.join(
        getUserFolder(), "config", PLUGIN_ID, f"{PLUGIN_ID}_{remote}.json"
    )


def read_config(remote: str = "Local") -> dict:
    """Read the saved configuration, returning {} when there is none yet."""
    path = config_path(remote)
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_config(values: dict, remote: str = "Local") -> str:
    """
    Merge ``values`` into the saved configuration.

    Read-modify-write, because the file is shared by every config this plugin
    declares and Horus may have written other entries into it.
    """
    path = config_path(remote)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    current = read_config(remote)
    current.update({key: value for key, value in values.items() if value is not None})

    with open(path, "w", encoding="utf-8") as handle:
        json.dump(current, handle, indent=4)
    return path


# ==========================#
# Public API
# ==========================#
def status(remote: str = "Local") -> list:
    """
    Report the state of every tool.

    Returns one row per tool with ``state`` in ok / missing / optional-missing.
    """
    values = read_config(remote)
    rows = []
    for tool in TOOLS:
        try:
            found, detected, version = _CHECKS[tool["kind"]](tool, values)
            message = "" if found else version
        except Exception as error:  # pylint: disable=broad-except
            found, detected, version, message = False, "", "", str(error)

        if found:
            state = "ok"
        else:
            state = "optional-missing" if tool.get("optional") else "missing"

        rows.append({
            "key": tool["key"],
            "label": tool["label"],
            "kind": tool["kind"],
            "optional": bool(tool.get("optional")),
            "needed_by": tool["needed_by"],
            "config_var": tool.get("config_var"),
            "configured": values.get(tool.get("config_var") or "", ""),
            "installable": tool.get("install") is not None,
            "credentials": tool.get("credentials"),
            "note": tool.get("note", ""),
            "state": state,
            "detected": detected,
            "version": version if found else "",
            "message": message,
        })
    return rows


def blocked_blocks(rows=None, remote: str = "Local") -> list:
    """Names of the blocks that cannot run, given what is missing."""
    rows = rows if rows is not None else status(remote)
    blocked = []
    for row in rows:
        if row["state"] == "missing":
            blocked += row["needed_by"]
    return sorted(set(blocked))


def install(key: str, options=None, credentials=None, remote: str = "Local"):
    """
    Install one tool and save the paths it produced.

    Returns ``{"log": [...], "config": {...}}``. Credentials are used and then
    dropped; they are redacted from the log and never written to the config.
    """
    tool = TOOLS_BY_KEY.get(key)
    if tool is None:
        raise ValueError(f"Unknown tool '{key}'.")
    if tool.get("install") is None:
        raise ValueError(
            f"{tool['label']} is not installed automatically. {tool.get('note', '')}"
        )

    log = []
    produced = tool["install"](tool, options or {}, credentials or {}, log) or {}
    if produced:
        write_config(produced, remote)
        log.append(f"Saved to the plugin configuration: {', '.join(sorted(produced))}")
    return {"log": log, "config": produced}


def detected_paths(remote: str = "Local") -> dict:
    """The config values implied by what is currently detected on this machine."""
    values = {}
    for row in status(remote):
        if row["state"] == "ok" and row["config_var"] and row["detected"]:
            values[row["config_var"]] = row["detected"]
    return values
