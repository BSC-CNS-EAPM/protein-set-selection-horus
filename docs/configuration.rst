Tools and configuration
=======================

The plugin drives several external programs. Where each one comes from depends
on where the block runs:

- **On the Local remote**, the blocks find the tools through the plugin's
  **configurations** or, for Rosetta and BioEmu, through a parameter of the
  block itself (see the table).
- **On a cluster remote**, the job loads its own software: cluster modules and
  conda environments set in the block's parameters (see :doc:`remotes`).

Which tool each block needs
-----------------------------

.. list-table::
   :header-rows: 1
   :widths: 2 3 4 2

   * - Tool
     - Used by
     - Running locally, set it in
     - Installable from the Environment Setup page
   * - MMseqs2
     - MMseqs2 Clustering, MMseqs2 Threshold Sweep
     - configuration ``mmseqs_path``
     - yes
   * - MAFFT
     - Multiple Sequence Alignment (MAFFT)
     - configuration ``mafft_path``
     - yes
   * - PyTorch
     - ProteinMPNN Scoring
     - configuration ``proteinmpnn_python`` (a Python with torch)
     - yes
   * - Rosetta (``rosetta_scripts``)
     - Rosetta Relax
     - the block's **Rosetta path** and **Rosetta executable** parameters, or
       the executable on ``PATH``
     - no; ``install_deps.sh`` can (see :doc:`install_deps`)
   * - PyRosetta
     - Analyse Rosetta Relax
     - configuration ``pyrosetta_python`` (a Python with PyRosetta)
     - yes
   * - BioEmu
     - BioEmu Sampling
     - the block's **Cluster BioEmu environment** directory, or Python on
       ``PATH``; see :ref:`configuration:BioEmu execution`
     - yes
   * - SMOG2
     - Analyse BioEmu (fraction of native contacts, Q)
     - ``smog2`` on the ``PATH`` of the Horus process
     - no; ``install_deps.sh`` can (see :doc:`install_deps`)
   * - CodonTransformer
     - CodonTransformer
     - configuration ``codontransformer_env``, unless the block's
       **CodonTransformer environment** parameter is set
     - yes

.. note::

   The Rosetta, BioEmu and SMOG2 configurations are shown and checked by
   Horus, and the Environment Setup page fills them in, but the blocks do not
   read them yet: set the block parameters listed above instead.

Every other block (score reading, selection, collecting structures, Pareto,
the phylogenetic tree) is pure Python and needs nothing beyond the plugin's own
dependencies.

Finding the setup page and configuration dialog
-------------------------------------------------

These are two different views:

1. **Environment Setup**: in a flow window, open **Extensions → Environment
   Setup**. You can also open **Environment Setup** from the **Extensions**
   section of the Horus home screen. This page checks tools and offers
   **Install**, **Refresh** and **Save detected paths**.

   .. figure:: _static/environment-setup-menu.jpg
      :alt: Extensions menu with Environment Setup, above the setup page and its Refresh and Save detected paths buttons.
      :width: 860px

      The Extensions menu opens the setup page. Keep Remote set to Local for
      local tool setup.

2. **Configuration dialog**: open **Horus → Plugins**, then click the
   **Protein Set Selection** card or its gear button. Select **Local**, edit
   the tool paths and press **Save**.

   .. figure:: _static/plugin-manager-menu.jpg
      :alt: Horus menu with Plugins, and the Protein Set Selection card in the plugin manager.
      :width: 860px

      Open Plugins, then select the Protein Set Selection card or its gear.

   .. figure:: _static/plugin-configuration.jpg
      :alt: Protein Set Selection configuration dialog with Local selected, editable tool paths and a Save button.
      :width: 700px

      The configuration dialog edits saved values; it is separate from the
      Environment Setup extension.

The captures show an isolated documentation session. Installed tools and
status results depend on your machine.

The Environment Setup page
----------------------------

