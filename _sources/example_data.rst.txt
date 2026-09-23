Example data
============

Two small datasets ship with the plugin, in ``ProtSelect/ExampleData/``:

.. list-table::
   :header-rows: 1

   * -
     - ``lysozyme/``
     - ``hmfo/``
   * - Proteins
     - Lysozyme C / alpha-lactalbumin
     - 5-hydroxymethylfurfural oxidases
   * - Models
     - 10
     - 10
   * - Length
     - 121–130 residues
     - 503–577 residues
   * - Source
     - AlphaFold DB (CC-BY-4.0)
     - a 50,698-sequence family search
   * - Useful ``min_seq_id``
     - 0.45–0.8
     - below 0.5
   * - Good for
     - checking a flow is wired correctly, in seconds
     - seeing the pipeline on realistic input

Each dataset has the same layout:

.. code-block:: text

   structures/        one PDB per protein
   sequences.json     {model: sequence}, keyed by the structure file names
   labels.json        {model: organism}, for the phylogenetic tree
   provenance.json    where each entry comes from

Start with **lysozyme** to check that a flow is connected. Use **hmfo** to see
the pipeline behave at a realistic size: there ProteinMPNN takes minutes on a
CPU and the Rosetta relax is a cluster job. The HMFO set is the one the
pipeline was tested on end to end on a SLURM cluster.

Using your own data
-------------------

The **model name** joins everything in the pipeline: the ProteinMPNN scores,
the MMseqs2 clusters, the structure files and the rows of the Rosetta and BioEmu
tables are all keyed by it. With your own data:

- name each structure ``<model>.pdb``;
- key the sequences file by the same ``<model>`` names;
- use a FASTA file (``>model``) or a JSON ``{model: sequence}`` file.

Names that do not match are reported by the blocks that join the two, and
those models drop out of the rest of the pipeline.
