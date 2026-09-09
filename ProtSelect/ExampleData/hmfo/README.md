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

These were chosen as cluster representatives, so they are diverse by
construction and only merge at low identity:

| `min_seq_id` | Clusters |
| --- | --- |
| 0.40 | 5 |
| 0.50 | 10 |
| 0.60 and above | 10 (all singletons) |

**Sweep below 0.5 with this dataset** — the opposite of the lysozyme set, where
the interesting range is 0.45 to 0.8. That contrast is the point of the
threshold sweep block: the useful threshold depends entirely on how the set was
assembled, and guessing it is worse than looking.

## A caveat about the source

The family search these come from contains a great deal of fragmentary and
misannotated material. Of the 50,698 sequences, **22,632** are full-length GMC
oxidoreductases with a structure; the rest are short or lack the motif.

The `structural_trimmed_cluster` representatives in the source folder are a
particularly poor sampling frame: their median length is 82 residues and only 5
of the 2,454 are full-length family members. Selecting from them by sequence
diversity returns the most divergent entries, which are the junk — one early
attempt picked a `DGWEMDGRWMG` low-complexity repeat.

So these ten were filtered on length (450-650) and the FAD motif *before* any
diversity selection. Apply the same order to your own subsets.

## Cost

At ~540 residues these are roughly four times the lysozymes, so a CPU
ProteinMPNN pass takes minutes rather than seconds and Rosetta relax is a
cluster job. Use the lysozyme set to check that a flow is wired correctly, and
this one to see the pipeline behave on realistic input.

## Provenance

Structures and sequences come from `~/PhD/hmfo/hmfo` (trimmed AlphaFold models).
Organism names were resolved through the UniProt REST API; six of the ten
accessions have since been deleted from UniProtKB as "not part of a reference
proteome", so those carry the taxonomic mnemonic from their entry id rather than
a species name. `provenance.json` records the status of each.
