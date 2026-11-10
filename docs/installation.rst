Installation
============

This page takes you from nothing to a working plugin in six steps:

1. :ref:`install Horus <installation:Step 1: install Horus>`;
2. :ref:`install the plugin <installation:Step 2: install the plugin>`;
3. :ref:`install the external tools <installation:Step 3: install the external tools>`;
4. :ref:`point the plugin at the tools <installation:Step 4: point the plugin at the tools>`;
5. :ref:`set up your cluster <installation:Step 5: set up your cluster (optional)>`, if you use one;
6. :ref:`check it with the example data <installation:Step 6: check the installation>`.

Requirements
------------

- **A Linux or macOS machine** for the Horus desktop app. There is no Windows
  build; on Windows, use the Horus web app (see Step 1).
- **External tools** for the heavier stages: MMseqs2, MAFFT, PyTorch (for
  ProteinMPNN), Rosetta and PyRosetta, BioEmu, CodonTransformer and, optionally,
  SMOG2. Which ones you need depends on the blocks you use and where they run;
  see :doc:`configuration`. Step 3 installs them.
- **micromamba, mamba or conda**, to create the ``protselect`` environment the
  tools share.
- **Disk space**: about 7 GB for the ``protselect`` environment with CPU
  PyTorch, more with a CUDA build, plus about 75 GB while Rosetta installs if
  you install it locally.
- **A SLURM cluster** is recommended for anything beyond a small test:
  ProteinMPNN and BioEmu want a GPU, and a Rosetta relax of many models is a
  substantial compute workload. The plugin supports SLURM submission using
  your site's queue, modules and environments; see :doc:`remotes`.

.. important::

   **Rosetta and PyRosetta need licences.** Their non-commercial licences
   are distinct; commercial use requires the appropriate commercial agreement
   from the University of Washington CoMotion. Check coverage for both
   **Rosetta Relax** (Rosetta) and **Analyse Rosetta Relax** (PyRosetta).
   Download access alone does not grant commercial-use rights. See the
   `official licensing information <https://rosettacommons.org/software/download/>`_
   and :ref:`install_deps:Installing Rosetta for commercial use`.

Step 1: install Horus
---------------------

Download the latest Horus release for your system from the
`Horus releases page <https://gitlab.bsc.es/eapm/horus/-/releases>`_.

**Linux**

1. Download the ``.deb`` (Debian, Ubuntu) or ``.rpm`` (Fedora, Rocky, RHEL)
   package.
2. Install it with your package manager:

   .. code-block:: bash

      sudo apt install ./horus_<version>.deb      # Debian, Ubuntu
      sudo dnf install ./horus-<version>.rpm      # Fedora, Rocky, RHEL

3. Start Horus from the application menu, or from a terminal with ``horus``.

**macOS**

1. Download the ``.dmg``.
2. Open it and drag **Horus** into your Applications folder.
3. Start Horus from Applications.

**Windows**

Use a browser connected to a Linux or macOS Horus server with this plugin and
its tools installed. The Horus website links a `public demo
<https://horus.bsc.es/demo>`_ for exploring the interface; do not assume it
provides this plugin, your files or permission to install tools. In server
mode, **Local** means the server, not the computer running your browser.

**From source**

To run Horus from its repository instead (for developing Horus or plugins),
follow the README in the Horus repository: it installs micromamba and Bun (or
Node.js 18), creates a ``horus`` environment with ``bun run requirements``, and
starts the app with ``python Horus.py --debug --server``.

.. rubric:: Where Horus keeps its data

Horus stores its plugins, configurations and settings in its *AppSupport*
folder. You need it in Step 4 if you save the tool paths from a terminal.

.. list-table::
   :header-rows: 1
   :widths: 2 5

   * - Horus installed as
     - AppSupport folder
   * - Linux package
     - ``~/.local/share/com.bsc.horus``
   * - macOS app
     - ``~/Library/Application Support/com.bsc.horus``
   * - From source
     - ``AppSupport/`` in the Horus checkout

