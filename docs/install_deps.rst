The dependency installer
========================

``install_deps.sh``, at the root of the repository, installs the external tools
the plugin uses, from a terminal. It covers the same tools as the **Environment
Setup** page in Horus, plus Rosetta and SMOG2. You can run it before Horus is
installed.

The plugin's own Python dependencies are installed by Horus with the plugin
(see :doc:`installation`).

What it needs
-------------

- **Linux** (x86_64 or aarch64) or **macOS**, with bash, ``curl`` and ``tar``.
- **micromamba, mamba or conda** on ``PATH``. To install micromamba:

  .. code-block:: bash

     "${SHELL}" <(curl -L micro.mamba.pm/install.sh)

- An internet connection, except for an offline Rosetta install (see
  :ref:`install_deps:Installing Rosetta offline`).
- ``python3``, only for ``--config``.
- No root access: everything is installed in your home folder.

Quick start
-----------

.. code-block:: bash

   git clone https://github.com/BSC-CNS-EAPM/protein-set-selection-horus.git
   cd protein-set-selection-horus

   ./install_deps.sh --check     # report only, installs nothing
   ./install_deps.sh             # ask before each install

For every tool it shows whether it is found and which blocks need it, and asks
before installing a missing one. Answering no, or pressing Enter, skips the
tool. At the end it prints a summary and the configuration values to enter in
Horus.

You can run it again at any time; it only installs what is still missing.

Options
-------

.. list-table::
   :header-rows: 1
   :widths: 3 6

   * - Option
     - Effect
   * - ``--check``
     - Report what is found and install nothing.
   * - ``--yes``, ``-y``
     - Install everything missing without asking. Rosetta is still skipped
       unless ``--rosetta-noncommercial`` is also given.
   * - ``--only TOOL[,TOOL...]``
     - Handle only these tools: ``mmseqs``, ``mafft``, ``torch``,
       ``pyrosetta``, ``bioemu``, ``codontransformer``, ``rosetta``, ``smog``.
   * - ``--config FILE``
     - Also save the resulting paths into a Horus configuration file, normally
       ``<AppSupport>/config/protselect/protselect_Local.json``.
   * - ``--rosetta-noncommercial``
     - Confirm that your use of Rosetta is academic or non-commercial, so it can
       be installed without the question. Needed for unattended installs.
   * - ``--rosetta-archive FILE``
     - Download the Rosetta bundle to ``FILE`` and keep it, or install from the
       bundle already at ``FILE``.
   * - ``--tools-dir DIR``
     - Where MMseqs2, Rosetta and SMOG2 are installed. Default
       ``~/.local/share/protselect``.
   * - ``-h``, ``--help``
     - Print the usage and exit.

Environment variables:

- ``PROTSELECT_TOOLS_DIR``: default for ``--tools-dir``;
- ``ROSETTA_VERSION``: the Rosetta release to download (default ``3.15``).

Examples:

.. code-block:: bash

   # Only the tools for local scoring and alignment
   ./install_deps.sh --only torch,mafft

   # Install and save the paths straight into Horus (Linux package install)
   ./install_deps.sh --config ~/.local/share/com.bsc.horus/config/protselect/protselect_Local.json

   # Unattended, Rosetta included
   ./install_deps.sh --yes --rosetta-noncommercial

What it installs, and where
---------------------------

Most tools get their own conda environment, named after the tool.

.. list-table::
   :header-rows: 1
   :widths: 2 2 4 3

   * - Tool
     - Needed by
     - Installed as
     - Configuration value it reports
   * - MMseqs2
     - MMseqs2 Clustering, MMseqs2 Threshold Sweep
     - ``<tools-dir>/mmseqs``
     - ``mmseqs_path``
   * - MAFFT
     - Multiple Sequence Alignment (MAFFT)
     - conda environment ``mafft``
     - ``mafft_path``
   * - PyTorch
     - ProteinMPNN Scoring, locally
     - conda environment ``proteinmpnn``
     - ``proteinmpnn_python``
   * - PyRosetta
     - Analyse Rosetta Relax
     - conda environment ``pyrosetta``
     - ``pyrosetta_python``
   * - BioEmu
     - BioEmu Sampling, locally
     - conda environment ``bioemu``
     - ``bioemu_env``, for the block's **BioEmu environment**
   * - CodonTransformer
     - CodonTransformer
     - conda environment ``codontransformer``
     - ``codontransformer_env``
   * - Rosetta (optional)
     - Rosetta Relax, locally
     - ``<tools-dir>/rosetta``
     - ``rosetta_path``, for the block's **Rosetta executable**
   * - SMOG2 (optional)
     - Analyse BioEmu, for the fraction of native contacts only
     - ``<tools-dir>/bin/smog2``, or conda environment ``smog2``
     - ``smog_path``

