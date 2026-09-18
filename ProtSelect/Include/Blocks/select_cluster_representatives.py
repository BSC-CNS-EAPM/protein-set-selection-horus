"""
Module containing the cluster-representative selection block.

Reproduces the selection step of the reference workflow: rank the clusters by
the best score among their members, keep the top N, and take the best-scoring
member of each as its representative.

The workflow does this twice, once per ProteinMPNN weight set, and keeps the
union. Rather than two copies of this block feeding a third that merges them,
both score sets are inputs here: give one and you get a plain selection, give
both and you get the union, labelled by which set chose each model.
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
vanillaScoresFile = PluginVariable(
    id="vanilla_scores_file",
    name="Vanilla scores",
    description="Per-model scores under the vanilla ProteinMPNN weights: a JSON file "
    "mapping model name to score, or a CSV with a name and a score column. Give "
    "this, the soluble scores, or both.",
    type=VariableTypes.FILE,
    allowedValues=["json", "csv"],
    required=False,
)
solubleScoresFile = PluginVariable(
    id="soluble_scores_file",
    name="Soluble scores",
    description="Per-model scores under the soluble ProteinMPNN weights. Selected "
    "independently of the vanilla scores; with both given the result is the union.",
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
    description="How to combine the two selections when both score sets are given. "
    "'both' keeps the union; 'vanilla' or 'soluble' keep only that one.",
    type=VariableTypes.STRING_LIST,
    defaultValue="both",
    allowedValues=["both", "vanilla", "soluble"],
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
    description="JSON mapping each selected model to its score. With both score sets, "
    "the score from the set that selected it (the vanilla one, when both did).",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
originFile = PluginVariable(
    id="origin_file",
    name="Origin",
    description="JSON labelling each selected model 'vanilla only', 'soluble only' or "
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

    def given(variable):
        path = block.inputs.get(variable.id, None)
        return path if path and path != "None" and os.path.isfile(path) else None

    vanilla_path = given(vanillaScoresFile)
    soluble_path = given(solubleScoresFile)
    if not vanilla_path and not soluble_path:
        raise ValueError(
            "No scores were provided. Connect the vanilla scores, the soluble "
            "scores, or both."
        )

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

    vanilla_models, vanilla_scores, vanilla_rows = [], {}, []
    soluble_models, soluble_scores, soluble_rows = [], {}, []
    print(f"Ranking {len(clusters)} clusters...")
    if vanilla_path:
        vanilla_models, vanilla_scores, vanilla_rows = _select_one(
            clusters, load_scores(vanilla_path), top_n, maximize
        )
        print(f"  vanilla scores selected {len(vanilla_models)} representatives.")
    if soluble_path:
        soluble_models, soluble_scores, soluble_rows = _select_one(
            clusters, load_scores(soluble_path), top_n, maximize
        )
        print(f"  soluble scores selected {len(soluble_models)} representatives.")

    vanilla_set, soluble_set = set(vanilla_models), set(soluble_models)
    both_given = bool(vanilla_path and soluble_path)

    if both_given and combine_as == "vanilla":
        chosen = list(vanilla_models)
    elif both_given and combine_as == "soluble":
        chosen = list(soluble_models)
    else:
        # Union, keeping the vanilla order and appending what only the soluble
        # set found. With a single set given this is just that set.
        chosen = list(vanilla_models) + [m for m in soluble_models if m not in vanilla_set]

    if not chosen:
        raise ValueError(
            "No representatives were selected. Check that the model names in the "
            "scores file match those in the clusters file."
        )

    def origin_of(model):
        if model in vanilla_set and model in soluble_set:
            return "common"
        return "vanilla only" if model in vanilla_set else "soluble only"

    origin = {model: origin_of(model) for model in chosen}
    counts: dict = {}
    for label in origin.values():
        counts[label] = counts.get(label, 0) + 1
    print(f"Selected {len(chosen)} model(s)"
          + (f" ({', '.join(f'{k}: {v}' for k, v in sorted(counts.items()))})"
             if both_given else ""))

    combined_scores = {m: vanilla_scores.get(m, soluble_scores.get(m)) for m in chosen}

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
        for row in vanilla_rows:
            writer.writerow({**row, "score_set": "vanilla"})
        for row in soluble_rows:
            writer.writerow({**row, "score_set": "soluble"})

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
    description="Keep the best-scoring member of each of the top-N clusters. Give the "
    "vanilla and soluble scores to select from both and keep the union.",
    inputs=[clustersFile, vanillaScoresFile, solubleScoresFile, sequencesFile],
    variables=[topNVariable, maximizeVariable, selectionVariable],
    outputs=[selectedModelsFile, selectedSequencesFile, selectedScoresFile,
             originFile, selectionTableFile],
    action=select_representatives,
)
