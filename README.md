# Protein Set Selection — a Horus plugin

Pick a small, expressible, structurally diverse subset out of a large protein
family, end to end in the Horus UI.

The pipeline scores AlphaFold models with ProteinMPNN, clusters the family with
MMseqs2 across a sweep of identity thresholds, keeps the best-scoring
representative of each cluster, relaxes the survivors with Rosetta, samples
their conformational ensembles with BioEmu, ranks what is left on a Pareto
front, and codon-optimises the winners for expression.

The plugin is family-agnostic: every block takes a sequences FASTA/JSON, a
folder of structures, or a scores file. The workflow was developed for
unspecific peroxygenases, but nothing in the blocks assumes it, and the shipped
datasets are lysozymes and HMFOs.

## Documentation

The [documentation](https://bsc-cns-eapm.github.io/protein-set-selection-horus/)
covers installation, the external tools, setting up SLURM cluster remotes, the
workflow and the preset flow, and has a reference page for every block's inputs,
parameters and outputs.

## The pipeline

| Stage | Blocks |
| --- | --- |
| Score | ProteinMPNN Scoring, Read ProteinMPNN Scores |
| Cluster | MMseqs2 Clustering (runs locally or as a SLURM job), MMseqs2 Threshold Sweep |
| Select | Select Cluster Representatives, Sequence Length Distribution |
| Prepare | Trim AlphaFold Models, Collect Selected Structures |
| Relax | Rosetta Relax, Analyse Rosetta Relax |
| Sample | BioEmu Sampling, Analyse BioEmu |
| Rank | Pareto Selection |
| Express | CodonTransformer |
| Inspect | Multiple Sequence Alignment (MAFFT), Phylogenetic Tree |

A prebuilt flow wiring all of them together ships in `ProtSelect/Flows/` and
appears in Horus as a preset, along with example datasets in
`ProtSelect/ExampleData/` so it can be run out of the box.

ProteinMPNN can score with the vanilla weights, the soluble weights or both.
Select Cluster Representatives then keeps the union and labels each model
`vanilla only`, `soluble only` or `common`.

## Installation

Download `protselect-<version>.hp` from the
[releases page](https://github.com/BSC-CNS-EAPM/protein-set-selection-horus/releases),
then in Horus: **Plugins → Install plugin** and select the file.

Horus installs the Python dependencies listed in `plugin.meta` into a private
`ProtSelect/deps/` folder. Dependency installation does not run when Horus
starts in desktop mode — use the Plugin Manager button, or start Horus with
`--server`.

The external tools (MMseqs2, MAFFT, PyRosetta, BioEmu, CodonTransformer,
Rosetta, SMOG2) are not pip-installable into that folder. After installing the
plugin, open the **Environment Setup** page it adds: it reports which tools are
present, installs the ones it can, and saves the resolved paths into the plugin
configuration. `./install_deps.sh` does the same from a terminal, asking before
each install (`--check` only reports).

## Development

Point Horus at this checkout instead of installing a built artifact:

```bash
cd /path/to/horus
HORUS_PLUGINS_DIR=/path/to/protein-set-selection-horus python Horus.py --debug --server
```

Build a distributable artifact:

```bash
./build_plugin.sh          # produces protselect-<git tag>.hp
```

Releases are cut by pushing a tag (or running the **Build Plugin** workflow),
which builds the `.hp` and attaches it to a GitHub release.

Build the documentation locally:

```bash
micromamba create -f Devtools/Environment/docs.yaml
micromamba activate protselect_docs
sphinx-build -b html -W docs docs/build/html
```

## Repository layout

```
ProtSelect/                 the plugin root (this is what gets zipped)
├── plugin.meta             metadata and pip dependencies
├── ProtSelect.py           entry point; registers blocks, configs and pages
├── Flows/                  prebuilt flow presets
├── ExampleData/            runnable example datasets (lysozyme, hmfo)
├── Pages/                  HTML for the plugin's pages
└── Include/                plugin source
    ├── Blocks/             one module per block
    ├── Configs/            executable and environment paths
    ├── Pages/              page endpoints
    ├── sequence_io.py      shared FASTA/JSON/scores IO
    ├── env_manager.py      external tool detection and installation
    └── utils.py            SLURM and local job submission
docs/                       Sphinx documentation site
```

## Relationship to EAPM-plugins

The blocks are derived from
[EAPM-plugins](https://github.com/BSC-CNS-EAPM/EAPM-plugins). The plugin depends
on [bioprospecting-horus](https://github.com/BSC-CNS-EAPM/bioprospecting-horus)
for the ProteinMPNN, MAFFT and CodonTransformer backends.

## Licence

GPL-3.0, inherited from EAPM-plugins, from which the blocks are derived.
See [LICENSE](LICENSE).
