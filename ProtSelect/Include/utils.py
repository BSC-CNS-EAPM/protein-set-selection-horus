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
    localGPU=None,
    time=None,
    group_jobs_by=None,
):
    """
    Write the job scripts for the selected Horus remote.

    Parameters
    ==========
    localGPU : dict, optional
        ``{"gpus": int, "parallel": int}``. When given and running locally, the
        jobs are spread over the machine's GPUs instead of being run as plain
        parallel CPU jobs. The commands must contain the ``GPUID`` placeholder,
        which ``bsc_calculations`` substitutes with the GPU index.

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
        # Both are no-ops when unset: bsc_calculations keeps its 48h default and
        # one array task per job.
        if time:
            mn5_arguments["time"] = time
        if group_jobs_by:
            mn5_arguments["group_jobs_by"] = group_jobs_by
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
        if localGPU:
            local_gpus = int(localGPU.get("gpus", 1) or 1)
            local_parallel = int(localGPU.get("parallel", 1) or 1)
            print(f"Generating local GPU jobs on {local_gpus} GPU(s), "
                  f"{local_parallel} job(s) in parallel per GPU...")
            bsc_calculations.local.multipleGPUSimulations(
                jobs,
                gpus=local_gpus,
                parallel=local_parallel,
                script_name=scriptName,
            )
        else:
            print("Generating local jobs...")
            # Unlike mn5.jobArrays and multipleGPUSimulations, local.parallel
            # writes each job verbatim: without a trailing newline, two jobs
            # sharing a script run together as one command line.
            bsc_calculations.local.parallel(
                [job if job.endswith("\n") else job + "\n" for job in jobs],
                cpus=min(cpus or 40, len(jobs)),
                script_name=scriptName,
            )
    else:
        raise Exception(
            f"The remote '{cluster}' is not supported by this plugin. Use a "
            "MareNostrum 5 login node (glogin*/alogin*) or the local machine."
        )

    return cluster


def strip_srun(jobs):
    """
    Remove the ``srun`` launcher from job commands so they can run locally.

    ``prepare_proteins`` prefixes its commands with ``srun`` unconditionally,
    including the MPI task count. ``srun`` is the SLURM launcher and does not
    exist off a cluster, so a local run would fail with "srun: not found" -- and
    because the generated scripts end with a ``cd`` that succeeds, that failure
    is invisible unless the sub-scripts run under ``sh -e``.

    Only the launcher is dropped; the command it was wrapping is untouched.
    """
    import re

    return [
        re.sub(r"(?<![\w./-])srun(?:\s+-n\s*\d+)?\s+", "", job)
        for job in jobs
    ]


def removal_requested(block, remove_existing, folder_name) -> bool:
    """
    Whether 'Remove existing results' should delete the block's folder now.

    Only when the user started the run from this very block. Horus reruns every
    block downstream of the one started, so an option left on would otherwise
    delete hours of cluster results -- and resubmit them -- whenever anything
    upstream is touched. Horus records the starting block in
    ``flow.runStartedFrom``; on a Horus that does not, the start is unknown and
    the results are kept, since a skipped deletion costs nothing and a wrong
    one costs the whole calculation.
    """
    if not remove_existing or not os.path.exists(folder_name):
        return False

    flow = getattr(block, "flow", None)
    started_from = getattr(flow, "runStartedFrom", None)
    # Compared as text: the placedID may reach the flow from the frontend as a string.
    if started_from is not None and str(started_from) == str(getattr(block, "_placedID", "")):
        print(f"Removing the existing '{folder_name}' ('Remove existing results' is on).")
        return True

    if started_from is None:
        advice = ("the run's starting block is unknown (an older Horus, or a resumed "
                  f"run). Delete '{folder_name}' by hand to start over.")
    else:
        advice = ("the run was started from another block and only reached this one. "
                  "Run this block itself to remove it.")
    print(f"Keeping the existing '{folder_name}' although 'Remove existing results' "
          f"is on: {advice}")
    return False


def _hook_script(scriptName: str) -> str:
    """
    Build the driver that runs the local sub-scripts and waits for them.

    Both ``bsc_calculations`` local backends write one sub-script per slot,
    named ``<scriptName>_<index>`` zero-filled to the width of the highest
    index, plus a driver that backgrounds them with ``nohup`` and does not wait.
    ``local.parallel`` zero-fills by the CPU count and
    ``local.multipleGPUSimulations`` by ``gpus * parallel``.

    Neither generated driver is usable here, and neither was the hook the EAPM
    plugin replaced them with. Its shortcomings, all of which are silent -- they
    change the block's success verdict, not its output:

    * ``for script in <name>_?`` matches exactly one character, so it picks the
      sub-scripts up at up to 10 slots and matches *nothing* above that, where
      the names gain a second digit. The block then reports success having run
      no jobs at all.
    * ``exit_code=$?`` is read immediately after ``&``, so it captures whether
      backgrounding succeeded, never the job's own status: a job exiting 3 was
      reported as success.
    * Failure was instead inferred from a non-empty ``.err`` file, so any tool
      that writes a warning to stderr was reported as failed.
    * ``${{script%.*}}`` strips at the dot in ``calculation_script.sh_0``,
      yielding ``calculation_script`` for *every* sub-script, so they all wrote
      over one another's logs.

    This version launches every sub-script, gives each its own logs, remembers
    the PIDs and waits on each, so the exit status is the real one.

    The sub-scripts are run with ``sh -e``. Without it a failure goes unnoticed:
    the generated scripts have the shape ``cd <dir>; <tool> ...; cd ../../..``,
    so the exit status is that of the trailing ``cd``, which always succeeds. A
    missing executable would otherwise be reported as a successful run that
    happened to produce no output.
    """
    return f"""
