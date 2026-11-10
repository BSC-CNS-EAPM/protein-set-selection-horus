# Protein Set Selection — a Horus plugin

Prioritise a small subset of a protein family for experimental testing, using
sequence clustering and computational scores in the Horus UI.

The pipeline scores AlphaFold models with ProteinMPNN, clusters the family with
MMseqs2 at a chosen identity threshold, selects representatives separately for
each ProteinMPNN weight set, relaxes them with Rosetta, samples conformations
with BioEmu, and selects a shortlist using Pareto fronts and crowding distance.
CodonTransformer generates DNA predictions for a chosen host. An optional
threshold-sweep block helps compare clustering thresholds. These computational
criteria do not establish expression, stability or biological function.

The plugin is family-agnostic: every block takes a sequences FASTA/JSON, a
folder of structures, or a scores file. The workflow was developed for
unspecific peroxygenases, but nothing in the blocks assumes it, and the shipped
datasets contain lysozyme-family proteins and HMFO-search candidates.

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

A prebuilt flow connects the main pipeline in `ProtSelect/Flows/` and appears
in Horus as **ProteSel Pipeline**. Threshold Sweep, Sequence Length Distribution
and Trim AlphaFold Models are additional blocks outside that preset. Example
datasets ship in `ProtSelect/ExampleData/`; install and configure the required
tools before running them. The preset's alignment and tree describe the cluster
representatives, while CodonTransformer receives the final Pareto selection.

ProteinMPNN can score with the vanilla weights, the soluble weights or both.
Select Cluster Representatives then keeps the union and labels each model
`vanilla only`, `soluble only` or `common`.

## Installation

The [installation guide](https://bsc-cns-eapm.github.io/protein-set-selection-horus/installation.html)
walks through every step. In short:

1. **Install Horus.** Obtain a package for your platform from the
   [Horus releases](https://gitlab.bsc.es/eapm/horus/-/releases). To use a
   browser, connect to a Horus server configured with this plugin and its
   tools. The [public demo](https://horus.bsc.es/demo) is for exploring Horus;
   it is not a preconfigured Protein Set Selection service.
2. **Install the plugin.** Download `protselect-<version>.hp` from the
   [releases page](https://github.com/BSC-CNS-EAPM/protein-set-selection-horus/releases),
   then in Horus: **Plugins → Install plugin** and select the file. Horus
   installs the plugin's Python dependencies with it.
3. **Install the external tools.** MMseqs2, MAFFT, PyTorch, PyRosetta, BioEmu,
   CodonTransformer, Rosetta and SMOG2 are installed separately as needed.
   Open **Extensions → Environment Setup** to inspect local tools, or clone
   this repository and run its installer from a terminal:

   ```bash
   ./install_deps.sh --check    # report only
   ./install_deps.sh            # ask before each install
   ```

   It needs micromamba, mamba or conda, and puts the tools that need an
   environment into a single one, `protselect`. It also installs Rosetta (after
   you confirm non-commercial use) and SMOG2. See
   [the dependency installer](https://bsc-cns-eapm.github.io/protein-set-selection-horus/install_deps.html)
   for every option.
4. **Point the plugin at the tools.** Open **Horus → Plugins → Protein Set
   Selection** and select **Local**. Review any values saved through
   **Save detected paths** or the installer's `--config FILE` option. The
   [configuration guide](https://bsc-cns-eapm.github.io/protein-set-selection-horus/configuration.html)
   explains detection limitations and the separate Rosetta/BioEmu block
   settings; SMOG2 must be on Horus's `PATH`.
5. **Set up your cluster** as a Horus remote, if you use one, and run the
   **ProteSel Pipeline** preset on the lysozyme example to check everything.

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
which builds the `.hp` and attaches it to a GitHub release. The local build
script uses `git describe --tags` (falling back to `0.0.1`), updates
`ProtSelect/plugin.meta`, and removes existing `.hp` files in the current
folder. On macOS it needs GNU sed (`gsed`), as well as `zip` and `unzip`.

Build the documentation locally:

```bash
micromamba create -f Devtools/Environment/docs.yaml
micromamba activate protselect_docs
python3 -m unittest discover -s Devtools -p 'test_docs_reference.py'
sphinx-build -b html -W docs docs/build/html
```

The reference is regenerated from source declarations on every build. Correct
block descriptions in `ProtSelect/Include/Blocks/` and configuration descriptions
in `ProtSelect/Include/Configs/`; do not edit ignored `docs/reference/` outputs.

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
