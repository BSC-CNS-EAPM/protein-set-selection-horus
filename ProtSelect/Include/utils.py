"""
Job submission helpers shared by the compute blocks.

The blocks that do real work (ProteinMPNN, Rosetta Relax, BioEmu) are
``SlurmBlock``s: an initial action generates a list of shell commands with
``prepare_proteins``/``bioprospecting``, hands them to ``bsc_calculations`` to
be written out as scripts, uploads them and submits the job; a final action
downloads the results once the job finishes.

This module is trimmed from the EAPM plugin's ``utils.py`` to the two targets
this plugin supports: MareNostrum 5 (``glogin*``/``alogin*``) and the local
machine. The PELE special case and the minotauro, nord3, cte-amd and
"powerpuff" branches were dropped along with the blocks that used them.
"""

import datetime
import os
import shutil
import subprocess
import typing

from HorusAPI import PluginVariable, SlurmBlock, VariableList, VariableTypes


def setup_bsc_calculations_based_on_horus_remote(
    remote_name,
    remote_host: str,
    jobs,
    partition,
    scriptName,
    cpus,
    job_name,
    program,
    modulePurge,
    cpus_per_task,
    gpus=None,
    conda_env=None,
    modules=None,
    exports=None,
):
    """
    Write the job scripts for the selected Horus remote.

    Returns the resolved cluster name ("local" or the remote host), which the
    caller uses to decide between submitting a job and running in place.
    """
    import bsc_calculations

    cluster = "local"

    if remote_name != "local":
        cluster = remote_host

    # marenostrum
    if "glogin" in cluster or "alogin" in cluster:
        print("Generating Marenostrum jobs...")
        mn5_arguments = {}
        if gpus is not None:
            mn5_arguments["gpus"] = gpus
        # A 'program' shortcut overwrites the environment it knows about, so these
        # are only honoured when the caller drops the program name.
        if conda_env:
            mn5_arguments["conda_env"] = conda_env
        if modules:
            mn5_arguments["modules"] = modules
        if exports:
            mn5_arguments["exports"] = exports
        bsc_calculations.mn5.jobArrays(
            jobs,
            job_name=job_name,
            partition=partition,
            program=program,
            script_name=scriptName,
            ntasks=cpus,
            cpus_per_task=cpus_per_task,
            module_purge=modulePurge,
            **mn5_arguments,
        )
    # local
    elif cluster == "local":
        print("Generating local jobs...")
        bsc_calculations.local.parallel(
            jobs,
            cpus=min(cpus or 40, len(jobs)),
            script_name=scriptName,
        )
    else:
        raise Exception(
            f"The remote '{cluster}' is not supported by this plugin. Use a "
            "MareNostrum 5 login node (glogin*/alogin*) or the local machine."
        )

    return cluster


HOOK_SCRIPT = """
for script in calculation_script.sh_?; do
    sh "$script" > "${script%.*}.out" 2> "${script%.*}.err" &
    exit_code=$?
done

# Wait for all background processes to finish
wait

if [ $exit_code -ne 0 ]; then
    echo "Error: Script $script failed with exit code $exit_code" >&2
    exit 1
fi

# Check if the .err file is empty in order to determine
# if the script ran successfully
if [ -s "${script%.*}.err" ]; then
    echo "Error: Script $script failed with errors:" >&2
    cat "${script%.*}.err" >&2
    exit 1
fi


echo "All scripts completed successfully."

"""