The ``HORUS_APP_SUPPORT_DIR`` environment variable overrides it. Horus prints
the folder it uses in its log at start-up (*AppSupport Dir: …*).

Step 2: install the plugin
--------------------------

1. Download ``protselect-<version>.hp`` from the
   `plugin's releases <https://github.com/BSC-CNS-EAPM/protein-set-selection-horus/releases>`_.
2. In Horus, open the **Plugin Manager** and use **Install plugin** to select
   the ``.hp`` file.
3. Horus installs the plugin and its Python dependencies (listed in
   ``plugin.meta``) into the plugin's own ``deps/`` folder. Follow the progress
   in the **Installation logs**, and wait for it to finish.
4. The **Protein Set Selection** blocks appear in the block palette, and the
   plugin adds an **Environment Setup** page.

Install the plugin from the Plugin Manager rather than by copying it into the
plugins folder. The desktop app refuses to install dependencies while it
starts, so a copied plugin loads without them. If that happens, reinstall from
the Plugin Manager, or start Horus with ``--server`` once so the dependencies
install at start-up.

Python dependencies
~~~~~~~~~~~~~~~~~~~

Installed automatically with the plugin:

- numpy (below 2.5), pandas, scipy, pyyaml, matplotlib, seaborn, tqdm,
  biopython 1.81, mdtraj, ipywidgets;
- `bsc_calculations <https://github.com/martin-floor/bsc_calculations>`_: writes
  and submits the cluster job scripts;
- `prepare_proteins <https://github.com/martin-floor/prepare_proteins>`_:
  Rosetta, BioEmu and structure handling;
- `bioprospecting-horus <https://github.com/BSC-CNS-EAPM/bioprospecting-horus>`_:
  a trimmed ``bioprospecting`` with the ProteinMPNN, MAFFT and CodonTransformer
  code the blocks use, including the ProteinMPNN weights.

PyTorch is not installed with the plugin; Step 3 installs it.

Step 3: install the external tools
----------------------------------

There are two installers. Both put the tools that need a conda environment
into one environment, ``protselect``. See
:ref:`configuration:Where the two installers put tools` before choosing.

**From Horus: the Environment Setup page.** In a flow window, choose
**Extensions → Environment Setup**. This is separate from **Horus → Plugins →
Protein Set Selection**, which opens the configuration dialog. The
:ref:`configuration:Finding the setup page and configuration dialog` section
shows both routes with screenshots. For every tool the page shows whether it
is found, where, and which blocks need it, with
an **Install** button for MMseqs2, MAFFT, PyTorch, PyRosetta, BioEmu and
CodonTransformer. It only detects Rosetta and SMOG2.

**From a terminal: install_deps.sh.** The installer at the root of the
repository checks every tool, says which blocks need it and asks before
installing it. It also installs Rosetta and SMOG2, and works before Horus is
installed.

.. code-block:: bash

   git clone https://github.com/BSC-CNS-EAPM/protein-set-selection-horus.git
   cd protein-set-selection-horus
   ./install_deps.sh --check     # see what is already there
   ./install_deps.sh             # install what is missing, asking first

If you have no micromamba, mamba or conda, install micromamba first and open a
new shell:

.. code-block:: bash

   "${SHELL}" <(curl -L micro.mamba.pm/install.sh)

All of the installer's options, what it installs where, and how to install
Rosetta offline are in :doc:`install_deps`.

.. tip::

   Install only what you will run **locally**. A block that runs on a cluster
   remote uses the cluster's modules and environments, not these. If
   ProteinMPNN, BioEmu and Rosetta all run on the cluster, local post-processing
   still needs PyRosetta, CodonTransformer, MAFFT and SMOG2 if native-contact
   analysis is enabled. Local clustering also needs MMseqs2. For BioEmu, clear
   the block's **BioEmu environment** if you do not intend to run cache
   preparation on the Horus host; see :ref:`configuration:BioEmu execution`.

