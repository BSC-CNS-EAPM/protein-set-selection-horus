#!/usr/bin/env python3
"""
Record what a working installation of this plugin actually consists of.

A reproducibility record cannot be assembled from the repository alone. The
repository pins almost nothing: ``plugin.meta`` names three dependencies by git
URL with no commit, ``install_deps.sh`` takes MMseqs2 from ``mmseqs.com/latest``
and SMOG 2 from whatever its latest GitHub release is, and torch comes from
whatever the index serves that day. Two installs made a month apart are
therefore different software, and only the machine that ran a calculation knows
which one it had.

So this script is run *in that environment* -- the interpreter Horus uses, or
the one on the cluster -- and writes down what is there: interpreter and
platform, the installed version of every distribution ``plugin.meta`` asks for,
the resolved commit of each VCS dependency, and the version each external tool
reports when asked. Unknowns are recorded as nulls with a reason, never guessed.

Usage
-----

    Devtools/runtime_manifest.py                      # this interpreter
    Devtools/runtime_manifest.py --python /path/to/python
    Devtools/runtime_manifest.py -o manifest.json
    Devtools/runtime_manifest.py --tool mmseqs=/opt/mmseqs/bin/mmseqs

Home directories are written as ``~`` so a manifest can be shared without
carrying someone's account name. Check the output before sending it anyway:
cluster paths can still name a project or a user.
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PLUGIN_META = os.path.join(REPO, "ProtSelect", "plugin.meta")

#: Tools the plugin drives, and how to ask each one its version. The plugin
#: never bundles these; an installation may legitimately lack any of them.
TOOL_PROBES = {
    "mmseqs": ["version"],
    "mafft": ["--version"],
    "rosetta_scripts.mpi.linuxgccrelease": ["-version"],
    "colabfold_search": ["--help"],
}

#: Importable packages worth a version even though plugin.meta does not name
#: them: they live in their own environments (see docs/configuration.rst).
FOREIGN_MODULES = ("pyrosetta", "bioemu", "CodonTransformer", "torch", "mdtraj")


def run(command, timeout=30):
    """Return (returncode, first useful output line) without raising."""
    try:
        done = subprocess.run(command, capture_output=True, text=True,
                              timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        return None, f"{type(error).__name__}: {error}"
    text = (done.stdout or "") + (done.stderr or "")
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    return done.returncode, line


def mask_home(value):
    """Write the user's home directory as ``~``."""
    if not isinstance(value, str):
        return value
    home = os.path.expanduser("~")
    return value.replace(home, "~") if home and home != "/" else value


def declared_dependencies():
    """The dependency list from plugin.meta, split into PyPI and VCS entries."""
    try:
        with open(PLUGIN_META) as handle:
            meta = json.load(handle)
    except (OSError, ValueError) as error:
        return {}, [], {"error": f"could not read plugin.meta: {error}"}

    pypi, vcs = {}, []
    for entry in meta.get("dependencies") or []:
        if entry.startswith("git+"):
            vcs.append(entry)
        else:
            name = re.split(r"[<>=!~\[]", entry, maxsplit=1)[0].strip()
            pypi[name] = entry
    return pypi, vcs, {
        "plugin_version_in_source": meta.get("version"),
        "plugin_id": meta.get("id"),
    }


def installed_versions(python, names):
    """Ask an interpreter for the installed version of each distribution."""
    probe = (
        "import json,sys\n"
        "from importlib.metadata import version, PackageNotFoundError\n"
        "out={}\n"
        "for n in sys.argv[1:]:\n"
        "    try: out[n]=version(n)\n"
        "    except PackageNotFoundError: out[n]=None\n"
        "    except Exception as e: out[n]='error: %s' % e\n"
        "print(json.dumps(out))\n"
    )
    code, line = run([python, "-c", probe, *names], timeout=120)
    if code != 0:
        return {"error": line}
    try:
        return json.loads(line)
    except ValueError:
        return {"error": f"unparseable output: {line[:200]}"}


def vcs_commits(python, vcs_entries):
    """
    Resolve the commit each git dependency is installed at.

    pip records what it installed in ``direct_url.json`` (PEP 610), which is
    the only place the commit survives: ``plugin.meta`` names no ref, so the
    version number alone cannot say which commit is present.
    """
    names = []
    for entry in vcs_entries:
        match = re.search(r"/([^/]+?)(?:\.git)?(?:@.*)?$", entry)
        names.append(match.group(1) if match else entry)

    probe = (
        "import json,sys\n"
        "from importlib.metadata import distribution, PackageNotFoundError\n"
        "out={}\n"
        "for n in sys.argv[1:]:\n"
        "    key=n.replace('-','_')\n"
        "    try: d=distribution(n)\n"
        "    except PackageNotFoundError:\n"
        "        try: d=distribution(key)\n"
        "        except PackageNotFoundError:\n"
        "            out[n]={'installed': False}; continue\n"
        "    info={'installed': True, 'version': d.version, 'commit': None}\n"
        "    try:\n"
        "        raw=d.read_text('direct_url.json')\n"
        "        if raw:\n"
        "            du=json.loads(raw)\n"
        "            info['commit']=(du.get('vcs_info') or {}).get('commit_id')\n"
        "            info['requested_revision']=(du.get('vcs_info') or {}).get('requested_revision')\n"
        "            info['url']=du.get('url')\n"
        "    except Exception as e: info['commit_error']=str(e)\n"
        "    out[n]=info\n"
        "print(json.dumps(out))\n"
    )
    code, line = run([python, "-c", probe, *names], timeout=120)
    if code != 0:
        return {"error": line}
    try:
        resolved = json.loads(line)
    except ValueError:
        return {"error": f"unparseable output: {line[:200]}"}
    for entry, name in zip(vcs_entries, names):
        if name in resolved and isinstance(resolved[name], dict):
            resolved[name]["declared_as"] = entry
            resolved[name].setdefault("commit", None)
    return resolved