The page reports detected locations and which blocks need each tool. It has
**Install** buttons for MMseqs2, MAFFT, PyTorch, PyRosetta, BioEmu and
CodonTransformer. Every button except MMseqs2 installs into the ``protselect``
environment, which needs micromamba, mamba or conda on the ``PATH`` of the Horus
process. The page only detects Rosetta and SMOG2; install those separately (see
:doc:`install_deps`, including the commercial Rosetta instructions).

After **Save detected paths**, reopen the configuration dialog to inspect the
new values. The page's **Remote** field chooses a configuration file; checks
and installations still run on the machine hosting Horus, not over SSH on that
remote. Use **Local** here and configure cluster software on the blocks.

Where the two installers put tools
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Both use one conda environment, ``protselect``, for every tool that needs one:

.. list-table::
   :header-rows: 1
   :widths: 2 4 4

   * - Tool
     - Terminal: ``install_deps.sh``
     - Horus: Environment Setup
   * - MMseqs2
     - ``<tools-dir>/mmseqs`` (static build)
     - ``<plugin>/deps/mmseqs``
   * - MAFFT, PyTorch, PyRosetta, BioEmu, CodonTransformer
     - Environment ``protselect``
     - Environment ``protselect``
   * - Rosetta / SMOG2
     - Rosetta bundle / SMOG2 container wrapper or ``protselect``
     - Detection only

Detection and saving limitations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The setup page checks executables using the saved path, ``PATH``, the plugin's
``deps/bin`` and the ``protselect`` environment. A found file is not proof that
it can run successfully. For PyTorch, BioEmu, PyRosetta and CodonTransformer, it
uses the saved environment or interpreter, or ``protselect`` if none is saved,
and tries to import the package. This does not test model downloads, GPU
execution or a complete calculation.

One current limitation needs manual attention. For **BioEmu**, **Save detected
paths** writes the detected Python executable, but the configuration dialog's
BioEmu check expects an environment name or directory. Use the directory
containing ``bin/python`` (for example ``/home/me/micromamba/envs/protselect``),
and configure the sampling block too.

The terminal installer looks for Python tools only in ``protselect``; it does
not read configured interpreter paths, even with ``--config`` (that option
writes results). Tools configured in another environment can work despite a
``missing`` result from ``--check``.

Saving from the setup page or with ``--config`` writes JSON directly and does
not run the configuration dialog's validation callbacks. Review the values
before running a workflow.

From a terminal
-----------------

``install_deps.sh``, at the root of the repository, provides terminal setup
with the installation layout listed above. It checks each tool, says which blocks need it and asks before
installing it, and it also installs Rosetta and SMOG2.

.. code-block:: bash

   ./install_deps.sh --check     # report only
   ./install_deps.sh             # ask before each install
   ./install_deps.sh --config <AppSupport>/config/protselect/protselect_Local.json

At the end it prints the configuration values to enter in Horus. With
``--config`` it merges them into the saved configuration instead. Every option,
what it installs where, and how to install Rosetta offline are in
:doc:`install_deps`.

Setting the configurations by hand
------------------------------------

Open **Horus → Plugins → Protein Set Selection**, select **Local**, enter
absolute paths where possible, then press **Save**. Horus calls the plugin's
validation functions when saving from this dialog. Their checks differ:

- **MMseqs2 / MAFFT / SMOG2**: check whether the supplied file exists or the
  command resolves on ``PATH``. They do not run a calculation or verify that
  an arbitrary file is a working executable.
- **ProteinMPNN Python**: tries to import torch and reports CUDA availability.
  A missing GPU is a note, not an error.
- **PyRosetta**: tries to import PyRosetta in the selected Python.
- **CodonTransformer**: tries to import CodonTransformer and torch in the
  selected environment.
- **BioEmu**: tries to import BioEmu if it finds the environment. An empty or
  unresolved environment only produces a message or warning; it can still
  save. Named-environment discovery here searches ``~/miniconda3/envs``,
  ``~/anaconda3/envs``, ``~/micromamba/envs`` and ``~/mambaforge/envs``.
  Use an absolute environment directory for another location.
