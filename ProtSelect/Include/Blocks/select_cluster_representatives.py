"""
Module containing the cluster-representative selection block.

Reproduces the selection step of the reference workflow: rank the clusters by
the best score among their members, keep the top N, and take the best-scoring
member of each as its representative.

The workflow does this twice, once per ProteinMPNN weight set, and keeps the
union. Rather than two copies of this block feeding a third that merges them,
the second score set is an optional input here: give one and you get a plain
selection, give two and you get the union, labelled by which set each model came
from.
"""

from HorusAPI import PluginBlock, PluginVariable, VariableTypes
from sequence_io import load_scores, read_sequences, write_fasta

# ==========================#
# Variable inputs
# ==========================#
clustersFile = PluginVariable(
    id="clusters_file",
    name="Clusters file",
    description="JSON mapping each cluster representative to its member list, as "
    "produced by the MMseqs2 Clustering block.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
scoresFile = PluginVariable(
    id="scores_file",
    name="Scores file",
    description="Per-model scores. Either a JSON file mapping model name to score, "
    "or a CSV with a name column and a score column.",
    type=VariableTypes.FILE,
    allowedValues=["json", "csv"],
)
secondScoresFile = PluginVariable(
    id="scores_file_2",
    name="Second scores file (optional)",
    description="A second set of scores, selected independently. The result is the "
    "union of the two selections. The reference workflow uses the ProteinMPNN "
    "vanilla and soluble scores here.",
    type=VariableTypes.FILE,
    allowedValues=["json", "csv"],
    required=False,
)
sequencesFile = PluginVariable(
    id="sequences_file",
    name="Sequences file (optional)",
    description="Sequences of the clustered models. When given, the selected "
    "sequences are written out as a FASTA for the rest of the pipeline.",
    type=VariableTypes.FILE,
    allowedValues=["fasta", "fa", "faa", "json"],
    required=False,
)

# ==========================#
# Variables (parameters)
# ==========================#
topNVariable = PluginVariable(
    id="top_n_clusters",
    name="Top N clusters",
    description="Number of best-scoring clusters to keep, per score set.",
    type=VariableTypes.INTEGER,
    defaultValue=100,
)
maximizeVariable = PluginVariable(
    id="maximize",
    name="Maximize score",
    description="If enabled, higher scores are better. By default lower scores are "
    "better, as with ProteinMPNN scores.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)
selectionVariable = PluginVariable(
    id="model_selection",
    name="Combine as",
    description="How to combine the two selections when a second score set is "
    "given. 'both' keeps the union; 'first' or 'second' keep only that one.",
    type=VariableTypes.STRING_LIST,
    defaultValue="both",
    allowedValues=["both", "first", "second"],
)

# ==========================#
# Variable outputs
# ==========================#
selectedModelsFile = PluginVariable(
    id="selected_models_file",
    name="Selected models",
    description="JSON list of the selected model names.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
selectedSequencesFile = PluginVariable(
    id="selected_sequences_file",
    name="Selected sequences",
    description="FASTA of the selected sequences (only when a sequences file is given).",
    type=VariableTypes.FILE,
    allowedValues=["fasta"],
)
selectedScoresFile = PluginVariable(
    id="selected_scores_file",
    name="Selected scores",
    description="JSON mapping each selected model to its score. With two score sets, "
    "the score from the set that selected it (the first, when both did).",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
originFile = PluginVariable(
    id="origin_file",
    name="Origin",
    description="JSON labelling each selected model 'first only', 'second only' or "
    "'common'. Feed this to the Pareto Selection block to colour its plot.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
selectionTableFile = PluginVariable(
    id="selection_table_file",
    name="Selection table",
    description="CSV of the selection: cluster, chosen model, score, cluster size "
    "and which score set chose it.",
    type=VariableTypes.FILE,
    allowedValues=["csv"],
)


def _select_one(clusters, scores, top_n, maximize):
    """
    Rank clusters by their best member score and take that member from the top N.

    Returns (ordered model names, {model: score}, table rows). Clusters with no
    scored member sink to the bottom of the ranking and are then skipped, so a
    partially scored clustering degrades rather than failing.
    """
    inf = float("inf")

    def cluster_best(members):
        values = [scores[m] for m in members if m in scores]
        if not values:
            return None
        return max(values) if maximize else min(values)

    def sort_key(cluster_id):
        best = cluster_best(clusters[cluster_id])
        if best is None:
            return inf
        return -best if maximize else best

    ordered = sorted(clusters.keys(), key=sort_key)[: int(top_n)]

    models, model_scores, rows = [], {}, []
    for cluster_id in ordered:
        members = clusters[cluster_id]
        scored = [m for m in members if m in scores]
        if not scored:
            continue

        best_model = (max if maximize else min)(scored, key=lambda m: scores[m])
        models.append(best_model)
        model_scores[best_model] = scores[best_model]
        rows.append({
            "cluster_representative": cluster_id,
            "best_model": best_model,
            "best_score": scores[best_model],
            "cluster_size": len(members),
            "scored_members": len(scored),
        })
    return models, model_scores, rows


def select_representatives(block: PluginBlock):
    """
    Select one representative per cluster, optionally from two score sets.

    Args:
        block (PluginBlock): The PluginBlock object representing the current block.
    """
    # pylint: disable=import-outside-toplevel
    import csv
    import json
    import os

    # pylint: enable=import-outside-toplevel

    clusters_path = block.inputs.get(clustersFile.id, None)
    if not clusters_path or not os.path.isfile(clusters_path):
        raise ValueError("A valid clusters JSON file must be provided.")

    scores_path = block.inputs.get(scoresFile.id, None)
    if not scores_path or not os.path.isfile(scores_path):
        raise ValueError("A valid scores file (JSON or CSV) must be provided.")

    second_path = block.inputs.get(secondScoresFile.id, None)
    if second_path == "None":
        second_path = None

    sequences_path = block.inputs.get(sequencesFile.id, None)
    if sequences_path == "None":
        sequences_path = None

    top_n = block.variables.get(topNVariable.id, 100)
    maximize = block.variables.get(maximizeVariable.id, False)
    combine_as = block.variables.get(selectionVariable.id, "both") or "both"

    with open(clusters_path) as jf:
        clusters = json.load(jf)
    if not isinstance(clusters, dict):
        raise ValueError("The clusters file must map representatives to member lists.")

    first_models, first_scores, first_rows = _select_one(
        clusters, load_scores(scores_path), top_n, maximize
    )
    print(f"Ranked {len(clusters)} clusters; first score set selected "
          f"{len(first_models)} representatives.")

    second_models, second_scores, second_rows = [], {}, []
    if second_path and os.path.isfile(second_path):
        second_models, second_scores, second_rows = _select_one(
            clusters, load_scores(second_path), top_n, maximize
        )
        print(f"Second score set selected {len(second_models)} representatives.")

    first_set, second_set = set(first_models), set(second_models)

    if not second_models or combine_as == "first":
        chosen = list(first_models)
    elif combine_as == "second":
        chosen = list(second_models)
    else:
        # Union, keeping the first set's order and appending what only the
        # second set found.
        chosen = list(first_models) + [m for m in second_models if m not in first_set]

    if not chosen:
        raise ValueError(
            "No representatives were selected. Check that the model names in the "
            "scores file match those in the clusters file."
        )

    def origin_of(model):
        if second_models:
            if model in first_set and model in second_set:
                return "common"
            return "first only" if model in first_set else "second only"
        return "first only"

    origin = {model: origin_of(model) for model in chosen}
    counts: dict = {}
    for label in origin.values():
        counts[label] = counts.get(label, 0) + 1
    print(f"Selected {len(chosen)} model(s)"
          + (f" ({', '.join(f'{k}: {v}' for k, v in sorted(counts.items()))})"
             if second_models else ""))

    combined_scores = {m: first_scores.get(m, second_scores.get(m)) for m in chosen}

    models_output = "selected_models.json"
    with open(models_output, "w") as jf:
        json.dump(chosen, jf, indent=2)

    scores_output = "selected_scores.json"
    with open(scores_output, "w") as jf:
        json.dump(combined_scores, jf, indent=2)

    origin_output = "selected_origin.json"
    with open(origin_output, "w") as jf:
        json.dump(origin, jf, indent=2)

    table_output = "selection_table.csv"
    with open(table_output, "w", newline="") as cf:
        writer = csv.DictWriter(
            cf,
            fieldnames=["cluster_representative", "best_model", "best_score",
                        "cluster_size", "scored_members", "score_set"],
        )
        writer.writeheader()
        for row in first_rows:
            writer.writerow({**row, "score_set": "first"})
        for row in second_rows:
            writer.writerow({**row, "score_set": "second"})

    block.setOutput(selectedModelsFile.id, models_output)
    block.setOutput(selectedScoresFile.id, scores_output)
    block.setOutput(originFile.id, origin_output)
    block.setOutput(selectionTableFile.id, table_output)

    if sequences_path and os.path.isfile(sequences_path):
        sequences = read_sequences(sequences_path)
        missing = [m for m in chosen if m not in sequences]
        if missing:
            print(f"Warning: {len(missing)} selected model(s) are missing from the "
                  f"sequences file (e.g. {missing[:3]}).")
        selected_sequences_output = write_fasta(
            {m: sequences[m] for m in chosen if m in sequences},
            "selected_sequences.fasta",
        )
        block.setOutput(selectedSequencesFile.id, selected_sequences_output)


selectClusterRepresentativesBlock = PluginBlock(
    category="Clustering & Selection",
    name="Select Cluster Representatives",
    id="select_cluster_representatives",
    description="Keep the best-scoring member of each of the top-N clusters. Give a "
    "second score set to select from both and keep the union.",
    inputs=[clustersFile, scoresFile, secondScoresFile, sequencesFile],
    variables=[topNVariable, maximizeVariable, selectionVariable],
    outputs=[selectedModelsFile, selectedSequencesFile, selectedScoresFile,
             originFile, selectionTableFile],
    action=select_representatives,
)