def launchCalculationAction(
    block: SlurmBlock,
    jobs: typing.List[str],
    program: str,
    uploadFolders: typing.Optional[typing.List[str]] = None,
    modulePurge: typing.Optional[bool] = False,
    condaEnv: typing.Optional[str] = None,
    modules: typing.Optional[typing.List[str]] = None,
    exports: typing.Optional[typing.List[str]] = None,
):
    """
    Initial action of a compute block: write, upload and submit the jobs.

    Args:
        block: The block to run the action on.
        jobs: Shell commands to run, one per model.
        program: A ``bsc_calculations`` program shortcut that selects a known
            environment on the cluster, or None to supply ``condaEnv``,
            ``modules`` and ``exports`` explicitly.
        uploadFolders: Folders to upload instead of the whole working
            directory. Uploading everything is the default but is slow once a
            flow has accumulated results.
    """
    if jobs is None:
        raise Exception("No jobs selected")

    partition = block.variables.get("partition")
    cpus = block.variables.get("cpus")
    cpus_per_task = block.variables.get("cpus_per_task")
    # Only the blocks that expose the GPUs variable request them; the rest keep
    # the cluster defaults.
    gpus = block.variables.get("gpus")
    simulationName = block.variables.get("folder_name")
    scriptName = block.variables.get("script_name", "calculation_script.sh")

    if simulationName is None:
        simulationName = block.flow.name.lower().replace(" ", "_")

    block.extraData["simulationName"] = simulationName

    print(f"Launching BSC calculation with {cpus} CPUs")
    if gpus is not None:
        print(f"Requesting {gpus} GPU(s) and {cpus_per_task} CPUs per task")

    # The local remote has no host, so only ask for it on real remotes
    remoteHost = "localhost" if block.remote.isLocal else block.remote.host

    # Read the environment variables
    environmentValues = block.variables.get("environment_list", [])
    environmentListValues = {}
    if environmentValues is not None:
        for env in environmentValues:
            environmentListValues[env["environment_key"]] = env["environment_value"]

    # The environment variables are written into the script by hand for the local
    # runs below; on a cluster they have to travel as exports of the job.
    jobExports = list(exports or [])
    jobExports += [f"{key}={value}" for key, value in environmentListValues.items()]

    cluster = setup_bsc_calculations_based_on_horus_remote(
        block.remote.name.lower(),
        remoteHost,
        jobs,
        partition,
        scriptName,
        cpus,
        simulationName,
        program,
        modulePurge,
        cpus_per_task,
        gpus,
        condaEnv,
        modules,
        jobExports,
    )

    # Rewrite the main script to add the environment variables and to wait for
    # the background jobs to finish. bsc_calculations.local.parallel writes a
    # driver that backgrounds its sub-scripts without waiting, so without this
    # the block would report success the moment the jobs were launched.
    if cluster == "local":
        with open(scriptName, "w") as f:
            f.write("#!/bin/sh\n")

            for key, value in environmentListValues.items():
                f.write(f"export {key}={value}\n")

            f.write(HOOK_SCRIPT)

    if cluster != "local":
        savedID_and_date = block.flow.savedID + "_" + str(datetime.datetime.now().timestamp())
        simRemoteDir = os.path.join(block.remote.workDir, savedID_and_date)
        block.extraData["remoteDir"] = simRemoteDir
        block.remote.command(f"mkdir -p -v {simRemoteDir}")

        print(f"Created simulation folder in the remote at {simRemoteDir}")
        print("Sending data to the remote...")

        # Upload only the folders the caller asked for, or the whole working
        # directory when it did not say.
        if uploadFolders is not None:
            for file in uploadFolders:
                block.remote.sendData(file, simRemoteDir)
            block.extraData["uploadedFolder"] = False
        else:
            simRemoteDir = block.remote.sendData(os.getcwd(), simRemoteDir)
            block.extraData["uploadedFolder"] = True

        block.extraData["remoteContainer"] = simRemoteDir

        # Upload the commands
        for file in os.listdir("."):
            if file.startswith(scriptName):
                block.remote.sendData(file, simRemoteDir)

        # Upload the script
        scriptPath = block.remote.sendData(scriptName, simRemoteDir)

        print("Data sent to the remote.")
        print("Running the simulation...")

        print(f"Submitting the job to the remote... {scriptPath}")
        jobID = block.remote.submitJob(scriptPath)
        print(f"Simulation running with job ID {jobID}. Waiting for it to finish...")

    # * Local
    else:
        print("Running the simulation locally...")

        oldEnv = os.environ.copy()

        for key, value in environmentListValues.items():
            os.environ[key] = value

        # Run the simulation
        try:
            with subprocess.Popen(
                ["sh", scriptName],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ) as p:
                print(f"Simulation running with PID {p.pid}. Waiting for it to finish...")

                if p.stdout is None:
                    raise Exception("No stdout produced by the process")

                for line in p.stdout:
                    strippedOut = line.decode("utf-8").strip()
                    if strippedOut != "":
                        print(strippedOut)

                # Print the error
                strippedErr = ""
                if p.stderr:
                    for line in p.stderr:
                        strippedErr = line.decode("utf-8").strip()
                        if strippedErr != "":
                            print(strippedErr)

                # Wait for the process to finish
                p.wait()

                if p.returncode != 0:
                    raise Exception(strippedErr)
        finally:
            os.environ = oldEnv