- **Rosetta**: checks for the executable file, follows symlinks and looks for
  ``main/database`` relative to the usual ``main/source/bin`` layout. A missing
  database produces a warning; an empty executable is also allowed. It does
  not launch Rosetta or verify the database contents.

These checks run on the Horus host, even when another remote's configuration
is selected. They do not prove that software is installed on a cluster.
Horus writes each configuration before its check runs, so a failed check can
leave saved values behind and stop validation of later entries. Correct the
reported problem and save again. A successful save is not an end-to-end tool
test, and the Rosetta/BioEmu/SMOG2 execution limitations above still apply.

Configurations are stored **per remote**: the values you save while the Local
remote is selected apply to local runs only. The full list, with every setting,
is in :doc:`reference/configurations`.

Environments with another Python
----------------------------------

The installers put PyRosetta, CodonTransformer, BioEmu and the torch used by
ProteinMPNN into ``protselect``. Subprocess-based tools can use a different
Python version from Horus; configure the interpreter or environment in the
appropriate setting. BioEmu execution is configured on its block.

Examples of valid values:

- ``pyrosetta_python``: ``/home/me/micromamba/envs/protselect/bin/python``
- ``codontransformer_env``: an environment name (``protselect``), its
  folder (``/home/me/micromamba/envs/protselect``) or its Python
- ``mmseqs_path``: ``/home/me/.local/share/protselect/mmseqs/bin/mmseqs``


The protselect environment
~~~~~~~~~~~~~~~~~~~~~~~~~~

Every pip install into ``protselect`` uses the constraints in
``ProtSelect/Include/protselect_constraints.txt``. CodonTransformer requires
``numpy<2``, so the whole environment stays on numpy 1.x and on the JAX release
that supports it. Leave those constraints in place when adding packages by hand.

Environments created by an earlier version of the installer (``mafft``,
``proteinmpnn``, ``pyrosetta``, ``bioemu``, ``codontransformer``, ``smog2``) are
neither reused nor removed. A saved configuration that points at one keeps
working. After installing into ``protselect``, save the new paths, then delete
the old environments if you no longer need them.

To use another environment instead, configure it as follows:

- set ``proteinmpnn_python`` and ``pyrosetta_python`` to its ``bin/python``;
- set ``codontransformer_env`` to the environment directory;
- set ``bioemu_env`` in the configuration dialog to the directory for its
  check, and set **Cluster BioEmu environment** to that directory on the
  sampling block. Configure or disable the separate host-side cache step
  described below;
- set ``mmseqs_path`` and ``mafft_path`` to their executables, if installed
  there, and expose ``smog2`` on Horus's ``PATH`` if needed;
- keep the Rosetta bundle and database together and set **Rosetta executable**
  on the relax block. Rosetta is a compiled program, not a Python package that
  must share this environment.

Run the dialog's checks and a small workflow for every tool you intend to use.

BioEmu execution
------------------

The current ``prepare_proteins`` backend distinguishes setup from sampling:

- **BioEmu environment** (default ``protselect``), when nonempty, can activate
  an environment through **conda.sh path** and run a one-sample cache-preparation
  command on the Horus host. This happens during job setup, even when the
  selected remote is a cluster. Clear this field if you do not want that local
  preparation step.
- **Cluster BioEmu environment** is an environment directory. The plugin
  substitutes its ``bin/python`` into the sampling commands. An explicit
  directory works for local runs too, despite the field's name. Without it,
  outside the MareNostrum fallback, the commands use ``python`` on ``PATH``;
  the setup environment field alone does not activate that Python.
- For local runs, start Horus with the needed tools on ``PATH`` or set the
  block's **Environment variables**. The shared local runner does not apply
  cluster module loads or the BioEmu-specific cluster cache exports.

For compute nodes without network access, prepare model checkpoints and any
required caches in advance. A local ColabFold database and **MSA calculation**
avoid the alignment web-service request, but do not download missing BioEmu
checkpoints. See :ref:`remotes:Per-block advice`.
