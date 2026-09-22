Remotes and clusters
====================

In Horus every block runs on a **remote**: the **Local** remote (the machine
running Horus) or an SSH connection to another machine, typically a SLURM
cluster login node. You choose the remote per block, in the drop-down at the
bottom of the block.

Which blocks can run where
--------------------------

.. list-table::
   :header-rows: 1
   :widths: 3 2 5

   * - Block
     - Runs on
     - Recommended
   * - ProteinMPNN Scoring
     - Local or cluster
     - GPU cluster remote. Locally it runs on CPU or local GPUs; fine for a few
       small proteins.
   * - MMseqs2 Clustering
     - Local or cluster
     - Local for up to a few thousand sequences; CPU cluster remote for large
       families.
   * - Rosetta Relax
     - Local or cluster
     - CPU cluster remote. A relax of 100 structures per model is hours of CPU
       per model.
   * - BioEmu Sampling
     - Local or cluster
     - GPU cluster remote.
   * - Every other block
     - Local
     - These read and write small files and run on the machine running Horus.

Most of these other blocks stop with an error if a cluster remote is selected.

Creating a remote
-----------------

Open **Remotes** in the Horus toolbar and create a **New remote**:

.. list-table::
   :header-rows: 1
   :widths: 2 5

   * - Field
     - What to enter
   * - Name
     - Any name. You pick it in the block's drop-down.
   * - Host
     - The login node, e.g. ``glogin2.bsc.es``.
   * - Username, Port
     - Your cluster account and the SSH port (22).
   * - Password or Key file
     - One of the two. A key file is recommended.
   * - ProxyCommand
     - Only if you reach the cluster through a jump host.
   * - Working directory
     - A folder on the cluster where Horus creates one sub-folder per job, e.g.
       ``/gpfs/projects/<group>/<user>/horus_work``. Put it on a file system
       with space for BioEmu and Rosetta output.
   * - Load profile
     - Source your shell profile before each command. Enable it if you need
       your ``.bashrc`` environment.

MareNostrum 5: one remote for GPU, one for CPU
----------------------------------------------

On MareNostrum 5, create **two remotes**:

.. list-table::
   :header-rows: 1

   * - Remote name (suggestion)
     - Host
     - Use for
   * - ``acc``
     - ``alogin2.bsc.es`` (or another ``alogin`` node)
     - ProteinMPNN Scoring, BioEmu Sampling (GPU, ``acc_*`` partitions)
   * - ``mn``
     - ``glogin2.bsc.es`` (or another ``glogin`` node)
     - MMseqs2 Clustering, Rosetta Relax (CPU, ``gp_*`` partitions)

A job submitted with ``sbatch`` inherits the module environment of the login
node it was submitted from. GPU software is in the ACC login nodes' module tree
and Rosetta in the general-purpose one, so a single remote would fail for one of
the two partitions.

Use the same working directory for both remotes if you like; each job gets its
own folder.

Assigning remotes in the preset
-------------------------------

The **ProteSel Pipeline** preset opens with every block on **Local**, because
remote names differ between installations. Before running it on a cluster,
change the remote of these four blocks:

- **ProteinMPNN Scoring**: your GPU remote (``acc``);
- **BioEmu Sampling**: your GPU remote (``acc``);
- **MMseqs2 Clustering**: your CPU remote (``mn``), or leave it Local for small
  sets;
- **Rosetta Relax**: your CPU remote (``mn``).

Leave all the other blocks on Local.

Sizing the cluster jobs
-----------------------

The four cluster-capable blocks share a set of job settings, under *Slurm
configuration* (full list: :doc:`reference/cluster_job_settings`). The ones that
matter most:

.. list-table::
   :header-rows: 1
   :widths: 2 6

   * - Setting
     - How to choose it
   * - Partition
     - ``acc_*`` for GPU blocks, ``gp_*`` for CPU blocks. ``*_debug`` queues
       start fast but only allow short runs; use them to test a flow.
   * - Walltime (``time``, hours)
     - Leave it at 0 for the 48 h default, or set it close to the real run time:
       shorter jobs usually wait less in the queue. The plugin cannot extend a
       job that runs out of time, but you can rerun the block and it resumes (see
       :ref:`workflow:Rerunning and resuming`).
   * - Group jobs per array task (``group_jobs_by``)
     - The block writes one job per model, submitted as a SLURM array. 0 gives
       one array task per job, which is right for long jobs. For short jobs
       (ProteinMPNN takes minutes per model) the queue wait dominates, so group
       them, e.g. 1000 to run everything in one task.
   * - CPUs, CPUs per task
     - See the per-block advice below.
   * - Remove folder on finish
     - Deletes the job folder on the cluster once the results are downloaded.
       Disable it to keep a cluster-side copy.

Per-block advice
~~~~~~~~~~~~~~~~

**ProteinMPNN Scoring.** GPU partition, **GPUs** 1, jobs grouped into one task,
walltime of an hour or two. The job activates **Cluster environment**, a conda
environment with torch, after loading **Cluster modules**.

**MMseqs2 Clustering.** CPU partition. **CPUs per task** is MMseqs2's thread
count. MareNostrum's module (``mmseqs2/15-6f452``) is an MPI build: keep **MPI
runner** at ``srun`` there. Clear it for a non-MPI build. Locally, MMseqs2 uses
every core.

**Rosetta Relax.** The block runs ``rosetta_scripts`` with MPI: one rank
coordinates and each other rank relaxes one structure at a time. Set **CPUs**
to ``nstruct + 1``, for example 101 for nstruct 100, and keep
``group_jobs_by`` at 0 so each model gets its own array task and all models run
in parallel. A single structure cannot use more than one CPU, so adding CPUs
beyond ``nstruct + 1`` does not help. Grouping models in one task makes them run
one after another. Rosetta itself comes from the ``rosetta`` module that
bsc_calculations loads (``gcc/12.3.0``, ``rosetta/3.14`` on MareNostrum 5), so
it must run on a general-purpose login node.

**BioEmu Sampling.** GPU partition, **GPUs** 1. The job activates **Cluster
BioEmu environment**. On clusters whose compute nodes have no internet access
(MareNostrum), enable **MSA calculation**, which builds the MSA with
``colabfold_search`` against a local database. Otherwise BioEmu tries to reach
the ColabFold web server and fails. **Persistent MSA folder** keeps the MSAs
between runs.
