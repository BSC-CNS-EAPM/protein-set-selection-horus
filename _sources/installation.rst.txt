Installation
============

Requirements
------------

- **Horus.** Install the plugin into a Horus installation (desktop app, server
  or web app).
- **External tools** for the heavier stages: MMseqs2, MAFFT, PyTorch (for
  ProteinMPNN), Rosetta and PyRosetta, BioEmu, CodonTransformer and, optionally,
  SMOG2. Which ones you need depends on the blocks you use and where they run;
  see :doc:`configuration`.
- **A SLURM cluster** is recommended for anything beyond a small test:
  ProteinMPNN and BioEmu want a GPU, and a Rosetta relax of many models is a
  cluster job. Cluster submission currently targets MareNostrum 5 login nodes;
  everything else runs on the machine running Horus. See :doc:`remotes`.

Installing the plugin
---------------------

1. Download ``protselect-<version>.hp`` from the repository's releases.
2. In Horus, open the **Plugin Manager** and use **Install plugin** to select
   the ``.hp`` file.
3. Horus installs the plugin and its Python dependencies (listed in
   ``plugin.meta``) into the plugin's own ``deps/`` folder. Follow the progress
   in the **Installation logs**.

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

PyTorch is deliberately not among them: it is large and depends on your CUDA
version. ProteinMPNN runs with a Python environment that has it (see
:doc:`configuration`).

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

The block reference is generated from the block definitions at every build.

Next steps
----------

- :doc:`configuration`: point the plugin at the external tools.
- :doc:`remotes`: set up your cluster.
- :doc:`workflow`: open and run the preset.
