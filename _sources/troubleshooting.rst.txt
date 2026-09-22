Troubleshooting
===============

The job finished on the cluster but the block says it failed
------------------------------------------------------------

If the job's output on the cluster is complete (check with ``sacct`` or the job
folder), use the block's **Continue** action. It downloads the results and runs
the rest of the flow. **Run** would submit the job again.

Older Horus versions reported finished **job arrays** as failed (status
UNKNOWN) when they checked them after the job had left the SLURM queue, for
example after reopening a paused flow. Continue recovers from that too.

A cluster job ran out of time
-----------------------------

Rerun the block with **Skip finished** on. Only the models without results are
submitted. For Rosetta, give each model its own array task
(``group_jobs_by`` 0) and **CPUs** = ``nstruct + 1``: grouped models run one
after another, which is the usual reason a relax runs out of time. See
:doc:`remotes`.

``numpy._core._multiarray_umath`` / numpy fails to import
---------------------------------------------------------

A tool running in another Python environment picked up Horus's own Python
packages. The plugin removes Horus's ``PYTHONPATH`` for PyRosetta,
CodonTransformer, BioEmu and ProteinMPNN. If you see this, update the plugin.
If it persists, report which block raised it.

"PyRosetta was not found in your Python environment"
----------------------------------------------------

Analyse Rosetta Relax could not extract the scores of some model and fell back
to PyRosetta inside Horus, which does not have it. Check that ``pyrosetta_python``
points at a Python with PyRosetta, and look above this message in the block log
for the first failing extraction job.

"mmseqs: not found" or MMseqs2 fails on the cluster
---------------------------------------------------

- **Locally:** set the ``mmseqs_path`` configuration (see :doc:`configuration`).
- **On MareNostrum:** keep **Cluster modules** at ``bsc/1.0, mmseqs2/15-6f452``
  and **MPI runner** at ``srun``. Without ``srun`` the MPI build aborts with
  ``PMI2_Job_GetId``.

Rosetta cannot find its module / BioEmu cannot find the GPU environment
-----------------------------------------------------------------------

The job was submitted from the wrong kind of login node. On MareNostrum 5, GPU
software (BioEmu, ProteinMPNN) needs an ``alogin`` remote and Rosetta a
``glogin`` remote. See :doc:`remotes`.

"The folder ... holds a clustering of different sequences / other settings"
---------------------------------------------------------------------------

MMseqs2 Clustering refuses to reuse a clustering made with other input. Change
**Output folder name**, or run the block itself with **Remove existing results**
on.

A block shows as a ghost / missing block
----------------------------------------

The flow uses a block that this version of the plugin does not have. The local
MMseqs2 Clustering block (``mmseqs2_cluster``) was merged into the SLURM one;
replace it with **MMseqs2 Clustering**, which runs locally or on a cluster.

No dGf column in the BioEmu metrics
-----------------------------------

Every BioEmu sample was folded (Q above ``q_threshold``), so the folding free
energy cannot be computed. Expected with few samples. Use more samples (the
default 10,000) to get unfolded frames.

Pareto Selection drops models
-----------------------------

A model needs a value for every objective. Models sampled by BioEmu but not
relaxed (or the reverse) have no ``score_per_residue`` (or no ``Q_Average``)
and are dropped, with a warning. Feed BioEmu the selected sequences so both
branches see the same models.

A value typed into a block was not saved
----------------------------------------

Number fields commit their value when they lose focus. Press Enter or click
elsewhere before saving the flow, or before running a block.
