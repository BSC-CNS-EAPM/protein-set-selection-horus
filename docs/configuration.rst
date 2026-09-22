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
     - no: licensed, install it yourself
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
     - no: registration required
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

Rosetta and SMOG2 are only detected, never installed: Rosetta needs a licence
and SMOG2 a registration. Install them yourself and point the configuration at
them.

After saving from the page, reopen the configurations in Horus to see the new
values.

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
Horus. The plugin runs them as separate processes and removes Horus's own
``PYTHONPATH`` from their environment, so you can point the configuration at any
environment. You do not need to install these tools into Horus.

Examples of valid values:

- ``pyrosetta_python``: ``/home/me/micromamba/envs/rosetta/bin/python``
- ``codontransformer_env``: an environment name (``codontransformer``), its
  folder (``/home/me/micromamba/envs/codontransformer``) or its Python
- ``mmseqs_path``: ``/home/me/micromamba/envs/mmseqs/bin/mmseqs``

