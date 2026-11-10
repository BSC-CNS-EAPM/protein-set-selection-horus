Troubleshooting
===============

The job finished on the cluster but the block says it failed
--------------------------------------------------------------

If the job's output on the cluster is complete (check with ``sacct`` or the job
folder), use the block's **Continue** action. It downloads the results and runs
the rest of the flow. Check the retrieved output counts and logs: Continue
does not repair incomplete calculations. **Run** prepares jobs again, subject
to **Skip finished** and existing-results settings.

Older Horus versions reported finished **job arrays** as failed (status
UNKNOWN) when they checked them after the job had left the SLURM queue, for
example after reopening a paused flow. Continue recovers from that too.

A cluster job ran out of time
-------------------------------

Check the logs for the cause, then rerun with **Skip finished** on to reuse
completed model outputs. An unfinished model may be rerun, rather than resumed
from the exact interrupted step. For Rosetta, ``group_jobs_by`` 0 gives each
model its own array task; grouped models run sequentially and must share the
walltime. Choose resources for the installed serial/MPI build and your queue
limits, as described in :doc:`remotes`. Use a fresh output folder if the inputs
or protocol changed, because completion checks do not validate all settings.

``numpy._core._multiarray_umath`` / numpy fails to import
-----------------------------------------------------------

A tool running in another Python environment picked up Horus's own Python
packages. The plugin removes Horus's ``PYTHONPATH`` for PyRosetta,
CodonTransformer, BioEmu and ProteinMPNN. If you see this, update the plugin.
If it persists, report which block raised it.

A tool is ``missing`` after upgrading the plugin
--------------------------------------------------

The installers now use one environment, ``protselect``, and no longer look in
the per-tool environments of earlier versions (``bioemu``, ``proteinmpnn`` and
so on). Run ``./install_deps.sh`` to install into ``protselect``, then save the
new paths. A saved configuration that points at an old environment keeps
working until you change it. A block placed earlier keeps the **BioEmu
environment** value it was saved with, so update that field too. See
:ref:`configuration:The protselect environment`.

A tool breaks after installing another package in ``protselect``
--------------------------------------------------------------------

All the tools share this environment, so an unconstrained ``pip install`` can
replace a version one of them needs, most often by moving numpy to 2.x. Install
with the same constraints the installers use:

.. code-block:: bash

   python -m pip install -c ProtSelect/Include/protselect_constraints.txt <package>

"PyRosetta was not found in your Python environment"
------------------------------------------------------

Analyse Rosetta Relax could not extract the scores of some model and fell back
to PyRosetta inside Horus, which does not have it. Check that ``pyrosetta_python``
points at a Python with PyRosetta, and look above this message in the block log
for the first failing extraction job.

"mmseqs: not found" or MMseqs2 fails on the cluster
-----------------------------------------------------

- **Locally:** set the ``mmseqs_path`` configuration (see :doc:`configuration`).
- **On a cluster:** check that **Cluster modules** names a module that provides
  MMseqs2 on that cluster. An MPI build needs **MPI runner** at ``srun``:
  without it, it aborts with ``PMI2_Job_GetId``.

Rosetta cannot find its module / BioEmu cannot find the GPU environment
-------------------------------------------------------------------------

Either the block's cluster software settings do not match your site (see
:ref:`remotes:Software on the cluster`), or the job was submitted from a login
node that cannot see that software: on a cluster with separate GPU and CPU
login nodes, submit the GPU blocks from the GPU remote and Rosetta from the CPU
one. See :doc:`remotes`.

"The folder … holds a clustering of different sequences / other settings"
---------------------------------------------------------------------------

MMseqs2 Clustering refuses to reuse a clustering made with other input. Change
**Output folder name**, or run the block itself with **Remove existing results**
on.

A block shows as a ghost / missing block
------------------------------------------

The flow uses a block that this version of the plugin does not have. The local
MMseqs2 Clustering block (``mmseqs2_cluster``) was merged into the SLURM one;
replace it with **MMseqs2 Clustering**, which runs locally or on a cluster.

No dGf column in the BioEmu metrics
-------------------------------------

First check whether native-contact generation and Q analysis ran. Disabling
contacts removes both Q and dGf. With Q available, a finite estimate requires
frames on both sides of ``q_threshold``: folded means ``Q >= q_threshold``.
All-folded or all-unfolded samples leave dGf missing for that model; the whole
column can be absent if no model has a finite estimate. More samples may help
characterise the populations, but do not guarantee both states will appear.
Check references, contact definitions and the ensemble before interpreting
missing values as a stability result.

Pareto Selection drops models
-------------------------------

A model needs a value for every objective. Models sampled by BioEmu but not
relaxed (or the reverse) have no ``score_per_residue`` (or no ``Q_Average``)
and are dropped, with a warning. Feed BioEmu the selected sequences so both
branches see the same models.

A value typed into a block was not saved
------------------------------------------

Number fields commit their value when they lose focus. Press Enter or click
elsewhere before saving the flow, or before running a block.

MAFFT rejects the selected algorithm
--------------------------------------

Use **Algorithm** ``auto``. The current UI also offers ``linsi``, ``ginsi``,
``einsi``, ``fftns`` and ``fftnsi``, but the backend accepts different names;
those UI choices fail validation. This is a known implementation mismatch.

SMOG2 is installed but native-contact generation fails
--------------------------------------------------------

The saved ``smog_path`` configuration is checked by the configuration dialog
but is not read by Analyse BioEmu. Put ``smog2`` on the Horus process's PATH,
including its required runtime environment. Missing SMOG2 does not automatically
skip contacts: either provide it, reuse compatible cached contacts, or disable
**Compute native contacts** and remove Q-dependent Pareto objectives. Contact
cache reuse checks file presence, so use a fresh contacts folder after changing
reference structures.

BioEmu fails before the cluster job is submitted
--------------------------------------------------

The backend may run a warm-up sample on the machine running Horus. Check that
**BioEmu environment** and **conda.sh path** resolve there and that required
packages, weights and caches are available. The saved ``bioemu_env`` plugin
configuration is not used by this block. See :ref:`configuration:BioEmu execution`
for the distinction between preparation and sampling.
