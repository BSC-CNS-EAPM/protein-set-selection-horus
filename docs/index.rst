Protein Set Selection
=====================

A `Horus <https://horus.bsc.es>`_ plugin that picks a small, expressible and
structurally diverse set of proteins out of a large protein family.

Starting from structures (for example AlphaFold models) and their sequences, it:

1. scores every structure with **ProteinMPNN**, using both the vanilla and the
   soluble weights;
2. clusters the sequences by identity with **MMseqs2** and keeps the
   best-scoring member of each of the top clusters;
3. relaxes the representatives with **Rosetta** and samples their
   conformational ensembles with **BioEmu**;
4. ranks them on several objectives at once with a **Pareto** selection;
5. codon-optimises the final set for expression with **CodonTransformer**, and
   aligns it (**MAFFT**) and builds a **phylogenetic tree** to inspect its
   diversity.

The plugin is not tied to any protein family. The workflow was developed for
unspecific peroxygenases and tested on 5-hydroxymethylfurfural oxidases, but
every block takes generic inputs: a sequences file, a folder of structures,
score and metric tables.

The whole pipeline ships as a ready-made flow, **ProteSel Pipeline**, that you
open from the plugin's presets in Horus.

.. grid:: 2
   :gutter: 3

   .. grid-item-card:: Getting started
      :link: installation
      :link-type: doc

      Install the plugin, set up the external tools and your cluster remotes.

   .. grid-item-card:: The workflow
      :link: workflow
      :link-type: doc

      What each stage does, how the blocks connect, and how to run the preset.

   .. grid-item-card:: Remotes and clusters
      :link: remotes
      :link-type: doc

      Which blocks run where, and how to size the cluster jobs.

   .. grid-item-card:: Block reference
      :link: reference/index
      :link-type: doc

      Inputs, parameters and outputs of every block.

.. toctree::
   :maxdepth: 2
   :caption: Getting started
   :hidden:

   installation
   configuration
   remotes
   example_data

.. toctree::
   :maxdepth: 2
   :caption: Using the plugin
   :hidden:

   workflow
   troubleshooting

.. toctree::
   :maxdepth: 2
   :caption: Reference
   :hidden:

   reference/index