# Run each sub-script in the background and wait for all of them.
pids=""
for script in {scriptName}_*; do
    # Skip the log files the sub-scripts produce, and any glob that matched nothing.
    case "$script" in
        *.out|*.err|*.nohup) continue ;;
    esac
    [ -f "$script" ] || continue

    sh -e "$script" > "$script.out" 2> "$script.err" &
    pids="$pids $!"
done

if [ -z "$pids" ]; then
    echo "Error: no sub-scripts matching '{scriptName}_*' were found." >&2
    exit 1
fi

status=0
for pid in $pids; do
    if ! wait "$pid"; then
        status=1
    fi
done

if [ $status -ne 0 ]; then
    echo "Error: at least one job failed. See the .err files next to the sub-scripts." >&2
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
    localGPU: typing.Optional[dict] = None,
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
        localGPU: ``{"gpus": int, "parallel": int}`` to spread the jobs over
            local GPUs instead of running them as parallel CPU jobs. Only
            meaningful when the block runs on the local remote, and the jobs
            must carry the ``GPUID`` placeholder.
    """
    if jobs is None:
        raise Exception("No jobs selected")

    partition = block.variables.get("partition")
    cpus = block.variables.get("cpus")
    cpus_per_task = block.variables.get("cpus_per_task")
    # Only the blocks that expose the GPUs variable request them; the rest keep
    # the cluster defaults.
    gpus = block.variables.get("gpus")
    walltime = block.variables.get("time") or None
    groupJobsBy = block.variables.get("group_jobs_by") or None
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
        localGPU,
        walltime,
        groupJobsBy,
    )

    # Rewrite the main script to add the environment variables and to wait for
    # the background jobs to finish. Both bsc_calculations local backends write
    # a driver that backgrounds its sub-scripts without waiting, so without this
    # the block would report success the moment the jobs were launched.
    if cluster == "local":
        body = _hook_script(scriptName)
        with open(scriptName, "w") as f:
            f.write("#!/bin/sh\n")

            for key, value in environmentListValues.items():
                f.write(f"export {key}={value}\n")

            f.write(body)

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
    description="Name of the generated job script. Change it only to run two "
    "calculations of the same block in one folder.",
    type=VariableTypes.STRING,
    defaultValue="calculation_script.sh",
    category="Slurm configuration",
)

partitionVariable = PluginVariable(
    name="Partition",
    id="partition",
    description="SLURM queue (QOS) to submit to. On MareNostrum 5, gp_* queues are "
    "the general-purpose CPU partition and acc_* the GPU partition; *_debug queues "
    "start fast but are limited to short runs.",
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
    description="CPUs given to each task (OpenMP/threads). Most blocks use one; "
    "MMseqs2 uses it as its thread count.",
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

timeVariable = PluginVariable(
    name="Walltime (hours)",
    id="time",
    description="Wall clock limit in hours. bsc_calculations clamps this to the "
    "QOS cap (2h on the *_debug queues), and a request far above what a job needs "
    "only makes it queue longer. 0 leaves the bsc_calculations default of 48h.",
    type=VariableTypes.INTEGER,
    defaultValue=0,
    category="Slurm configuration",
)

groupJobsByVariable = PluginVariable(
    name="Group jobs per array task",
    id="group_jobs_by",
    description="Bundle this many jobs into each array task, run one after another. "
    "One array task per job is right for long jobs, but for jobs of a few minutes "
    "the queue wait dominates: ten one-minute jobs each wait separately. Setting "
    "this to the number of jobs runs them all in a single task. 0 keeps one task "
    "per job.",
    type=VariableTypes.INTEGER,
    defaultValue=0,
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
    cpusPerTaskVariable,
    timeVariable,
    groupJobsByVariable,
    environmentList,
    removeFolderOnFinishVariable,
]
