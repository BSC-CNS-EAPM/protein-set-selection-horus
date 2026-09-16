"""
Plugin configuration for the CodonTransformer environment.

CodonTransformer needs torch and a transformers stack of its own, so it lives in
a separate conda environment rather than in the plugin's dependencies. The block
resolves that environment's ``bin`` onto PATH rather than calling
``conda activate``, which does not work on hosts where conda is provided by
micromamba.
"""

from HorusAPI import PluginConfig, PluginVariable, VariableTypes

codonTransformerEnvVariable = PluginVariable(
    id="codontransformer_env",
    name="CodonTransformer environment",
    description="Name of the conda environment holding CodonTransformer, a path to "
    "it, or a path to its python interpreter.",
    type=VariableTypes.STRING,
    defaultValue="codontransformer",
)


def _resolve_env_python(env: str):
    """Return the interpreter for an environment given by name, path or interpreter."""
    import os

    if os.path.isfile(env):
        return env

    candidates = []
    if os.path.isdir(env):
        candidates.append(os.path.join(env, "bin", "python"))
    else:
        for root in (
            os.path.expanduser("~/micromamba/envs"),
            os.path.expanduser("~/miniconda3/envs"),
            os.path.expanduser("~/anaconda3/envs"),
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


def checkCodonTransformerInstallation(block: PluginConfig):
    """Check that the configured environment can import CodonTransformer."""
    import subprocess

    env = (block.variables.get(codonTransformerEnvVariable.id) or "").strip()
    if not env:
        raise Exception(
            "No CodonTransformer environment configured. Create one with "
            "'conda create -n codontransformer python=3.11' followed by "
            "'pip install CodonTransformer', then name it here."
        )

    interpreter = _resolve_env_python(env)
    if not interpreter:
        raise Exception(
            f"Could not find an environment named '{env}'. Give its name, its path, "
            "or the path to its python interpreter."
        )

    print(f"Verifying CodonTransformer in {interpreter}")
    probe = subprocess.run(
        [interpreter, "-c", "import CodonTransformer, torch; print(torch.__version__)"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        env=_foreign_python_env(),
    )
    if probe.returncode != 0:
        raise Exception(
            f"The environment '{env}' cannot import CodonTransformer. Install it "
            "there with 'pip install CodonTransformer'.\n"
            f"{probe.stderr.decode('utf-8', 'replace').strip()}"
        )

    print(f"Found CodonTransformer with torch {probe.stdout.decode().strip()}")


codonTransformerExecutableConfig = PluginConfig(
    id="codontransformer_environment",
    name="CodonTransformer environment",
    description="Configure the conda environment used for codon optimisation",
    variables=[codonTransformerEnvVariable],
    action=checkCodonTransformerInstallation,
)
