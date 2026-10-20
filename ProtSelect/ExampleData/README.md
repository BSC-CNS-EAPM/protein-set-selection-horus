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

## Which to use

Start with **lysozyme**: at ~125 residues a CPU ProteinMPNN pass takes seconds,
so you find out quickly whether a flow is connected properly. Move to **hmfo**
once it is, to see behaviour at a realistic size — at ~540 residues that pass
takes minutes, and Rosetta relax becomes a cluster job.

## Choosing a threshold

The useful `min_seq_id` differs between the two sets (see the table). Run the
**MMseqs2 Threshold Sweep** block to choose one for your own data.
