"""
Plugin configuration for the interpreter that runs ProteinMPNN locally.

ProteinMPNN is invoked as a subprocess and needs torch, which is deliberately
not one of the plugin's pip dependencies: the wheel is large and its build has
to match the machine's CUDA version. Point this at an environment that has it.
"""

from HorusAPI import PluginConfig, PluginVariable, VariableTypes

proteinmpnnPythonVariable = PluginVariable(
    id="proteinmpnn_python",
    name="ProteinMPNN Python interpreter",
    description="Python interpreter with torch installed, used to run ProteinMPNN "
    "on the local machine. Leave empty to use the interpreter running Horus.",
    type=VariableTypes.FILE,
    defaultValue="",
)


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


def checkProteinMPNNInstallation(block: PluginConfig):
    """Check that the configured interpreter can import torch."""
    import os
    import subprocess
    import sys

    interpreter = (block.variables.get(proteinmpnnPythonVariable.id) or "").strip()
    if not interpreter:
        interpreter = sys.executable
        print(f"No interpreter configured; falling back to {interpreter}")

    # Accept an environment directory as well as an interpreter path
    if os.path.isdir(interpreter):
        candidate = os.path.join(interpreter, "bin", "python")
        if os.path.isfile(candidate):
            interpreter = candidate

    if not os.path.isfile(interpreter):
        raise Exception(
            f"The interpreter '{interpreter}' does not exist. Point this at the "
            "python of an environment that has torch installed."
        )

    print(f"Verifying torch in {interpreter}")
    probe = subprocess.run(
        [interpreter, "-c", "import torch; print(torch.__version__)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        env=_foreign_python_env(),
    )
    if probe.returncode != 0:
        raise Exception(
            f"The interpreter '{interpreter}' cannot import torch. Install torch "
            "into that environment, or point this entry at one that has it.\n"
            f"{probe.stderr.decode('utf-8', 'replace').strip()}"
        )

    version = probe.stdout.decode("utf-8", "replace").strip()
    print(f"Found torch {version}")

    cuda_probe = subprocess.run(
        [interpreter, "-c", "import torch; print(torch.cuda.is_available())"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
        env=_foreign_python_env(),
    )
    if cuda_probe.stdout.decode("utf-8", "replace").strip() != "True":
        print(
            "Note: torch reports no CUDA device. ProteinMPNN will run on CPU, "
            "which works but is much slower; keep the model count small."
        )


proteinmpnnExecutableConfig = PluginConfig(
    id="proteinmpnn_interpreter",
    name="ProteinMPNN interpreter",
    description="Configure the Python interpreter used to run ProteinMPNN locally",
    variables=[proteinmpnnPythonVariable],
    action=checkProteinMPNNInstallation,
)
