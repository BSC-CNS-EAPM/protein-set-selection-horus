"""
Module containing the Rosetta relax block.

Reproduces the relax setup and submission of the reference workflow::

    jobs = selected_models.setUpRosettaOptimization('relax_selected_models',
                                                    nstruct=100,
                                                    cst_optimization=False,
                                                    skip_finished=True)
    bsc_calculations.mn5.jobArrays(jobs, job_name='selected_models_relax',
                                   program='rosetta', ...)

The jobs are built with ``prepare_proteins`` and handed to the shared BSC
launcher, so the block runs on MareNostrum / Nord3 or locally exactly like the
other BSC blocks (Alphafold, PELE).
"""

from utils import BSC_JOB_VARIABLES

from HorusAPI import PluginVariable, SlurmBlock, VariableTypes

# ==========================#
# Variable inputs
# ==========================#
modelsFolder = PluginVariable(
    name="Models folder",
    id="models_folder",
    description="Folder with the structures to relax (e.g. the 'selected_models' "
    "folder produced by 'Collect Selected Structures').",
    type=VariableTypes.FOLDER,
    defaultValue=None,
)

# ==========================#
# Variables
# ==========================#
output = PluginVariable(
    name="Relax folder",
    id="folder_name",
    description="Name of the folder where the relax calculation will be stored.",
    type=VariableTypes.STRING,
    defaultValue="relax_selected_models",
)
nstructVariable = PluginVariable(
    name="nstruct",
    id="nstruct",
    description="Number of relaxed structures generated per model.",
    type=VariableTypes.INTEGER,
    defaultValue=100,
)
relaxCyclesVariable = PluginVariable(
    name="Relax cycles",
    id="relax_cycles",
    description="Number of relax cycles.",
    type=VariableTypes.INTEGER,
    defaultValue=5,
)
cstOptimizationVariable = PluginVariable(
    name="Constraint optimization",
    id="cst_optimization",
    description="Run a constrained optimization. The notebook disables this for the "
    "the reference workflow; note the prepare_proteins default is enabled.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)
cartesianVariable = PluginVariable(
    name="Cartesian",
    id="cartesian",
    description="Run a cartesian-space relax.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)
caConstraintVariable = PluginVariable(
    name="CA constraint",
    id="ca_constraint",
    description="Apply constraints on the CA atoms.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)
skipFinishedVariable = PluginVariable(
    name="Skip finished",
    id="skip_finished",
    description="Do not regenerate jobs whose output already exists.",
    type=VariableTypes.BOOLEAN,
    defaultValue=True,
)
executableVariable = PluginVariable(
    name="Rosetta executable",
    id="executable",
    description="Rosetta scripts executable used on the cluster.",
    type=VariableTypes.STRING,
    defaultValue="rosetta_scripts.mpi.linuxgccrelease",
)
rosettaPathVariable = PluginVariable(
    name="Rosetta path",
    id="rosetta_path",
    description="Path to the Rosetta installation. Leave empty to use the cluster's "
    "module / environment default.",
    type=VariableTypes.STRING,
    defaultValue=None,
)
paramFilesVariable = PluginVariable(
    name="Param files",
    id="param_files",
    description="Optional Rosetta .params files (e.g. for ligands), comma separated.",
    # Not STRING_LIST: in Horus that is a dropdown constrained to allowedValues,
    # but these are arbitrary paths the user supplies.
    type=VariableTypes.STRING,
    defaultValue="",
)
removeExistingResults = PluginVariable(
    name="Remove existing results",
    id="remove_existing_results",
    description="Remove the relax folder if it already exists.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)

# ==========================#
# Variable outputs
# ==========================#
relaxFolderVariable = PluginVariable(
    id="relax_folder",
    name="Relax folder",
    description="Folder holding the Rosetta relax output (feed this into "
    "'Analyse Rosetta Relax').",
    type=VariableTypes.FOLDER,
)


def initial_rosetta_relax(block: SlurmBlock):
    """
    Set up the Rosetta relax jobs and send them to the remote.

    Args:
        block (SlurmBlock): The block to run the action on.
    """
    # pylint: disable=import-outside-toplevel
    import os

    import prepare_proteins
    from utils import launchCalculationAction, strip_srun

    # pylint: enable=import-outside-toplevel

    models_folder = block.inputs.get(modelsFolder.id, None)
    if not models_folder or models_folder == "None":
        raise Exception("No models folder provided.")
    if not os.path.isdir(models_folder):
        raise Exception(f"The models folder '{models_folder}' does not exist.")

    has_pdb = any(f.endswith(".pdb") for f in os.listdir(models_folder))
    if not has_pdb:
        raise Exception(f"There are no pdb files in the models folder: {models_folder}")

    folder_name = block.variables.get(output.id, "relax_selected_models")
    remove_existing = block.variables.get(removeExistingResults.id, False)

    if remove_existing and os.path.exists(folder_name):
        os.system("rm -rf " + folder_name)

    if not remove_existing and os.path.exists(folder_name):
        raise Exception(
            f"The folder {folder_name} already exists. "
            "Please, choose another name or remove it with the remove existing folder option."
        )

    block.extraData["folder_name"] = folder_name

    print("Loading models...")
    models = prepare_proteins.proteinModels(models_folder, ignore_biopython_warnings=True)

    rosetta_path = block.variables.get(rosettaPathVariable.id, None)

    # prepare_proteins wants a list; the variable is a comma-separated string so
    # the user can type arbitrary paths.
    param_files_raw = block.variables.get(paramFilesVariable.id) or ""
    if isinstance(param_files_raw, str):
        param_files = [p.strip() for p in param_files_raw.split(",") if p.strip()] or None
    else:
        param_files = list(param_files_raw) or None

    print("Setting up Rosetta relax...")
    jobs = models.setUpRosettaOptimization(
        folder_name,
        nstruct=block.variables.get(nstructVariable.id, 100),
        relax_cycles=block.variables.get(relaxCyclesVariable.id, 5),
        cst_optimization=block.variables.get(cstOptimizationVariable.id, False),
        cartesian=block.variables.get(cartesianVariable.id, False),
        ca_constraint=block.variables.get(caConstraintVariable.id, False),
        skip_finished=block.variables.get(skipFinishedVariable.id, True),
        executable=block.variables.get(executableVariable.id)
        or "rosetta_scripts.mpi.linuxgccrelease",
        rosetta_path=rosetta_path or None,
        param_files=param_files or None,
    )

    if not jobs:
        raise Exception(
            "No Rosetta jobs were generated. If 'Skip finished' is enabled the "
            "calculation may already be complete."
        )

    print(f"Generated {len(jobs)} Rosetta relax job(s).")

    if block.remote.isLocal:
        # prepare_proteins prefixes every command with srun, which only exists on
        # a SLURM cluster. Drop it so the relax can run on this machine.
        jobs = strip_srun(jobs)

    launchCalculationAction(block, jobs, "rosetta", [folder_name])


def final_rosetta_relax(block: SlurmBlock):
    """
    Download the Rosetta relax results.

    Args:
        block (SlurmBlock): The SlurmBlock object representing the current block.
    """
    # pylint: disable=import-outside-toplevel
    import os

    from utils import downloadResultsAction

    # pylint: enable=import-outside-toplevel

    downloaded_path = downloadResultsAction(block)

    results_folder = block.extraData["folder_name"]
    relax_folder = os.path.join(downloaded_path, results_folder)

    print(f"Rosetta relax finished. Results in: {relax_folder}")

    block.setOutput(relaxFolderVariable.id, relax_folder)


rosettaRelaxBlock = SlurmBlock(
    category="Rosetta",
    name="Rosetta Relax",
    id="rosetta_relax",
    description="Set up and run a Rosetta relax optimization on a folder of models "
    "(for MareNostrum, Nord3 clusters or local).",
    initialAction=initial_rosetta_relax,
    finalAction=final_rosetta_relax,
    variables=BSC_JOB_VARIABLES
    + [
        output,
        nstructVariable,
        relaxCyclesVariable,
        cstOptimizationVariable,
        cartesianVariable,
        caConstraintVariable,
        skipFinishedVariable,
        executableVariable,
        rosettaPathVariable,
        paramFilesVariable,
        removeExistingResults,
    ],
    inputs=[modelsFolder],
    outputs=[relaxFolderVariable],
)
