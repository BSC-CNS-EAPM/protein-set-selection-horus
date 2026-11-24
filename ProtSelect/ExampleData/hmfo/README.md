# HMFO example dataset

Ten 5-hydroxymethylfurfural oxidases (HMFOs), drawn from a 50,698-sequence
search of the family. These are real working data at realistic size, in contrast
to the small [lysozyme set](../lysozyme/README.md).

```
structures/        10 trimmed AlphaFold models, one PDB per protein
sequences.json     {model: sequence}, keyed by the structure basenames
labels.json        {model: organism}, for the phylogenetic tree
provenance.json    accession, organism, length and source cluster size
```

## Contents

All ten are genuine GMC oxidoreductases, 503-577 residues, each carrying the
family's FAD-binding Rossmann motif (`YDFIIVGAGSAG…`) near the N terminus.

| Model | Organism | Residues | Represents |
| --- | --- | --- | --- |
| `A0A1I7JNY4` | *Halomonas korlensis* | 532 | 4252 sequences |
| `A0A4Q5P860` | unclassified Burkholderiales | 577 | 1618 |
| `A0A264TCW4` | unclassified Gammaproteobacteria | 543 | 1393 |
| `A0A5C1NM78` | *Halomonas binhaiensis* | 548 | 869 |
| `A0A182E4A1` | *Onchocerca ochengi* | 560 | 602 |
| `A0A1X0T8Y9` | unclassified Hyphomicrobiales | 531 | 491 |
| `A0A4Q7S5X9` | *Cupriavidus agavae* | 545 | 475 |
| `A3YC68` | unclassified Gammaproteobacteria | 543 | 471 |
| `A0A1A0KLH1` | unclassified Mycobacteriaceae | 503 | 401 |
| `A0A5B8EKM0` | unclassified Actinomycetes | 524 | 288 |

"Represents" is the size of the 50%-identity sequence cluster each one heads, so
the ten together stand for roughly 11,000 of the family's members.

## Clustering behaviour

| `min_seq_id` | Clusters |
| --- | --- |
| 0.40 | 5 |
| 0.50 | 10 |
| 0.60 and above | 10 (all singletons) |

**Sweep below 0.5 with this dataset.**

The ten were selected after filtering for length (450-650 residues) and the
FAD-binding motif.

## Cost

A CPU ProteinMPNN pass takes minutes rather than seconds, and Rosetta relax is a
cluster job.

## Provenance

Trimmed AlphaFold models of the family. Organism names were resolved through the
UniProt REST API; six of the ten accessions have since been deleted from
UniProtKB as "not part of a reference proteome", so those carry the taxonomic
mnemonic from their entry id rather than a species name. `provenance.json`
records the status of each.

The ten were drawn from a 50,698-sequence search of the family, filtered for
length (450-650 residues) and the FAD-binding motif, then kept as the heads of
the largest 50%-identity clusters. The structure files hold ATOM records only;
the per-atom B-factor column carries the model's pLDDT.

They are taken **unchanged** from the project's family-wide set of trimmed
AlphaFold models — 50,699 structures, one per sequence, assembled in February
2025 — and each of the ten here is byte-identical to its counterpart there. The
trimming was applied before that set was stored, so the models in this folder
have never been edited by the plugin.

## Sources and attribution

This example is third-party data redistributed with the plugin, not data the
plugin's authors produced.

- **Structures**: predicted models from the AlphaFold Protein Structure
  Database (https://alphafold.ebi.ac.uk/), trimmed. That database states its
  data is "available for academic and commercial use, under a CC-BY-4.0
  licence", and EMBL-EBI expects attribution in work that uses it. Cite
  AlphaFold DB as its site asks, and DeepMind's AlphaFold papers for the
  method. The AlphaFold DB release these models came from was not recorded, and
  the trimmed files no longer carry the header that would say.
- **Sequences and organism names**: UniProtKB accessions
  (https://www.uniprot.org/). Check UniProt's current licence and citation
  terms at https://www.uniprot.org/help/license before redistributing them
  further.
- **Status**: six of the ten accessions are no longer live in UniProtKB. The
  copies here are a snapshot, kept deliberately so the example stays runnable;
  they are not a current view of the database.

Anyone redistributing this plugin redistributes these files too. The plugin's
own GPL-3.0 licence covers the code, not this data.
