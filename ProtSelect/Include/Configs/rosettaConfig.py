"""
Plugin configuration for the Rosetta installation used by the relax block.

Rosetta is licensed and distributed as a large compiled bundle, so the plugin
never installs it: point this at an existing installation, or at the module
path on a cluster. Note that this is the ``rosetta_scripts`` binary used to run
the relax itself; the *analysis* of the results uses PyRosetta, configured
separately.
"""

from HorusAPI import PluginConfig, PluginVariable, VariableTypes

rosettaPathVariable = PluginVariable(
    id="rosetta_path",
    name="Rosetta executable",
    description="Path to the rosetta_scripts executable, for example "
    "<rosetta>/main/source/bin/rosetta_scripts.mpi.linuxgccrelease. On a cluster "
    "this can be left empty and supplied by the loaded module instead.",
    type=VariableTypes.FILE,
    defaultValue="",
)


def checkRosettaInstallation(block: PluginConfig):
    """Check that the configured Rosetta executable exists and looks usable."""
    import os
    import shutil

    rosetta_path = (block.variables.get(rosettaPathVariable.id) or "").strip()

    if not rosetta_path:
        print(
            "No Rosetta executable configured. This is fine when the relax block "
            "runs on a cluster that provides Rosetta through a module, but the "
            "block cannot run locally without it."
        )
        return

    resolved = rosetta_path if os.path.isfile(rosetta_path) else shutil.which(rosetta_path)
    if not resolved:
        raise Exception(
            f"The Rosetta executable '{rosetta_path}' was not found. Rosetta is "
            "licensed and is not installed by this plugin; download it from "
            "https://rosettacommons.org and point this entry at "
            "main/source/bin/rosetta_scripts.*"
        )

    # Rosetta needs its database, which normally sits at <rosetta>/main/database.
    # It is found relative to the binary, so a binary without one will fail at
    # run time with a much less obvious message than this.
    print(f"Found Rosetta at {os.path.realpath(resolved)}")
    source_dir = os.path.dirname(os.path.dirname(os.path.realpath(resolved)))
    database = os.path.join(os.path.dirname(source_dir), "database")
    if os.path.isdir(database):
        print(f"Found the Rosetta database at {database}")
    else:
        print(
            "Warning: could not find the Rosetta database next to the executable "
            f"(looked in {database}). If relax fails, set -database explicitly or "
            "check the installation layout."
        )


rosettaExecutableConfig = PluginConfig(
    id="rosetta_executable",
    name="Rosetta executable",
    description="Configure the path to the rosetta_scripts executable used for relax",
    variables=[rosettaPathVariable],
    action=checkRosettaInstallation,
)
