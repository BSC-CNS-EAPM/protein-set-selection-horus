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
---------------------------

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
     - no; ``install_deps.sh`` can (see below)
   * - PyRosetta
     - Analyse Rosetta Relax
     - configuration ``pyrosetta_python`` (a Python with PyRosetta)
     - yes
   * - BioEmu
     - BioEmu Sampling
     - the block's **BioEmu environment** parameter
     - yes
   * - SMOG2
     - Analyse BioEmu (fraction of native contacts, Q)
     - ``smog2`` on the ``PATH`` of the Horus process
     - no; ``install_deps.sh`` can (see below)
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

The Environment Setup page
--------------------------

The plugin adds an **Environment Setup** page to Horus. For every tool it shows
whether the tool is found, where, and which blocks need it. From there you can:

- **install** the tools it knows how to install (MMseqs2, MAFFT, PyTorch,
  PyRosetta, BioEmu, CodonTransformer), each into its own environment;
- **save the detected paths** into the plugin configuration, so the blocks find
  them.

The page only detects Rosetta and SMOG2. Neither needs credentials, but
Rosetta is a ~21.5 GB download licensed for non-commercial use only, and SMOG2
needs a container engine or a Perl toolchain. Install them with
``install_deps.sh`` (below) or by hand, and point the configuration at
them.

After saving from the page, reopen the configurations in Horus to see the new
values.

From a terminal
---------------

``install_deps.sh``, at the root of the repository, does the same from a
terminal, which is handy on a machine where Horus is not running yet. It checks
each tool, explains which blocks need it and asks before installing it:
MMseqs2 from the official static build, the rest into their own conda
environments (``mafft``, ``proteinmpnn``, ``pyrosetta``, ``bioemu``,
``codontransformer``). It needs micromamba, mamba or conda for the
environments.

It also installs the two tools the page leaves alone:

- **Rosetta**: the binary bundle from RosettaCommons, after you confirm that
  your use is academic or non-commercial; Rosetta (like PyRosetta) is licensed
  for that use only, and commercial use needs a commercial licence (see
  :doc:`installation`). It is about 21.5 GB to download and 52 GB extracted,
  and an interrupted download resumes when you rerun the script. With
  ``--rosetta-archive FILE`` it keeps the bundle at ``FILE``, or installs from a
  bundle you already have there, which also works on a machine without
  internet access. Set the Rosetta Relax block's **Rosetta executable** to the
  binary it reports, or let the script link it onto ``PATH``.
- **SMOG2**: a ``smog2`` wrapper around the official container when podman or
  docker is installed, otherwise a native install into a ``smog2`` environment,
  which builds PDL from source and takes several minutes. Analyse BioEmu looks
  ``smog2`` up on ``PATH``, so the script offers to link it into
  ``~/.local/bin``.

.. code-block:: bash

   ./install_deps.sh --check     # report only
   ./install_deps.sh             # ask before each install
   ./install_deps.sh --config <appSupport>/config/protselect/protselect_Local.json
   ./install_deps.sh --yes --rosetta-noncommercial   # unattended, Rosetta included

At the end it prints the configuration values to enter in Horus. With
``--config`` it merges them into the saved configuration instead.

Setting the configurations by hand
----------------------------------

In Horus, open the plugin's configurations and set each tool you use. Every
configuration has a check that runs when you save it and reports whether the
tool was found, and for Rosetta whether its database sits next to the binary.

Configurations are stored **per remote**: the values you save while the Local
remote is selected apply to local runs only. The full list, with every setting,
is in :doc:`reference/configurations`.

Environments with another Python
--------------------------------

PyRosetta, CodonTransformer, BioEmu and the torch used by ProteinMPNN usually
live in their own conda environments, often on a different Python version from
Horus. You can point the configuration at any environment, even one with a
different Python version. You do not need to install these tools into Horus.

Examples of valid values:

- ``pyrosetta_python``: ``/home/me/micromamba/envs/rosetta/bin/python``
- ``codontransformer_env``: an environment name (``codontransformer``), its
  folder (``/home/me/micromamba/envs/codontransformer``) or its Python
- ``mmseqs_path``: ``/home/me/micromamba/envs/mmseqs/bin/mmseqs``

