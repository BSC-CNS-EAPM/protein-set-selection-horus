"""
Plugin configuration for the BioEmu environment and the SMOG installation.

BioEmu runs in its own conda environment because it pulls in a large torch and
model stack that has no business in the plugin's own dependencies. SMOG is only
needed for the native-contacts half of the BioEmu analysis, which produces Q and
the folding free energy; it is registration-gated, so the plugin never installs
it and the analysis degrades gracefully without it.
"""

from HorusAPI import PluginConfig, PluginVariable, VariableTypes

bioemuEnvVariable = PluginVariable(
    id="bioemu_env",
    name="BioEmu environment",
    description="Name or path of the conda environment holding BioEmu. On a "
    "cluster this is set per-block instead, so it can be left empty here.",
    type=VariableTypes.STRING,
    defaultValue="bioemu",
)

smogPathVariable = PluginVariable(
    id="smog_path",
    name="SMOG executable (optional)",
    description="Path to the SMOG 2 executable, used for native contacts (Q and "
    "the folding free energy). Leave empty to skip that analysis phase.",
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
                "'conda create -n bioemu python=3.11 && pip install bioemu'."
            )
        else:
            probe = subprocess.run(
                [interpreter, "-c", "import bioemu; print('ok')"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
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
            "No SMOG executable configured. The BioEmu analysis will skip native "
            "contacts, so it produces RMSD and RMSF but not Q or the folding free "
            "energy. Disable 'Compute native contacts' on that block to match."
        )
        return

    resolved = smog_path if os.path.isfile(smog_path) else shutil.which(smog_path)
    if not resolved:
        raise Exception(
            f"The SMOG executable '{smog_path}' was not found. SMOG 2 requires "
            "registration and is not installed by this plugin; see "
            "https://smog-server.org, or clear this entry to skip native contacts."
        )
    print(f"Found SMOG at {resolved}")


bioemuExecutableConfig = PluginConfig(
    id="bioemu_environment",
    name="BioEmu environment",
    description="Configure the BioEmu conda environment and the optional SMOG "
    "installation used for native contacts",
    variables=[bioemuEnvVariable, smogPathVariable],
    action=checkBioEmuInstallation,
)
