# HMFO example dataset

Ten 5-hydroxymethylfurfural oxidases (HMFOs), drawn from a 50,698-sequence
search of the family. These are real working data at realistic size, in contrast
to the small [lysozyme set](../lysozyme/README.md).

```
structures/        10 trimmed AlphaFold models, one PDB per protein
sequences.json     {model: sequence}, keyed by the structure basenames
labels.json        {model: organism}, for the phylogenetic tree
provenance.json    accession, organism, length, source cluster size, UniProtKB
                   residues kept and the verified AlphaFold DB file
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
UniProtKB, five as "not part of a reference proteome" and `A0A1A0KLH1` as
"excluded proteome", so those carry the taxonomic mnemonic from their entry id
rather than a species name. `provenance.json` records the status of each.

The ten were drawn from a 50,698-sequence search of the family, filtered for
length (450-650 residues) and the FAD-binding motif, then kept as the heads of
the largest 50%-identity clusters. The structure files hold ATOM records only;
the per-atom B-factor column carries the model's pLDDT.

They are taken **unchanged** from the project's family-wide set of trimmed
AlphaFold models — 50,699 structures, one per sequence, assembled in February
2025 — and each of the ten here is byte-identical to its counterpart there. The
trimming was applied before that set was stored, so the models in this folder
have never been edited by the plugin.

### AlphaFold DB source, recovered 2026-11-26

When the set was assembled, nobody recorded which AlphaFold DB release the
models came from or the URL of each, and the trimmed files carry no header that
would say. The source was reconstructed afterwards, from the data alone:

1. **Accession.** The sequence read from each file's ATOM records occurs exactly
   once in the UniProtKB sequence of the accession the file is named after. For
   the six deleted entries, the sequence is UniProtKB's own archived entry
   (UniSave); every one of the ten has only ever had sequence version 1. For the
   four live entries, an exact peptide search of UniProtKB returns that same
   accession. The UniProtKB residues each file keeps are in `provenance.json`
   (`uniprot_residues`); the trimming removed 3-37 residues from the N terminus
   and 3-42 from the C terminus.
2. **AlphaFold DB file.** For eight of the ten, the current AlphaFold DB file
   `AF-<accession>-F1-model_v6.cif` was fetched. Its sequence is the full
   UniProtKB sequence. Over the residues kept here, every atom's coordinates and
   pLDDT are identical to the local file. That URL is recorded per model as
   `alphafold_url`.
3. **Release.** It cannot be pinned, because the coordinates are identical
   across releases. AlphaFold DB serves only the current file per entry (v1-v5
   return 404), so only v6 could be compared directly. AlphaFold DB's own list of
   the 9,203,041 entries whose coordinates changed in v4
   (`v4/v4_updated_accessions.txt` on its FTP) contains none of the ten, so v3
   and v4 coordinates are the same as each other. None of the eight appears in
   the current release's diff list (`diffs.ndjson.gz`), which AlphaFold DB
   records as changes since v4. The v6 files date their revisions v3 2022-06-01,
   v4 2022-09-30, v5 2025-03-31 and v6 2025-08-01. If the February 2025 assembly
   date above is right, the models were downloaded from v3 or v4, and v4 and v6
   coordinates are identical for these entries. Either way, the coordinates do
   not tell the releases apart. `provenance.json` therefore leaves
   `alphafold_download_version` null.

| Model | UniProtKB residues kept | AlphaFold DB file checked | Result |
| --- | --- | --- | --- |
| `A0A1I7JNY4` | 8-539 of 575 | `AF-A0A1I7JNY4-F1-model_v6.cif` | identical |
| `A0A4Q5P860` | 6-582 of 586 | `AF-A0A4Q5P860-F1-model_v6.cif` | identical |
| `A0A264TCW4` | 6-548 of 590 | none retrievable | removed from AlphaFold DB |
| `A0A5C1NM78` | 14-561 of 568 | `AF-A0A5C1NM78-F1-model_v6.cif` | identical |
| `A0A182E4A1` | 38-597 of 626 | `AF-A0A182E4A1-F1-model_v6.cif` | identical |
| `A0A1X0T8Y9` | 10-540 of 547 | `AF-A0A1X0T8Y9-F1-model_v6.cif` | identical |
| `A0A4Q7S5X9` | 6-550 of 555 | `AF-A0A4Q7S5X9-F1-model_v6.cif` | identical |
| `A3YC68` | 4-546 of 550 | `AF-A3YC68-F1-model_v6.cif` | identical |
| `A0A1A0KLH1` | 9-511 of 519 | none retrievable | removed from AlphaFold DB |
| `A0A5B8EKM0` | 6-529 of 532 | `AF-A0A5B8EKM0-F1-model_v6.cif` | identical |

Files are under `https://alphafold.ebi.ac.uk/files/`.

**Two models cannot be traced to a file.** `A0A1A0KLH1` and `A0A264TCW4` are
listed as `REMOVED` in AlphaFold DB's current diff. The API has no record of
either, and every `model_v1` to `model_v6` URL returns 404. Their accessions are
verified as above, but no AlphaFold DB file could be fetched to check their
coordinates against, so no URL is recorded for them. A copy would survive only
in an older full-database dump. The v4 dump on Google Cloud Storage
(`public-datasets-deepmind-alphafold-v4`) refuses anonymous reads.

The sequences of two deleted entries now sit under newer UniProtKB accessions
in the same UniParc record: `A0A264TCW4` under `A0ABX4G3Q8` (first public
2025-10-08) and `A0A5B8EKM0` under `A0ACN7CD59` (2026-09-02). Both are later
than the set's assembly, so neither is the source. Neither has an AlphaFold DB
entry as of 2026-11-26.

## Sources and attribution

This example is third-party data redistributed with the plugin, not data the
plugin's authors produced.

- **Structures**: predicted models from the AlphaFold Protein Structure
  Database (https://alphafold.ebi.ac.uk/), trimmed. That database states its
  data is "available for academic and commercial use, under a CC-BY-4.0
  licence", and EMBL-EBI expects attribution in work that uses it. Cite
  AlphaFold DB as its site asks, and DeepMind's AlphaFold papers for the
  method. Eight models are identical, over the residues kept, to the AlphaFold
  DB v6 file recorded for each in `provenance.json`. The release they were
  downloaded from cannot be pinned, and two models have no retrievable source
  file; see [AlphaFold DB source](#alphafold-db-source-recovered-2026-11-26).
- **Sequences and organism names**: UniProtKB accessions
  (https://www.uniprot.org/). UniProt applies the [Creative Commons Attribution
  4.0 International (CC BY 4.0)
  licence](https://creativecommons.org/licenses/by/4.0/) to all copyrightable
  parts of its databases. Cite The UniProt Consortium, *UniProt: the Universal
  Protein Knowledgebase in 2025*, Nucleic Acids Research 53:D609-D617 (2025).
- **Status**: six of the ten accessions are no longer live in UniProtKB. The
  copies here are a snapshot, kept deliberately so the example stays runnable;
  they are not a current view of the database.

Anyone redistributing this plugin redistributes these files too. The plugin's
own GPL-3.0 licence covers the code, not this data.
