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

**The model name is the join key for the whole pipeline.** The ProteinMPNN
scores, the MMseqs2 clusters, the structure file names and the rows of the
Rosetta and BioEmu metrics tables are all keyed by it. If you substitute your own
data, keep the `sequences.json` keys identical to the `structures/` file names.

## Which to use

Start with **lysozyme**: at ~125 residues a CPU ProteinMPNN pass takes seconds,
so you find out quickly whether a flow is connected properly. Move to **hmfo**
once it is, to see behaviour at a realistic size — at ~540 residues that pass
takes minutes, and Rosetta relax becomes a cluster job.

## On choosing a threshold

The two sets cluster in opposite directions. The lysozymes resolve into
subfamilies as `min_seq_id` rises from 0.45 to 0.8; the HMFOs, picked as cluster
representatives, are all singletons above 0.5 and only merge below it.

That is the argument for the **MMseqs2 Threshold Sweep** block. There is no
generally correct identity threshold: it depends on how the set was assembled,
and the reference notebook's 0.45 is right for several thousand peroxygenases
and wrong for both of these. Run the sweep and read the plot.
