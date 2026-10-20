# Lysozyme example dataset

Ten members of the lysozyme C / alpha-lactalbumin family, enough to run the
whole pipeline end to end in a few minutes.

```
structures/        10 trimmed AlphaFold models, one PDB per protein
sequences.json     {model: sequence}, keyed by the structure basenames
labels.json        {model: organism}, for the phylogenetic tree
provenance.json    accession, organism, model version and source URL per model
```

## Clustering behaviour

| `min_seq_id` | Clusters | Groups |
| --- | --- | --- |
| 0.30 | 1 | everything together |
| 0.45 | 1 | everything together |
| 0.60 | 3 | alpha-lactalbumins \| horse lysozyme \| bird + human lysozymes |
| 0.80 | 5 | the above, split further by species |

**Use `min_seq_id` around 0.7 with this dataset.**

## Contents

| Model | Organism | Protein | Residues |
| --- | --- | --- | --- |
| `LYSC_CHICK` | *Gallus gallus* | Lysozyme C | 130 |
| `LYSC_COTJA` | *Coturnix japonica* | Lysozyme C | 130 |
| `LYSC_MELGA` | *Meleagris gallopavo* | Lysozyme C | 129 |
| `LYSC_COLVI` | *Colinus virginianus* | Lysozyme C | 129 |
| `LYSC_HUMAN` | *Homo sapiens* | Lysozyme C | 130 |
| `LYSC1_HORSE` | *Equus caballus* | Lysozyme C, milk isozyme | 129 |
| `LALBA_BOVIN` | *Bos taurus* | Alpha-lactalbumin | 121 |
| `LALBA_CAPHI` | *Capra hircus* | Alpha-lactalbumin | 122 |
| `LALBA_HUMAN` | *Homo sapiens* | Alpha-lactalbumin | 122 |
| `LALBA_SHEEP` | *Ovis aries* | Alpha-lactalbumin | 121 |

## Provenance

Downloaded from the [AlphaFold Protein Structure Database](https://alphafold.ebi.ac.uk/)
(model version 6) and trimmed with this plugin's own **Trim AlphaFold Models**
block at a pLDDT threshold of 90, which removes the low-confidence signal
peptides and leaves the mature protein.

The sequences are read back from the trimmed CA traces, so they match the
structures exactly rather than the full UniProt entries.

AlphaFold DB data is released by DeepMind and EMBL-EBI under
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). `provenance.json`
records the accession and source URL for each model.