PyTorch and the GPU
~~~~~~~~~~~~~~~~~~~

On a machine with an NVIDIA GPU the installer offers the CUDA build of
PyTorch, otherwise the CPU build, which works but is slow. Before installing it
shows the PyTorch package index it will use; type another one to change it, for
example ``https://download.pytorch.org/whl/cu118`` for an older driver.

PyTorch is only needed to score with ProteinMPNN **locally**. On a cluster
remote the block uses the conda environment set in its parameters.

Rosetta
~~~~~~~

Rosetta is optional: skip it if Rosetta Relax runs on a cluster that provides
Rosetta as a module.

- **Licence.** Rosetta is licensed for academic and non-commercial use only
  (see :doc:`installation`). The installer asks you to confirm that your use is
  covered, or takes ``--rosetta-noncommercial`` for unattended runs.
- **Size.** About 21.5 GB to download and 52 GB once installed; have about
  75 GB free while installing.
- **Platforms.** Linux x86_64 and macOS (Intel and Apple silicon).
- **Interrupted downloads.** Run the installer again to resume the download.

When it finishes, it prints what to set in the Rosetta Relax block:
**Rosetta executable** (the binary's name) and, if you use symmetry,
**Rosetta path**. It then offers to link the binary into ``~/.local/bin`` so
Horus finds it on ``PATH``.

Installing Rosetta offline
^^^^^^^^^^^^^^^^^^^^^^^^^^

``--rosetta-archive`` keeps the downloaded bundle, so you can install it on
another machine without downloading it again:

.. code-block:: bash

   # On a machine with internet: download and keep the bundle
   ./install_deps.sh --only rosetta --rosetta-archive ~/rosetta_bundle.tar.bz2

   # Copy the bundle over, then on the offline machine:
   ./install_deps.sh --only rosetta --rosetta-archive ~/rosetta_bundle.tar.bz2

SMOG2
~~~~~

SMOG2 is optional: Analyse BioEmu only needs it for the fraction of native
contacts (Q) and the folding free energy derived from it.

- With **podman or docker** installed, SMOG2 runs from its official container.
- Otherwise it is installed into a ``smog2`` conda environment, which takes
  several minutes.

Analyse BioEmu needs ``smog2`` on ``PATH``, so the installer offers to link it
into ``~/.local/bin``.

After installing
----------------

At the end, the installer prints a summary and the configuration values:

.. code-block:: text

   == Summary ==
     MMseqs2                  ok
     MAFFT                    installed
     PyTorch (ProteinMPNN)    installed
     ...
     Rosetta                  optional-missing

   == Plugin configuration values ==
     mmseqs_path            /home/me/.local/share/protselect/mmseqs/bin/mmseqs
     mafft_path             /home/me/micromamba/envs/mafft/bin/mafft
     ...

Each tool ends as ``ok`` (already there), ``installed``, ``missing`` (you
skipped it), ``failed``, or ``optional-missing`` (Rosetta or SMOG2 not
installed).

Get the values into Horus in one of three ways:

- run with ``--config FILE`` to save them into that configuration file (keep
  Horus closed, or restart it afterwards);
- press **Save detected paths** on the **Environment Setup** page;
- enter them by hand in the plugin's configurations, with the **Local** remote
  selected.

Rosetta and BioEmu are set on their blocks, and SMOG2 is found on ``PATH``:
see :doc:`configuration`.

If ``~/.local/bin`` is not on your ``PATH``, the installer says so. Add it in
your shell profile, and make sure Horus is started from a shell that has it.

Exit status
-----------

The installer exits with **1** when a required tool is still missing at the
end, and **0** otherwise; Rosetta and SMOG2 are optional. So
``./install_deps.sh --check`` also works as a quick test of a machine's setup.