def downloadResultsAction(block: SlurmBlock):
    """
    Final action of a compute block. It downloads the results from the remote.

    Args:
        block (SlurmBlock): The block to run the action on.
    """

    if block.remote.name != "Local":
        cluster = block.remote.host
    else:
        cluster = "local"

    if cluster != "local":
        simRemoteDir = block.extraData["remoteDir"]

        print("Calculation finished, downloading results...")

        currentFolder = os.getcwd()
        folderDestinationOverride = os.path.join(currentFolder, "tmp_download")

        if os.path.exists(folderDestinationOverride):
            shutil.rmtree(folderDestinationOverride)

        # Create the folder
        os.makedirs(folderDestinationOverride)

        final_path = block.remote.getData(simRemoteDir, folderDestinationOverride)

        # If we sent the whole folder, the results are in a subfolder
        # Move them to the parent folder
        if block.extraData.get("uploadedFolder", False):
            print("Uploaded folder, moving results to parent folder")
            final_path = os.path.join(final_path, os.path.basename(currentFolder))

        # Move the contents of the downloaded folder to its parent
        # This is done because the folder is downloaded as a subfolder
        for file in os.listdir(final_path):
            current_path = os.path.join(final_path, file)
            new_path = os.path.join(currentFolder, file)

            if os.path.exists(new_path):
                if os.path.isdir(new_path):
                    shutil.rmtree(new_path)
                else:
                    os.remove(new_path)

            shutil.move(current_path, new_path)

        # Remove the downloaded folder
        shutil.rmtree(folderDestinationOverride)

        final_path = currentFolder

        print(f"Results downloaded to {final_path}")

        remoteContainer = block.extraData["remoteContainer"]

        remove_remote_folder_on_finish = block.variables.get("remove_folder_on_finish", True)
        # Remove the remote folder
        if remove_remote_folder_on_finish:
            print(f"Removing remote folder {remoteContainer}")
            block.remote.command(f"rm -rf {remoteContainer}")
    else:
        final_path = os.path.join(os.getcwd())
        print("Calculation finished, results are in the folder: ", final_path)

    return final_path


# ==========================#
# Shared SLURM variables
# ==========================#
scriptNameVariable = PluginVariable(
    name="Script name",
    id="script_name",
    description="Name of the script.",
    type=VariableTypes.STRING,
    defaultValue="calculation_script.sh",
    category="Slurm configuration",
)

partitionVariable = PluginVariable(
    name="Partition",
    id="partition",
    description="Partition where to lunch.",
    type=VariableTypes.STRING_LIST,
    defaultValue="gp_bscls",
    allowedValues=["gp_bscls", "gp_debug", "acc_bscls", "acc_debug", "debug", "bsc_ls"],
    category="Slurm configuration",
)

cpusVariable = PluginVariable(
    name="CPUs",
    id="cpus",
    description="Number of CPUs to use. On a cluster this sets the job's tasks/CPUs; "
    "running locally it sets how many jobs run in parallel (capped by the number "
    "of jobs).",
    type=VariableTypes.INTEGER,
    defaultValue=1,
    category="Slurm configuration",
)

cpusPerTaskVariable = PluginVariable(
    name="CPUs per task",
    id="cpus_per_task",
    description="Number of CPUs per task to use.",
    type=VariableTypes.INTEGER,
    defaultValue=1,
    category="Slurm configuration",
)

gpusVariable = PluginVariable(
    name="GPUs",
    id="gpus",
    description="Number of GPUs to request per job (--gres gpu:N). Only honoured on "
    "GPU partitions (the 'acc_*' queues on MareNostrum); set the CPUs per task "
    "variable to choose how many CPUs go with them.",
    type=VariableTypes.INTEGER,
    defaultValue=1,
    category="Slurm configuration",
)

removeFolderOnFinishVariable = PluginVariable(
    name="Remove remote folder on finish",
    id="remove_folder_on_finish",
    description="Deletes the calculation folder on the remote on finish.",
    type=VariableTypes.BOOLEAN,
    defaultValue=True,
    category="Remote",
)

# Advanced variables
environmentKeyVariable = PluginVariable(
    name="Environment",
    id="environment_key",
    description="Environment key",
    type=VariableTypes.STRING,
    category="Environment",
)

environmentValueVariable = PluginVariable(
    name="Value",
    id="environment_value",
    description="Environment value",
    type=VariableTypes.STRING,
    category="Environment",
)

environmentList = VariableList(
    id="environment_list",
    name="Environment variables",
    description="Environment variables to set during the remote connection.",
    prototypes=[environmentKeyVariable, environmentValueVariable],
    category="Environment",
)

BSC_JOB_VARIABLES = [
    scriptNameVariable,
    partitionVariable,
    cpusVariable,
    environmentList,
    removeFolderOnFinishVariable,
    cpusPerTaskVariable,
]
