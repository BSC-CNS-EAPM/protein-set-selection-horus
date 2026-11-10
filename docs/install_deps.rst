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

- **Linux or macOS**, with bash, ``curl`` and ``tar``. Individual tools have
  platform restrictions: the MMseqs2 download is architecture-specific,
  Rosetta bundles do not cover Linux ARM, and the native SMOG2 route requests
  an x86_64 Linux sysroot. Use an appropriate container or manual SMOG2
  installation on other architectures.
- **micromamba, mamba or conda** on ``PATH``. To install micromamba:

  .. code-block:: bash

     "${SHELL}" <(curl -L micro.mamba.pm/install.sh)

- An internet connection, except for an offline Rosetta install (see
  :ref:`install_deps:Installing Rosetta offline`).
- ``python3`` (or ``python``), for ``--config``.
- No root access is needed for the default installation locations. A container
  installation additionally needs a working podman or docker setup.

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
       ``<AppSupport>/config/protselect/protselect_Local.json``. It writes
       results; it does not read this file to discover tools, and ``--check``
       suppresses the write.
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

MAFFT, ProteinMPNN's PyTorch, PyRosetta, BioEmu and CodonTransformer all go
into one conda environment, ``protselect``, created the first time a tool needs
it. MMseqs2 and Rosetta use standalone directories, and SMOG2 uses a container
wrapper or ``protselect``. The installer reuses MMseqs2, MAFFT, Rosetta and
SMOG2 when it finds them on ``PATH``. Tools in environments left by an earlier
version are not reused; see :ref:`configuration:The protselect environment`.

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
     - conda environment ``protselect``
     - ``mafft_path``
   * - PyTorch
     - ProteinMPNN Scoring, locally
     - conda environment ``protselect``
     - ``proteinmpnn_python``
   * - PyRosetta
     - Analyse Rosetta Relax
     - conda environment ``protselect``
     - ``pyrosetta_python``
   * - BioEmu
     - BioEmu Sampling, locally
     - conda environment ``protselect``
     - ``bioemu_env`` (environment directory); use that directory in the
       block's **Cluster BioEmu environment** for sampling
   * - CodonTransformer
     - CodonTransformer
     - conda environment ``protselect``
     - ``codontransformer_env``
   * - Rosetta (optional)
     - Rosetta Relax, locally
     - ``<tools-dir>/rosetta``
     - ``rosetta_path``, for the block's **Rosetta executable**
   * - SMOG2 (optional)
     - Analyse BioEmu, for the fraction of native contacts only
     - Container wrapper ``<tools-dir>/bin/smog2``, or native
       ``<tools-dir>/smog2-<version>/bin/smog2`` with dependencies in environment
       ``protselect``
     - ``smog_path``

PyTorch and the GPU
~~~~~~~~~~~~~~~~~~~

If ``nvidia-smi`` is on ``PATH``, the script defaults to the CUDA 12.4 PyTorch
index; otherwise it uses the CPU index. This is a simple heuristic, not a
check that your driver supports the chosen build. In interactive mode, the
script prompts for the index URL; choose one compatible with your driver
using the `official PyTorch installer <https://pytorch.org/get-started/locally/>`_.
``--yes`` accepts the script's default without that prompt.

The ``protselect`` environment is used for ProteinMPNN scoring **locally**. On
a cluster, that block uses the environment in its parameters. BioEmu and
CodonTransformer use the same PyTorch, so the build you choose applies to all
three.

Rosetta
~~~~~~~

Rosetta is optional: skip it if Rosetta Relax runs on a cluster that provides
Rosetta as a module.

- **Licence.** This installer's Rosetta download route is for non-commercial
  use. It asks for confirmation or accepts ``--rosetta-noncommercial``.
  Rosetta is also available under a separate commercial licence; follow
  :ref:`install_deps:Installing Rosetta for commercial use` for that route.
- **Size.** About 21.5 GB to download and 52 GB once installed; have about
  75 GB free while installing.
