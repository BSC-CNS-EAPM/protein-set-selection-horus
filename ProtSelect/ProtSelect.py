"""
Entry point for the Protein Set Selection plugin.

Horus imports this module after putting ``Include/`` and ``deps/`` on
``sys.path``, and reads the module-level ``plugin`` attribute. Blocks are
registered explicitly below; there is no auto-discovery of ``Include/Blocks``.

Imports are made inside ``create_plugin`` on purpose: a block module that fails
to import takes the whole plugin down with it, so keeping them local makes the
failure point obvious in the Horus log.
"""

from HorusAPI import Plugin


def create_plugin():
    """
    Generates the Protein Set Selection plugin and returns the instance
    """
    # ========== Plugin Definition ========== #

    protselect_plugin = Plugin()

    # ========== Blocks (grouped by category, in pipeline order) ========== #
    # pylint: disable=import-outside-toplevel

    # ---------- ProteinMPNN ----------
    from Blocks.proteinmpnn import proteinMPNNBlock

    protselect_plugin.addBlock(proteinMPNNBlock)

    from Blocks.read_proteinmpnn_scores import readProteinMPNNScoresBlock

    protselect_plugin.addBlock(readProteinMPNNScoresBlock)

    # ---------- Structure Preparation ----------
    from Blocks.trim_alphafold_models import trimAlphaFoldModelsBlock

    protselect_plugin.addBlock(trimAlphaFoldModelsBlock)

    from Blocks.collect_selected_pdbs import collectSelectedPDBsBlock

    protselect_plugin.addBlock(collectSelectedPDBsBlock)

    # ---------- Clustering & Selection ----------
    from Blocks.mmseqs2 import mmseqsClusterBlock

    protselect_plugin.addBlock(mmseqsClusterBlock)

    from Blocks.mmseqs2_slurm import mmseqsClusterSlurmBlock

    protselect_plugin.addBlock(mmseqsClusterSlurmBlock)

    from Blocks.mmseqs_threshold_sweep import mmseqsThresholdSweepBlock

    protselect_plugin.addBlock(mmseqsThresholdSweepBlock)

    from Blocks.select_cluster_representatives import selectClusterRepresentativesBlock

    protselect_plugin.addBlock(selectClusterRepresentativesBlock)

    from Blocks.combine_selected_sequences import combineSelectedSequencesBlock

    protselect_plugin.addBlock(combineSelectedSequencesBlock)

    from Blocks.sequence_length_distribution import sequenceLengthDistributionBlock

    protselect_plugin.addBlock(sequenceLengthDistributionBlock)

    # ---------- Rosetta ----------
    from Blocks.rosetta_relax import rosettaRelaxBlock

    protselect_plugin.addBlock(rosettaRelaxBlock)

    from Blocks.analyse_rosetta_relax import analyseRosettaRelaxBlock

    protselect_plugin.addBlock(analyseRosettaRelaxBlock)

    # ---------- BioEmu ----------
    from Blocks.bioemu import bioEmuBlock

    protselect_plugin.addBlock(bioEmuBlock)

    from Blocks.analyse_bioemu import analyseBioEmuBlock

    protselect_plugin.addBlock(analyseBioEmuBlock)

    # ========== Configs ========== #
    from Configs.mmseqsConfig import mmseqsExecutableConfig

    protselect_plugin.addConfig(mmseqsExecutableConfig)

    from Configs.mafftConfig import mafftExecutableConfig

    protselect_plugin.addConfig(mafftExecutableConfig)

    from Configs.proteinmpnnConfig import proteinmpnnExecutableConfig

    protselect_plugin.addConfig(proteinmpnnExecutableConfig)

    from Configs.rosettaConfig import rosettaExecutableConfig

    protselect_plugin.addConfig(rosettaExecutableConfig)

    from Configs.pyrosettaConfig import pyrosettaExecutableConfig

    protselect_plugin.addConfig(pyrosettaExecutableConfig)

    from Configs.bioemuConfig import bioemuExecutableConfig

    protselect_plugin.addConfig(bioemuExecutableConfig)

    # ========== Pages ========== #
    from Pages.load_tables import load_page

    protselect_plugin.addPage(load_page)

    # pylint: enable=import-outside-toplevel

    # Return the plugin
    return protselect_plugin


plugin = create_plugin()
