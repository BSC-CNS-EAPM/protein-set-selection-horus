"""
Module containing the ProteinMPNN scoring block.

Scores a folder of protein structures with ProteinMPNN, which is the first
stage of the selection workflow: the score measures how well the sequence a
model already carries matches the backbone it sits on, and is used downstream
to rank the members of each sequence cluster.

ProteinMPNN ships two sets of weights. The "vanilla" weights are trained on all
of the PDB; the "soluble" weights exclude membrane proteins and so favour
sequences that express solubly. The reference workflow scores with both and
keeps the union of the two selections. Set the weight set to "both" and this
block runs each in turn, writing them side by side for the score reader to pick
up; there is no need to place the block twice.

The work is GPU-bound. On a cluster the jobs go into a SLURM array; locally
they are spread over the machine's GPUs, several at a time per GPU. Running on
CPU works and is the only option on many machines, but is much slower, so keep
the model count small when testing.
"""

from HorusAPI import PluginVariable, SlurmBlock, VariableTypes
from utils import BSC_JOB_VARIABLES, downloadResultsAction, gpusVariable, launchCalculationAction, removal_requested

# ==========================#
# Variable inputs
# ==========================#
pdbsFolder = PluginVariable(
    id="pdbs_folder",
    name="Structures folder",
    description="Folder of PDB structures to score.",
    type=VariableTypes.FOLDER,
)
sequencesFile = PluginVariable(
    id="sequences_file",
    name="Sequences file (optional)",
    description="Extra sequences to evaluate against each backbone, as a FASTA file "
    "or a JSON {name: sequence} mapping. Leave empty to score the sequence each "
    "structure already carries.",
    type=VariableTypes.FILE,
    allowedValues=["fasta", "fa", "faa", "json"],
    required=False,
)