Step 4: point the plugin at the tools
-------------------------------------

The blocks find the local tools through the plugin's **configurations**, which
Horus stores per remote. Fill them in one of three ways:

- on the **Environment Setup** page, keep **Remote** set to **Local** and
  press **Save detected paths**, then reopen the configuration dialog and
  review the values. In particular, correct the BioEmu value as described in
  :ref:`configuration:Detection and saving limitations`;
- run the installer with ``--config``, pointing at the Local remote's
  configuration file in the AppSupport folder from Step 1:

  .. code-block:: bash

     ./install_deps.sh --config ~/.local/share/com.bsc.horus/config/protselect/protselect_Local.json

  Run it while Horus is closed, or restart Horus afterwards, so Horus reads
  the new values;
- enter the values the installer prints at the end by hand, in the plugin's
  configurations with the **Local** remote selected.

The current blocks do **not** read the saved ``rosetta_path``, ``bioemu_env``
or ``smog_path`` configuration entries. These entries support setup checks,
but saving them alone does not configure execution:

- **Rosetta Relax**: set the block's **Rosetta executable** to the full path
  of ``rosetta_scripts``, or to its command name if it is on ``PATH``. The
  block's **Rosetta path** is an installation directory, not the executable.
- **BioEmu Sampling**: set **Cluster BioEmu environment** to the environment
  directory used for sampling (this also works locally). **BioEmu environment**
  and **conda.sh path** control a separate cache-preparation step on the Horus
  host in the current backend; see :ref:`configuration:BioEmu execution`.
- **Analyse BioEmu**: make ``smog2`` available on the ``PATH`` inherited by
  Horus. Disable **Compute native contacts** if that analysis is not needed.

The installer prints the detected locations. See :doc:`configuration`.

Step 5: set up your cluster (optional)
--------------------------------------

To run the heavy blocks on a SLURM cluster, add the cluster as a remote in
Horus's **Remotes** manager (a CPU remote and, on clusters with separate GPU
login nodes, a GPU one), then check each block's cluster software settings
against your site. :doc:`remotes` explains which block goes where and how to
size the jobs.

Step 6: check the installation
------------------------------

1. Run ``./install_deps.sh --check``. It ends with a summary; every tool you
   need should read ``ok`` or ``installed``. It exits with status 1 while a
   checked tool is missing or an installation attempt failed. Use ``--only``
   to limit checks to the tools you need locally.
2. In Horus, choose **Extensions → Environment Setup** and review the local
   checks. These are discovery checks, not a full test of each tool; see
   :ref:`configuration:Detection and saving limitations`.
3. Open the **ProteSel Pipeline** preset from the plugin's presets. Its input
   blocks come filled in with the small lysozyme example. Lower the expensive
   settings (Rosetta ``nstruct`` 2, BioEmu ``num_samples`` 10). For an MPI
   Rosetta cluster run, use **CPUs** 3; locally this setting instead controls
   concurrent model jobs. Configure the remotes and run it. See :doc:`workflow` and :doc:`example_data`.

If a block cannot find a tool, see :doc:`troubleshooting`.

Developing the plugin
---------------------

To work on the plugin itself, clone the repository and link its ``ProtSelect``
folder into Horus's plugins folder:

.. code-block:: bash

   git clone https://github.com/BSC-CNS-EAPM/protein-set-selection-horus.git
   ln -s "$PWD/protein-set-selection-horus/ProtSelect" <horus>/AppSupport/Plugins/ProtSelect

Restart Horus after changing a block's code. A block already placed in a flow
keeps a snapshot of its parameters, so a block that gained a new parameter
must be removed and added again to show it.

Building these docs:

.. code-block:: bash

   micromamba create -f Devtools/Environment/docs.yaml
   micromamba activate protselect_docs
   cd docs && make html
