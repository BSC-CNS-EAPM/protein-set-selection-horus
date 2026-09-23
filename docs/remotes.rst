Remotes and clusters
====================

In Horus every block runs on a **remote**: the **Local** remote (the machine
running Horus) or an SSH connection to another machine, typically a SLURM
cluster login node. You choose the remote per block, in the drop-down at the
bottom of the block.

.. important::

   Cluster jobs are written by ``bsc_calculations``, which this plugin drives
   for **MareNostrum 5 login nodes** (hosts containing ``glogin`` or
   ``alogin``). A cluster remote whose host is neither is refused with a clear
   error, and everything else runs on the Local remote. Several block defaults
   (module names, environment paths) also point at that installation; change
   them for your own site. Support for other SLURM clusters means extending
   ``ProtSelect/Include/utils.py``.

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
     - A GPU remote. Locally it runs on CPU or local GPUs; fine for a few small
       proteins.
   * - MMseqs2 Clustering
     - Local or cluster
     - Local for up to a few thousand sequences; a CPU remote for large
       families.
   * - Rosetta Relax
     - Local or cluster
     - A CPU remote. A relax of 100 structures per model is hours of CPU per
       model.
   * - BioEmu Sampling
     - Local or cluster
     - A GPU remote.
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
     - The cluster login node.
   * - Username, Port
     - Your cluster account and the SSH port (22).
   * - Password or Key file
     - One of the two. A key file is recommended.
   * - ProxyCommand
     - Only if you reach the cluster through a jump host.
   * - Working directory
     - A folder on the cluster where Horus creates one sub-folder per job. Put
       it on a file system with space for BioEmu and Rosetta output.
   * - Load profile
     - Source your shell profile before each command. Enable it if you need
       your ``.bashrc`` environment.

One remote for GPU, one for CPU
-------------------------------

A job submitted with ``sbatch`` inherits the environment of the login node it
was submitted from, including which modules it can load. On a cluster whose GPU
and CPU partitions are served by different login nodes with different module
trees, one remote cannot reach both: the GPU software is visible from one and
Rosetta from the other.

Create **two remotes** on such a cluster, and give each block the one that can
see the software it needs:

.. list-table::
   :header-rows: 1

   * - Remote
     - Host
     - Use for
   * - a GPU remote
     - the login node serving the GPU partitions
     - ProteinMPNN Scoring, BioEmu Sampling
   * - a CPU remote
     - the login node serving the general-purpose partitions
     - MMseqs2 Clustering, Rosetta Relax

On MareNostrum 5 those are the ``alogin`` and ``glogin`` nodes; the plugin was
tested with one remote for each. Where a single login node serves everything,
one remote is enough.

The two remotes can share a working directory; each job gets its own folder.

Assigning remotes in the preset
-------------------------------

The **ProteSel Pipeline** preset opens with every block on **Local**, because
remote names differ between installations. Before running it on a cluster,
change the remote of these four blocks:

- **ProteinMPNN Scoring**: your GPU remote;
- **BioEmu Sampling**: your GPU remote;
- **MMseqs2 Clustering**: your CPU remote, or leave it Local for small sets;
- **Rosetta Relax**: your CPU remote.

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
     - The queue (QOS) to submit to: a GPU queue for the GPU blocks, a
       general-purpose one for the others. Debug queues start fast but only
       allow short runs; use them to test a flow. The choices listed are
       MareNostrum 5's.
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

Software on the cluster
~~~~~~~~~~~~~~~~~~~~~~~

The plugin's local tool configuration (:doc:`configuration`) does not apply to
cluster jobs: there the job loads its own software. Each cluster-capable block
has parameters for that, and their defaults are the ones used during
development, so check them against your site:

- **Cluster modules**: modules loaded before the job runs;
- **Cluster environment** (ProteinMPNN, BioEmu): the conda environment the job
  activates, as a path or a name;
- **Preamble** (MMseqs2): free-text lines for anything a module does not cover.

Rosetta Relax is the exception: ``bsc_calculations`` loads its own Rosetta
module for that job, so the module must exist on the cluster you submit from.

Per-block advice
~~~~~~~~~~~~~~~~

**ProteinMPNN Scoring.** GPU queue, **GPUs** 1, jobs grouped into one task,
walltime of an hour or two. The job activates **Cluster environment**, which
must have torch.

**MMseqs2 Clustering.** CPU queue. **CPUs per task** is MMseqs2's thread count.
An MPI build of MMseqs2 must be started through a launcher: keep **MPI runner**
at ``srun``, which MMseqs2 uses for its MPI-parallel steps. Clear it for a
non-MPI build, where it would run a full copy of each step per task. Locally,
MMseqs2 uses every core.

**Rosetta Relax.** The block runs ``rosetta_scripts`` with MPI: one rank
coordinates and each other rank relaxes one structure at a time. Set **CPUs**
to ``nstruct + 1``, for example 101 for nstruct 100, and keep
``group_jobs_by`` at 0 so each model gets its own array task and all models run
in parallel. A single structure cannot use more than one CPU, so adding CPUs
beyond ``nstruct + 1`` does not help, and grouping models in one task makes them
run one after another.

**BioEmu Sampling.** GPU queue, **GPUs** 1. The job activates **Cluster BioEmu
environment**. On clusters whose compute nodes have no internet access, enable
**MSA calculation**, which builds the MSA with ``colabfold_search`` against a
local database; set **ColabFold bin folder**, **ColabFold database** and the
MMseqs2 path for your site. Otherwise BioEmu tries to reach the ColabFold web
server and fails. **Persistent MSA folder** keeps the MSAs between runs.