# ==========================#
# Variables (parameters)
# ==========================#
folderNameVariable = PluginVariable(
    id="folder_name",
    name="Output folder name",
    description="Name of the job folder. Each weight set is written to a subfolder "
    "named after it (vanilla/, soluble/).",
    type=VariableTypes.STRING,
    defaultValue="proteinmpnn",
)
weightsVariable = PluginVariable(
    id="weights",
    name="Weight set",
    description="Which ProteinMPNN weights to score with. The soluble weights "
    "exclude membrane proteins and favour solubly expressing sequences. Each set "
    "is written to a subfolder named after it; 'both' runs the two in turn, which "
    "is what the reference workflow compares.",
    type=VariableTypes.STRING_LIST,
    defaultValue="both",
    allowedValues=["vanilla", "soluble", "both"],
)
numSeqPerTargetVariable = PluginVariable(
    id="num_seq_per_target",
    name="Sequences per target",
    description="Number of sequences sampled per structure.",
    type=VariableTypes.INTEGER,
    defaultValue=100,
)
evaluatePdbSequenceVariable = PluginVariable(
    id="evaluate_pdb_sequence",
    name="Evaluate the PDB sequence",
    description="Score the sequence already present in each structure. This is what "
    "produces the per-model score the selection blocks consume.",
    type=VariableTypes.BOOLEAN,
    defaultValue=True,
)
scoreOnlyVariable = PluginVariable(
    id="score_only",
    name="Score only",
    description="Only score the given sequences instead of designing new ones.",
    type=VariableTypes.BOOLEAN,
    defaultValue=True,
)
modelNameVariable = PluginVariable(
    id="model_name",
    name="Model weights",
    description="Which ProteinMPNN weight file to use. The number is the training "
    "noise level in hundredths of an Angstrom; v_48_020 is the usual default.",
    type=VariableTypes.STRING_LIST,
    defaultValue="v_48_020",
    allowedValues=["v_48_002", "v_48_010", "v_48_020", "v_48_030"],
)
samplingTempVariable = PluginVariable(
    id="sampling_temp",
    name="Sampling temperature",
    description="Sampling temperature for sequence design. Lower values give more "
    "conservative sequences.",
    type=VariableTypes.FLOAT,
    defaultValue=0.1,
)
batchSizeVariable = PluginVariable(
    id="batch_size",
    name="Batch size",
    description="Number of sequences generated per forward pass. Raise it to use a "
    "large GPU more fully; it must not exceed the sequences per target.",
    type=VariableTypes.INTEGER,
    defaultValue=1,
)
backboneNoiseVariable = PluginVariable(
    id="backbone_noise",
    name="Backbone noise",
    description="Standard deviation of the Gaussian noise added to backbone atoms.",
    type=VariableTypes.FLOAT,
    defaultValue=0.0,
)
seedVariable = PluginVariable(
    id="seed",
    name="Random seed",
    description="Seed for reproducible sampling.",
    type=VariableTypes.INTEGER,
    defaultValue=0,
)
skipFinishedVariable = PluginVariable(
    id="skip_finished",
    name="Skip finished",
    description="Skip models that already have results in the output folder.",
    type=VariableTypes.BOOLEAN,
    defaultValue=True,
)
overwriteVariable = PluginVariable(
    id="overwrite",
    name="Overwrite",
    description="Overwrite existing per-model results.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)
localGpusVariable = PluginVariable(
    id="local_gpus",
    name="Local GPUs",
    description="When running locally, how many GPUs to spread the jobs over. Set 1 "
    "on a machine with a single GPU or no GPU at all.",
    type=VariableTypes.INTEGER,
    defaultValue=2,
)
localParallelVariable = PluginVariable(
    id="local_parallel",
    name="Local jobs per GPU",
    description="When running locally, how many jobs to run at once on each GPU.",
    type=VariableTypes.INTEGER,
    defaultValue=4,
)
clusterEnvVariable = PluginVariable(
    id="cluster_env",
    name="Cluster environment",
    description="Path to the conda environment providing torch on the cluster. "
    "bsc_calculations has no ProteinMPNN preset, so the environment is given "
    "explicitly; the LigandMPNN environment serves, being a torch environment.",
    type=VariableTypes.STRING,
    defaultValue="/gpfs/projects/bsc72/conda_envs/ligandmpnn",
)
clusterModulesVariable = PluginVariable(
    id="cluster_modules",
    name="Cluster modules",
    description="Comma-separated modules to load on the cluster before the job.",
    type=VariableTypes.STRING,
    defaultValue="bsc/1.0, anaconda",
)
removeExistingResultsVariable = PluginVariable(
    id="remove_existing_results",
    name="Remove existing results",
    description="Delete the existing results folder before running. Only applied when the "
    "run is started from this block: a run that reaches it through its "
    "connections keeps the results.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)

# ==========================#
# Variable outputs
# ==========================#
pmpnnFolder = PluginVariable(
    id="pmpnn_folder",
    name="ProteinMPNN folder",
    description="Folder holding the ProteinMPNN job and its per-model score files.",
    type=VariableTypes.FOLDER,
)


def _use_env_python(jobs, env_path):
    """
    Call an environment's interpreter by path instead of relying on ``python``.

    The commands ``bioprospecting`` generates start with a bare ``python``,
    which resolves against whatever PATH the block happens to inherit. That is
    rarely the environment holding torch, so rewrite it to an absolute path.
    The lookbehind avoids touching a ``python`` that is part of a longer path
    or word, and the lookahead only matches the interpreter position.
    """
    import os
    import re

    env_python = env_path
    if os.path.isdir(env_path):
        env_python = os.path.join(env_path, "bin", "python")

    return [re.sub(r"(?<![\w./-])python(?= )", env_python, job) for job in jobs]


def initial_proteinmpnn(block: SlurmBlock):
    """
    Set up the ProteinMPNN scoring jobs and run or submit them.

    Args:
        block (SlurmBlock): The block to run the action on.
    """
    # pylint: disable=import-outside-toplevel
    import os
    import shutil
    import sys

    from sequence_io import read_sequences

    # pylint: enable=import-outside-toplevel

    pdbs_folder = block.inputs.get(pdbsFolder.id, None)
    if not pdbs_folder or pdbs_folder == "None":
        raise Exception("No structures folder provided.")
    if not os.path.isdir(pdbs_folder):
        raise Exception(f"The structures folder '{pdbs_folder}' does not exist.")

    pdb_count = len([f for f in os.listdir(pdbs_folder) if f.endswith(".pdb")])
    if pdb_count == 0:
        raise Exception(f"There are no pdb files in the structures folder: {pdbs_folder}")

    folder_name = block.variables.get(folderNameVariable.id, "proteinmpnn")
    remove_existing = removal_requested(
        block, block.variables.get(removeExistingResultsVariable.id, False), folder_name
    )

    if remove_existing and os.path.exists(folder_name):
        shutil.rmtree(folder_name, ignore_errors=True)

    # An existing folder is reused, so a run that stopped part-way (walltime,
    # cancelled job) resumes: with 'Skip finished' on, only the models without
    # output get new jobs.
    if os.path.exists(folder_name) and not remove_existing:
        print(f"Reusing the existing folder '{folder_name}'. Finished models are "
              "skipped when 'Skip finished' is on.")

    block.extraData["folder_name"] = folder_name
    # extraData outlives a run; clear the flag a previous resume may have left.
    block.extraData["nothing_to_run"] = False

    sequences = None
    sequences_path = block.inputs.get(sequencesFile.id, None)
    if sequences_path and sequences_path != "None":
        sequences = read_sequences(sequences_path)
        print(f"Evaluating {len(sequences)} supplied sequence(s) against each backbone.")

    weights = block.variables.get(weightsVariable.id, "both") or "both"
    # Every weight set gets its own subfolder, named after it, even when only
    # one is run. That is what lets the score reader route each one to the
    # matching output: from the folder layout alone it could not otherwise tell
    # a vanilla-only run from a soluble-only one.
    labels = ["vanilla", "soluble"] if weights == "both" else [weights]
    runs = [(label, os.path.join(folder_name, label), label == "soluble")
            for label in labels]

    is_local = block.remote.isLocal

    print(f"Setting up ProteinMPNN for {pdb_count} structure(s) using the "
          f"{weights} weight set(s)...")

    # pylint: disable=import-outside-toplevel
    try:
        from bioprospecting.predictions.proteinMPNN import setUPProteinMPNNCalculations
    except ImportError as error:
        raise Exception(
            "Could not import bioprospecting, which provides ProteinMPNN. It is "
            "installed with the plugin's dependencies; reinstall them from the "
            "Horus Plugin Manager if this persists."
        ) from error
    # pylint: enable=import-outside-toplevel

    # gpu_local is what makes bioprospecting emit the 'CUDA_VISIBLE_DEVICES=GPUID'
    # prefix that bsc_calculations substitutes per GPU slot. It must track the
    # execution target: on the cluster the job array assigns the GPU instead.
    jobs = []
    for label, job_folder, soluble in runs:
        print(f"  {label}: {job_folder}")
        jobs += setUPProteinMPNNCalculations(
            job_folder,
            pdbs_folder,
            sequences=sequences,
            num_seq_per_target=block.variables.get(numSeqPerTargetVariable.id, 100),
            evaluate_pdb_sequence=block.variables.get(evaluatePdbSequenceVariable.id, True),
            score_only=block.variables.get(scoreOnlyVariable.id, True),
            model_name=block.variables.get(modelNameVariable.id, "v_48_020"),
            use_soluble_model=soluble,
            sampling_temp=block.variables.get(samplingTempVariable.id, 0.1),
            batch_size=block.variables.get(batchSizeVariable.id, 1),
            backbone_noise=block.variables.get(backboneNoiseVariable.id, 0.0),
            seed=block.variables.get(seedVariable.id, 0),
            skip_finished=block.variables.get(skipFinishedVariable.id, True),
            overwrite=block.variables.get(overwriteVariable.id, False),
            gpu_local=is_local,
        )

    if not jobs:
        # Every model already has results: a complete result, not a failure.
        # The final action picks up the folder as it stands.
        print("Every model already has results; nothing to run. Disable "
              "'Skip finished' to score them again.")
        block.extraData["nothing_to_run"] = True
        return

    print(f"Generated {len(jobs)} ProteinMPNN job(s).")

    if is_local:
        # The generated commands call a bare 'python'. Locally that is whatever
        # is on PATH, which is usually not the environment holding torch, so
        # point them at the configured interpreter. On the cluster the activated
        # conda environment supplies the right one.
        interpreter = block.config.get("proteinmpnn_python") or sys.executable
        jobs = _use_env_python(jobs, interpreter)

        local_gpus = int(block.variables.get(localGpusVariable.id, 2) or 1)
        local_parallel = int(block.variables.get(localParallelVariable.id, 4) or 1)

        launchCalculationAction(
            block,
            jobs,
            program=None,
            uploadFolders=None,
            localGPU={"gpus": local_gpus, "parallel": local_parallel},
        )
    else:
        cluster_env = (block.variables.get(clusterEnvVariable.id) or "").strip()
        modules = [
            module.strip()
            for module in (block.variables.get(clusterModulesVariable.id) or "").split(",")
            if module.strip()
        ]

        # program is None because bsc_calculations has no 'proteinmpnn' preset;
        # the torch environment is supplied explicitly instead.
        launchCalculationAction(
            block,
            jobs,
            program=None,
            uploadFolders=[folder_name],
            condaEnv=cluster_env or None,
            modules=modules or None,
        )


def final_proteinmpnn(block: SlurmBlock):
    """
    Collect the ProteinMPNN results once the jobs have finished.

    Args:
        block (SlurmBlock): The block to run the action on.
    """
    # pylint: disable=import-outside-toplevel
    import os

    # pylint: enable=import-outside-toplevel

    if block.extraData.get("nothing_to_run"):
        downloaded = os.getcwd()
    else:
        downloaded = downloadResultsAction(block)

    folder_name = block.extraData.get("folder_name", "proteinmpnn")
    output_folder = os.path.join(downloaded, folder_name)

    print(f"ProteinMPNN results are in {output_folder}")
    block.setOutput(pmpnnFolder.id, output_folder)


proteinMPNNBlock = SlurmBlock(
    category="ProteinMPNN",
    name="ProteinMPNN Scoring",
    id="proteinmpnn_scoring",
    description="Score a folder of structures with ProteinMPNN, with the vanilla "
    "weights, the soluble weights, or both.",
    inputs=[pdbsFolder, sequencesFile],
    variables=BSC_JOB_VARIABLES
    + [
        gpusVariable,
        folderNameVariable,
        weightsVariable,
        numSeqPerTargetVariable,
        evaluatePdbSequenceVariable,
        scoreOnlyVariable,
        modelNameVariable,
        samplingTempVariable,
        batchSizeVariable,
        backboneNoiseVariable,
        seedVariable,
        skipFinishedVariable,
        overwriteVariable,
        localGpusVariable,
        localParallelVariable,
        clusterEnvVariable,
        clusterModulesVariable,
        removeExistingResultsVariable,
    ],
    outputs=[pmpnnFolder],
    initialAction=initial_proteinmpnn,
    finalAction=final_proteinmpnn,
)