def foreign_module_versions(python):
    """Versions of packages that live in their own environments."""
    probe = (
        "import json,sys\n"
        "out={}\n"
        "for n in sys.argv[1:]:\n"
        "    try:\n"
        "        m=__import__(n)\n"
        "        out[n]=getattr(m,'__version__',None) or 'imported, no __version__'\n"
        "    except Exception as e: out[n]=None\n"
        "print(json.dumps(out))\n"
    )
    code, line = run([python, "-c", probe, *FOREIGN_MODULES], timeout=180)
    if code != 0:
        return {"error": line}
    try:
        return json.loads(line)
    except ValueError:
        return {"error": f"unparseable output: {line[:200]}"}


def tool_versions(extra):
    """What each external tool reports when asked its version."""
    probes = dict(TOOL_PROBES)
    found = {}
    for name, args in probes.items():
        command = extra.get(name, name)
        code, line = run([command, *args])
        found[name] = {
            "command": mask_home(command),
            "available": code is not None,
            "reported": mask_home(line) or None,
        }
    for name, command in extra.items():
        if name not in found:
            code, line = run([command, "--version"])
            found[name] = {
                "command": mask_home(command),
                "available": code is not None,
                "reported": mask_home(line) or None,
            }
    return found


def git_state():
    """The commit and tag of the checkout this script runs from, if any."""
    def git(*args):
        code, line = run(["git", "-C", REPO, *args])
        return line if code == 0 else None

    return {
        "commit": git("rev-parse", "HEAD"),
        "describe": git("describe", "--tags", "--always", "--dirty"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def horus_version(python):
    """
    Horus's own version, if this interpreter can see it.

    HorusAPI ships with the Horus application rather than PyPI, so an ordinary
    interpreter cannot import it and this stays null. Fill it in by hand from
    the application's About dialog.
    """
    probe = (
        "import json\n"
        "try:\n"
        "    import HorusAPI as h\n"
        "    print(json.dumps({'importable': True, 'version': getattr(h,'__version__',None),"
        " 'path': getattr(h,'__file__',None)}))\n"
        "except Exception as e:\n"
        "    print(json.dumps({'importable': False, 'reason': str(e)}))\n"
    )
    code, line = run([python, "-c", probe])
    if code != 0:
        return {"importable": False, "reason": line}
    try:
        found = json.loads(line)
    except ValueError:
        return {"importable": False, "reason": f"unparseable: {line[:120]}"}
    found["path"] = mask_home(found.get("path"))
    return found


def collect(python, extra_tools):
    pypi, vcs, meta = declared_dependencies()
    return {
        "recorded_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "recorded_by": "Devtools/runtime_manifest.py",
        "plugin": {**meta, "git": git_state()},
        "environment": {
            "interpreter": mask_home(python),
            "python": run([python, "-c", "import sys;print(sys.version.replace(chr(10),' '))"])[1],
            "platform": platform.platform(),
            "machine": platform.machine(),
            "node": platform.node(),
        },
        "horus": horus_version(python),
        "declared_dependencies": pypi,
        "installed_dependencies": installed_versions(python, sorted(pypi)) if pypi else {},
        "vcs_dependencies": vcs_commits(python, vcs) if vcs else {},
        "foreign_modules": foreign_module_versions(python),
        "external_tools": tool_versions(extra_tools),
        "seed_control": {
            "proteinmpnn": "exposed as the block's 'seed' setting (default 0)",
            "bioemu": None,
            "rosetta_relax": None,
            "codon_transformer": None,
            "note": "null means the block exposes no seed; those stages are not "
                    "reproducible run to run by setting anything in the flow.",
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("Usage", maxsplit=1)[0].strip()
    )
    parser.add_argument("--python", default=sys.executable,
                        help="the interpreter to inspect (default: this one)")
    parser.add_argument("-o", "--output", help="write JSON here instead of stdout")
    parser.add_argument("--tool", action="append", default=[], metavar="NAME=PATH",
                        help="probe this executable for NAME (repeatable)")
    args = parser.parse_args(argv)

    extra = {}
    for item in args.tool:
        name, _, path = item.partition("=")
        if not path:
            parser.error(f"--tool expects NAME=PATH, got {item!r}")
        extra[name] = path

    manifest = collect(args.python, extra)
    text = json.dumps(manifest, indent=2, sort_keys=False)

    if args.output:
        with open(args.output, "w") as handle:
            handle.write(text + "\n")
        print(f"Wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
