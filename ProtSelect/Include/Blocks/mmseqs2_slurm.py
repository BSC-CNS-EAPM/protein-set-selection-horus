"""
Run MMseqs2 sequence clustering on an HPC cluster via SLURM.

The SLURM counterpart of the local ``MMseqs2 Clustering`` block, running the
same ``mmseqs easy-cluster`` call. It earns its place on large families, where
clustering is slow enough to be worth a job; for a few hundred sequences the
local block is faster than the queue wait.

Like every other compute block here it goes through the shared launcher in
``utils``, so it gets the same Slurm variables, the account and time handling
that ``bsc_calculations`` applies, and the same upload/submit/download cycle.
The block it replaces hand-rolled its own SBATCH header, which meant it emitted
no ``--account`` unless one was typed in, did no time clamping, and offered a
different set of fields in the UI from the blocks either side of it.

MMseqs2 is not a program ``bsc_calculations`` knows, so the environment is
supplied through the usual "cluster modules" variable -- on MareNostrum that is
``mmseqs2/15-6f452`` -- or through a free-text preamble for anything a module
does not cover.
"""

import os

from HorusAPI import PluginVariable, SlurmBlock, VariableTypes
from utils import BSC_JOB_VARIABLES, downloadResultsAction, launchCalculationAction

# ==========================#
# Input
# ==========================#
sequencesFile = PluginVariable(
    id="sequences_file",
    name="Sequences file",
    description="Sequences to cluster. Either a FASTA file or a JSON file mapping "
    "sequence name to sequence.",
    type=VariableTypes.FILE,
    allowedValues=["fasta", "fa", "faa", "json"],
)