- **Platforms.** Linux x86_64 and macOS (Intel and Apple silicon).
- **Interrupted downloads.** Run the installer again to resume the download.

When it finishes, it prints what to set in the Rosetta Relax block:
**Rosetta executable** (use the full binary path unless it is on ``PATH``)
and, if needed by your workflow, **Rosetta path** (the installation directory).
It then offers to link the binary into ``~/.local/bin`` so Horus can find it
when that directory is on ``PATH``.

Installing Rosetta for commercial use
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Obtain or confirm your organisation's Rosetta commercial licence through
   `University of Washington CoMotion <https://els2.comotion.uw.edu/product/rosetta>`_
   (``license@uw.edu``). Check PyRosetta coverage separately if you use
   **Analyse Rosetta Relax**: it has a
   `separate licensing page <https://els2.comotion.uw.edu/product/pyrosetta>`_.
   The `Rosetta licence <https://github.com/RosettaCommons/rosetta/blob/main/LICENSE.md>`_
   explains that a commercial agreement supersedes the non-commercial terms.
2. Download or build the distribution permitted by your agreement, following
   the `official installation instructions
   <https://docs.rosettacommons.org/demos/latest/tutorials/install_build/install_build>`_.
   Preserve the bundle's ``main/source/bin`` and ``main/database`` layout.
3. In **Rosetta Relax**, set **Rosetta executable** to the full path of the
   suitable ``rosetta_scripts`` binary. Set the block's **Rosetta path** to
   the installation directory if required by your workflow. You may also fill
   in the configuration dialog's Rosetta executable for its check, but the
   block does not read that saved configuration entry.
4. Install licensed PyRosetta into an environment following its distribution
   instructions, then point ``pyrosetta_python`` at that environment's Python.

Do not pass ``--rosetta-noncommercial`` or answer yes to the non-commercial
question for commercial work. The script has no commercial-licence option;
its offline archive route asks the same question. Install licensed Rosetta
separately, then use ``./install_deps.sh --only rosetta --check`` to look for
it (put the binary on ``PATH`` if it is outside the installer's tools folder).

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

SMOG2 is needed to generate the native contacts used for Q and the
Q-derived folding free-energy estimate. Its absence is allowed by the
installer, but **Analyse BioEmu** does not automatically skip this phase:
disable **Compute native contacts** if you are not supplying the required
contacts. The preset's Pareto objective ``Q_Average`` then also needs changing.
SMOG2 is distributed under the GPL; see its
`official repository <https://github.com/smog-server/SMOG2>`_.

- With **podman or docker** installed, SMOG2 runs from its official container.
- Otherwise the script adds Perl, Java and build dependencies to the
  ``protselect`` environment, then downloads and configures SMOG2 under
  ``<tools-dir>/smog2-<version>``. This includes compiling dependencies.

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
     mafft_path             /home/me/micromamba/envs/protselect/bin/mafft
     ...

Each tool ends as ``ok`` (already there), ``installed``, ``missing`` (you
skipped it), ``failed``, or ``optional-missing`` (Rosetta or SMOG2 not
installed).

Get the values into Horus in one of three ways:

- run with ``--config FILE`` to save them into that configuration file (keep
  Horus closed, or restart it afterwards);
- press **Save detected paths** on **Extensions → Environment Setup**, then
  review and correct the values described in
  :ref:`configuration:Detection and saving limitations`;
- enter them by hand in the plugin's configurations, with the **Local** remote
  selected.

Rosetta and BioEmu are set on their blocks, and SMOG2 is found on ``PATH``:
see :doc:`configuration`.

If ``~/.local/bin`` is not on your ``PATH``, the installer says so. Add it in
your shell profile, and make sure Horus is started from a shell that has it.

Exit status
-----------

The installer exits with **1** if any processed tool is recorded as
``missing`` or ``failed``, and **0** otherwise. Skipping Rosetta or SMOG2
produces ``optional-missing`` and does not fail the check, but a failed attempt
to install either tool does. ``--only`` limits the tools included in this
summary. A successful check confirms discovery, not a complete workflow run.
