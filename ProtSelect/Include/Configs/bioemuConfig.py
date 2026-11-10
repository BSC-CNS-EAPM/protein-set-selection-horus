"""
Plugin configuration for the BioEmu environment and the SMOG installation.

These saved entries support detection and validation. The execution blocks do
not currently read them: configure BioEmu on its sampling block and expose
smog2 on the Horus process PATH. Native-contact analysis must be disabled
explicitly if compatible cached contacts or SMOG2 are unavailable.

"""

from HorusAPI import PluginConfig, PluginVariable, VariableTypes

bioemuEnvVariable = PluginVariable(
    id="bioemu_env",
    name="BioEmu environment",
    description="Name or directory of the BioEmu environment to check locally. "
    "Sampling does not read this entry; configure its block environment fields.",
    type=VariableTypes.STRING,
    defaultValue="protselect",
)

smogPathVariable = PluginVariable(
    id="smog_path",
    name="SMOG executable (optional)",
    description="SMOG2 executable to check locally. Analysis does not read this "
    "entry: expose smog2 on PATH. To omit Q and dGf, disable Compute native "
    "contacts on Analyse BioEmu explicitly.",
    type=VariableTypes.FILE,
    defaultValue="",
)


def _resolve_env_python(env: str):
    """Return the interpreter for a conda environment given by name or path."""
    import os

    candidates = []
    if os.path.isdir(env):
        candidates.append(os.path.join(env, "bin", "python"))
    else:
        for root in (
            os.path.expanduser("~/miniconda3/envs"),
            os.path.expanduser("~/anaconda3/envs"),
            os.path.expanduser("~/micromamba/envs"),
            os.path.expanduser("~/mambaforge/envs"),
        ):
            candidates.append(os.path.join(root, env, "bin", "python"))

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


def _foreign_python_env():
    """
    Environment for invoking an interpreter other than the one running Horus.

    Horus puts the plugin's own deps site-packages on PYTHONPATH, and a
    subprocess inherits it. Pointed at an environment on a different Python
    version that breaks the very imports being checked, with a numpy error that
    gives no hint of the cause. See sequence_io.foreign_python_env.
    """
    import os

    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(name, None)
    return env


def checkBioEmuInstallation(block: PluginConfig):
    """Check the BioEmu environment, and SMOG if one was configured."""
    import os
    import shutil
    import subprocess

    env = (block.variables.get(bioemuEnvVariable.id) or "").strip()

    if not env:
        print(
            "No BioEmu environment configured. The sampling block can still run "
            "on a cluster, where the environment is given per-block."
        )
    else:
        interpreter = _resolve_env_python(env)
        if not interpreter:
            print(
                f"Warning: could not find a local conda environment named '{env}'. "
                "This is expected when BioEmu only exists on the cluster; if you "
                "meant to run it locally, create the environment with "
                "install_deps.sh, which puts it in the 'protselect' environment."
            )
        else:
            probe = subprocess.run(
                [interpreter, "-c", "import bioemu; print('ok')"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
                env=_foreign_python_env(),
            )
            if probe.returncode != 0:
                raise Exception(
                    f"The environment '{env}' exists at {interpreter} but cannot "
                    "import bioemu. Install it there with 'pip install bioemu'.\n"
                    f"{probe.stderr.decode('utf-8', 'replace').strip()}"
                )
            print(f"Found BioEmu in {interpreter}")

    smog_path = (block.variables.get(smogPathVariable.id) or "").strip()
    if not smog_path:
        print(
            "No SMOG executable configured for this check. Analyse BioEmu uses "
            "smog2 on PATH or cached contacts. To omit Q and dGf, disable "
            "'Compute native contacts' on the analysis block explicitly."
        )
        return

    resolved = smog_path if os.path.isfile(smog_path) else shutil.which(smog_path)
    if not resolved:
        raise Exception(
            f"The SMOG executable '{smog_path}' was not found. Install SMOG2 "
            "separately or with install_deps.sh; see https://smog-server.org. "
            "Clearing this entry does not disable native-contact analysis."
        )
    print(f"Found SMOG at {resolved}")


bioemuExecutableConfig = PluginConfig(
    id="bioemu_environment",
    name="BioEmu environment",
    description="Check a local BioEmu environment and optional SMOG2 executable. "
    "Execution uses block settings and PATH instead of these saved entries.",
    variables=[bioemuEnvVariable, smogPathVariable],
    action=checkBioEmuInstallation,
)