# ==========================#
# Variables (parameters)
# ==========================#
folderNameVariable = PluginVariable(
    id="folder_name",
    name="Output folder name",
    description="Name of the job folder holding the MMseqs2 input and results.",
    type=VariableTypes.STRING,
    defaultValue="mmseqs_clustering",
)
minSeqIdVariable = PluginVariable(
    id="min_seq_id",
    name="Minimum sequence identity",
    description="List matches above this sequence identity for clustering "
    "(--min-seq-id, range 0.0-1.0).",
    type=VariableTypes.FLOAT,
    defaultValue=0.5,
)
coverageVariable = PluginVariable(
    id="coverage",
    name="Coverage",
    description="Minimum alignment coverage (-c, range 0.0-1.0).",
    type=VariableTypes.FLOAT,
    defaultValue=0.8,
)
covModeVariable = PluginVariable(
    id="cov_mode",
    name="Coverage mode",
    description="MMseqs2 coverage mode (--cov-mode). 0: bidirectional, "
    "1: target coverage, 2: query coverage.",
    type=VariableTypes.INTEGER,
    defaultValue=1,
)
clusterModulesVariable = PluginVariable(
    id="cluster_modules",
    name="Cluster modules",
    description="Comma-separated modules loaded before the job. MMseqs2 is not on "
    "PATH by default on MareNostrum; 'bsc/1.0, mmseqs2/15-6f452' provides it.",
    type=VariableTypes.STRING,
    defaultValue="bsc/1.0, mmseqs2/15-6f452",
)
preambleVariable = PluginVariable(
    id="preamble",
    name="Preamble",
    description="Extra shell lines run before MMseqs2, for anything the modules do "
    "not cover (sourcing a conda profile, exporting a licence path).",
    type=VariableTypes.TEXT_AREA,
    defaultValue="",
)
mpiRunnerVariable = PluginVariable(
    id="mpi_runner",
    name="MPI runner",
    description="Exported as RUNNER on the cluster, which MMseqs2 prefixes to its "
    "MPI-parallel steps. The MareNostrum module is an MPI build: without this, "
    "kmermatcher calls MPI_Init outside a launcher and aborts with 'PMI2_Job_GetId "
    "returned 14'. Clear it for a non-MPI build, where srun would instead start one "
    "full copy of each step per task. Not used when running locally.",
    type=VariableTypes.STRING,
    defaultValue="srun",
)
mmseqsCommandVariable = PluginVariable(
    id="mmseqs_command",
    name="MMseqs2 command",
    description="The MMseqs2 executable to call. Leave as 'mmseqs' when a module "
    "puts it on PATH; when the block runs locally that default is replaced by the "
    "plugin's configured MMseqs2 path. Give an absolute path to override both.",
    type=VariableTypes.STRING,
    defaultValue="mmseqs",
)
removeExistingResultsVariable = PluginVariable(
    id="remove_existing_results",
    name="Remove existing results",
    description="Delete the job folder if it already exists.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)

# ==========================#
# Outputs
# ==========================#
clustersFile = PluginVariable(
    id="clusters_file",
    name="Clusters file",
    description="JSON file mapping each cluster representative to the list of its members.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
representativesFile = PluginVariable(
    id="representatives_file",
    name="Representatives FASTA",
    description="FASTA file with one representative sequence per cluster.",
    type=VariableTypes.FILE,
    allowedValues=["fasta"],
)
resultsFolder = PluginVariable(
    id="results_folder",
    name="MMseqs2 results folder",
    description="Folder holding the raw MMseqs2 output (cluster TSV, representative "
    "and all-sequences FASTA).",
    type=VariableTypes.FOLDER,
)

# MMseqs2 easy-cluster output prefix used inside the job folder
CLUSTER_PREFIX = "clusterRes"


def initial_mmseqs_slurm(block: SlurmBlock):
    """
    Write the MMseqs2 input and command, and submit the job.

    Args:
        block (SlurmBlock): The block to run the action on.
    """
    # pylint: disable=import-outside-toplevel
    import shlex
    import shutil

    from sequence_io import read_sequences, write_fasta

    # pylint: enable=import-outside-toplevel

    sequences_path = block.inputs.get(sequencesFile.id, None)
    if not sequences_path or sequences_path == "None":
        raise Exception("No sequences file provided.")
    if not os.path.isfile(sequences_path):
        raise Exception(f"The sequences file '{sequences_path}' does not exist.")

    folder_name = block.variables.get(folderNameVariable.id, "mmseqs_clustering")
    remove_existing = block.variables.get(removeExistingResultsVariable.id, False)

    if remove_existing and os.path.exists(folder_name):
        shutil.rmtree(folder_name, ignore_errors=True)
    if not remove_existing and os.path.exists(folder_name):
        raise Exception(
            f"The folder {folder_name} already exists. "
            "Please, choose another name or remove it with the remove existing folder option."
        )

    os.makedirs(folder_name, exist_ok=True)
    block.extraData["folder_name"] = folder_name

    # MMseqs2 only reads FASTA, and the pipeline passes JSON around, so normalise
    # here rather than making the caller convert.
    sequences = read_sequences(sequences_path)
    input_fasta = write_fasta(sequences, os.path.join(folder_name, "input.fasta"))
    print(f"Clustering {len(sequences)} sequences with MMseqs2 on the cluster...")

    mmseqs_cmd = (block.variables.get(mmseqsCommandVariable.id) or "mmseqs").strip()
    if block.remote.isLocal and mmseqs_cmd == "mmseqs":
        # The default is right on a cluster, where a module puts mmseqs on PATH,
        # and wrong locally, where it usually lives in an environment of its
        # own. The plugin configuration already knows where; use it.
        from sequence_io import resolve_executable  # pylint: disable=import-outside-toplevel

        mmseqs_cmd = resolve_executable(block, "mmseqs_path", "mmseqs")
    cpus_per_task = block.variables.get("cpus_per_task") or 1

    command = " ".join([
        shlex.quote(mmseqs_cmd),
        "easy-cluster",
        shlex.quote(os.path.basename(input_fasta)),
        CLUSTER_PREFIX,
        "tmp",
        "--min-seq-id", str(block.variables.get(minSeqIdVariable.id, 0.5)),
        "-c", str(block.variables.get(coverageVariable.id, 0.8)),
        "--cov-mode", str(block.variables.get(covModeVariable.id, 1)),
        "--threads", str(int(cpus_per_task)),
    ])

    # easy-cluster writes its output into the working directory, so the job has
    # to run inside the folder that travels to the cluster.
    quoted_folder = shlex.quote(folder_name)
    job = f"cd {quoted_folder}\n{command}\ncd -"

    # MPI builds need their steps launched through srun to initialise; see the
    # mpi_runner variable. Only on the cluster: locally there is no srun, and
    # the configured binary is not an MPI build.
    runner = (block.variables.get(mpiRunnerVariable.id) or "").strip()
    if runner and not block.remote.isLocal:
        job = f"export RUNNER={shlex.quote(runner)}\n" + job

    preamble = (block.variables.get(preambleVariable.id) or "").strip()
    if preamble:
        job = preamble + "\n" + job

    modules = [
        module.strip()
        for module in (block.variables.get(clusterModulesVariable.id) or "").split(",")
        if module.strip()
    ]

    # program=None: bsc_calculations has no MMseqs2 preset, so the environment
    # comes from the modules above.
    launchCalculationAction(
        block,
        [job],
        program=None,
        uploadFolders=[folder_name],
        modules=modules or None,
    )


def final_mmseqs_slurm(block: SlurmBlock):
    """
    Download the results and build the clustering map.

    Args:
        block (SlurmBlock): The block to run the action on.
    """
    # pylint: disable=import-outside-toplevel
    import json
    import shutil

    # pylint: enable=import-outside-toplevel

    downloaded = downloadResultsAction(block)
    folder_name = block.extraData.get("folder_name", "mmseqs_clustering")
    results = os.path.join(downloaded, folder_name)

    cluster_tsv = os.path.join(results, CLUSTER_PREFIX + "_cluster.tsv")
    if not os.path.isfile(cluster_tsv):
        raise Exception(
            f"MMseqs2 clustering result not found ({cluster_tsv}). "
            "Check the job's .err file in the results folder."
        )

    clusters: dict = {}
    with open(cluster_tsv) as cr:
        for line in cr:
            if not line.strip():
                continue
            representative, member = line.split()
            clusters.setdefault(representative, []).append(member)

    clusters_output = "mmseqs_clusters.json"
    with open(clusters_output, "w") as jf:
        json.dump(clusters, jf, indent=2)

    representatives_output = "mmseqs_representatives.fasta"
    rep_seq_fasta = os.path.join(results, CLUSTER_PREFIX + "_rep_seq.fasta")
    if os.path.isfile(rep_seq_fasta):
        shutil.copyfile(rep_seq_fasta, representatives_output)

    print(f"MMseqs2 finished: {len(clusters)} clusters. Results in {results}")

    block.setOutput(clustersFile.id, clusters_output)
    if os.path.isfile(representatives_output):
        block.setOutput(representativesFile.id, representatives_output)
    block.setOutput(resultsFolder.id, results)


mmseqsClusterSlurmBlock = SlurmBlock(
    category="Clustering & Selection",
    name="MMseqs2 Clustering (SLURM)",
    id="mmseqs2_cluster_slurm",
    description="Cluster protein sequences by identity with MMseqs2 (easy-cluster), "
    "submitted as a SLURM job. Use the local block for small sets.",
    initialAction=initial_mmseqs_slurm,
    finalAction=final_mmseqs_slurm,
    inputs=[sequencesFile],
    variables=BSC_JOB_VARIABLES
    + [
        folderNameVariable,
        minSeqIdVariable,
        coverageVariable,
        covModeVariable,
        clusterModulesVariable,
        preambleVariable,
        mpiRunnerVariable,
        mmseqsCommandVariable,
        removeExistingResultsVariable,
    ],
    outputs=[clustersFile, representativesFile, resultsFolder],
)
