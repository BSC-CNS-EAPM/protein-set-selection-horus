# Example datasets

Two datasets, for two different purposes.

| | [`lysozyme/`](lysozyme/README.md) | [`hmfo/`](hmfo/README.md) |
| --- | --- | --- |
| What | Lysozyme C / alpha-lactalbumin | 5-hydroxymethylfurfural oxidases |
| Models | 10 | 10 |
| Residues | 121-130 | 503-577 |
| Size on disk | 832 KB | 3.3 MB |
| Source | AlphaFold DB (CC-BY-4.0) | a 50,698-sequence family search |
| Useful `min_seq_id` | 0.45-0.8 | below 0.5 |
| Good for | checking a flow is wired correctly | seeing the pipeline on realistic input |

Both follow the same layout: a `structures/` folder of PDBs, a `sequences.json`
keyed by the structure basenames, a `labels.json` of organisms for the
phylogenetic tree, and a `provenance.json`.

If you substitute your own data, keep the `sequences.json` keys identical to the
`structures/` file names: every block matches models by that name.

## Sources and licences

Both examples are third-party data redistributed with the plugin. The plugin's
own GPL-3.0 licence covers the code, not this data, and anyone redistributing
the plugin redistributes these files too.

- **Structures** are predicted models from the [AlphaFold Protein Structure
  Database](https://alphafold.ebi.ac.uk/), which states its data is available
  for academic and commercial use under
  [CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/); EMBL-EBI expects
  attribution. Cite Bertoni D. *et al.*, *AlphaFold Protein Structure Database
  2025: a redesigned interface and updated structural coverage*, Nucleic Acids
  Research (2025).
- **Sequences and organism names** come from UniProtKB accessions. UniProt
  applies [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) to all
  copyrightable parts of its databases. Cite The UniProt Consortium, *UniProt:
  the Universal Protein Knowledgebase in 2025*, Nucleic Acids Research
  53:D609-D617 (2025).

Per-set detail is in each folder's README. The lysozyme set records the
AlphaFold model version and a source URL per model. The HMFO set was recorded
without either and was traced afterwards. Eight of its ten models match their
current AlphaFold DB file exactly, and that file's URL is recorded. The release
they were downloaded from cannot be pinned, and two models have no retrievable
source file. The HMFO README sets out the evidence.

## Which to use

Start with **lysozyme**: at ~125 residues a CPU ProteinMPNN pass takes seconds,
so you find out quickly whether a flow is connected properly. Move to **hmfo**
once it is, to see behaviour at a realistic size — at ~540 residues that pass
takes minutes, and Rosetta relax becomes a cluster job.

## Choosing a threshold

The useful `min_seq_id` differs between the two sets (see the table). Run the
**MMseqs2 Threshold Sweep** block to choose one for your own data.
