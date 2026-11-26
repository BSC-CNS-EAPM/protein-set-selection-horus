Protein Set Selection
=====================

A `Horus <https://horus.bsc.es>`_ plugin that picks a small, expressible and
structurally diverse set of proteins out of a large protein family.

Starting from structures (for example AlphaFold models) and their sequences, it:

1. scores every structure with **ProteinMPNN**, using both the vanilla and the
   soluble weights;
2. clusters the sequences by identity with **MMseqs2** and keeps the
   best-scoring member of each of the top clusters, under each weight set in
   turn, keeping the union of the two selections;
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

      Install Horus and the plugin step by step, then the external tools and
      your cluster remotes.

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
   install_deps
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

Citing this plugin
------------------

Citation metadata lives in ``CITATION.cff`` at the repository root. GitHub turns
it into a **Cite this repository** button and exports BibTeX and APA from it.
Cite the exact version you used; the released version and its commit are both
recorded there.

Funding and acknowledgements
----------------------------

Developed at the `Barcelona Supercomputing Center <https://www.bsc.es/>`_ for
deliverable **D1.3** of work package 1 of the `ROBUSTOO project
<https://www.robustoo.eu/>`_ -- *Robust industrial biocatalysts with
peroxygenase, phenol-oxidase or furfuryl-oxidase activities from bacterial and
fungal hosts*.

Funded by the European Union under Grant Agreement No **101135119**. Views and
opinions expressed are however those of the authors only and do not necessarily
reflect those of the European Union. Neither the European Union nor the granting
authority can be held responsible for them.

.. |eu| image:: _static/logos/eu-funded.png
   :height: 55px
   :alt: Funded by the European Union

.. |robustoo| image:: _static/logos/robustoo.png
   :height: 55px
   :alt: ROBUSTOO
   :target: https://www.robustoo.eu/

.. |bsc| image:: _static/logos/bsc.jpg
   :height: 55px
   :alt: Barcelona Supercomputing Center
   :target: https://www.bsc.es/

|eu| |robustoo| |bsc|
