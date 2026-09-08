"""
Module containing the ProteinMPNN score-reading block.

Turns a finished ProteinMPNN run into the per-model scores file that the
clustering and selection blocks consume.

``readScoresToDataFrame`` returns one row per sampled sequence, indexed by
(Model, Sample), so the scores have to be aggregated down to one value per
model. The reference workflow takes the mean.

The primary output is JSON rather than CSV on purpose. The CSV reader in
``sequence_io.load_scores`` takes a single pass and keeps the last value it
sees for a repeated name, so handing it a multi-row-per-model table would
silently select an arbitrary sample instead of the aggregate. The CSV output
here is the full table, for inspection rather than for wiring onward.
"""

from HorusAPI import PluginBlock, PluginVariable, VariableTypes
from sequence_io import read_sequences, require_local, show_table_html

# ==========================#
# Variable inputs
# ==========================#
pmpnnFolder = PluginVariable(
    id="pmpnn_folder",
    name="ProteinMPNN folder",
    description="Folder produced by the ProteinMPNN Scoring block.",
    type=VariableTypes.FOLDER,
)
sequencesFile = PluginVariable(
    id="sequences_file",
    name="Sequences file (optional)",
    description="Restrict the output to models present in this sequences file. "
    "Useful when the structures folder held more models than the dataset.",
    type=VariableTypes.FILE,
    allowedValues=["fasta", "fa", "faa", "json"],
    required=False,
)

# ==========================#
# Variables (parameters)
# ==========================#
aggregationVariable = PluginVariable(
    id="aggregation",
    name="Aggregation",
    description="How to reduce the per-sample scores to one value per model. The "
    "reference workflow uses the mean; 'min' takes the single best sample.",
    type=VariableTypes.STRING_LIST,
    defaultValue="mean",
    allowedValues=["mean", "min", "median", "max", "first", "last"],
)
scoreColumnVariable = PluginVariable(
    id="score_column",
    name="Score column",
    description="Which ProteinMPNN score to read. 'mean_score' is the per-sample "
    "mean negative log-likelihood; lower is better.",
    type=VariableTypes.STRING_LIST,
    defaultValue="mean_score",
    allowedValues=["mean_score", "global_mean_score"],
)
sourceFilterVariable = PluginVariable(
    id="source_filter",
    name="Source filter",
    description="Which rows to keep. 'score_only' rows are the scored input "
    "sequences; 'designed' rows are newly sampled sequences. 'all' keeps both.",
    type=VariableTypes.STRING_LIST,
    defaultValue="all",
    allowedValues=["all", "score_only", "designed"],
)
readUntilVariable = PluginVariable(
    id="read_until",
    name="Read at most N files",
    description="Stop after reading this many score files. 0 reads all of them; "
    "use a small number to peek at a large run in progress.",
    type=VariableTypes.INTEGER,
    defaultValue=0,
)

# ==========================#
# Variable outputs
# ==========================#
scoresFile = PluginVariable(
    id="scores_file",
    name="Scores file",
    description="JSON mapping each model to its aggregated score. This is the input "
    "the clustering and selection blocks expect.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
scoresTableFile = PluginVariable(
    id="scores_table_file",
    name="Scores table",
    description="CSV of the full per-sample ProteinMPNN table, for inspection.",
    type=VariableTypes.FILE,
    allowedValues=["csv"],
)


def read_proteinmpnn_scores(block: PluginBlock):
    """
    Read a ProteinMPNN run into a per-model scores file.

    Args:
        block (PluginBlock): The PluginBlock object representing the current block.
    """
    # pylint: disable=import-outside-toplevel
    import json
    import os

    # pylint: enable=import-outside-toplevel

    require_local(block, "Read ProteinMPNN Scores")

    folder = block.inputs.get(pmpnnFolder.id, None)
    if not folder or not os.path.isdir(folder):
        raise ValueError("A valid ProteinMPNN output folder must be provided.")

    aggregation = block.variables.get(aggregationVariable.id, "mean") or "mean"
    score_column = block.variables.get(scoreColumnVariable.id, "mean_score") or "mean_score"
    source_filter = block.variables.get(sourceFilterVariable.id, "all") or "all"
    read_until = int(block.variables.get(readUntilVariable.id, 0) or 0)

    # pylint: disable=import-outside-toplevel
    try:
        from bioprospecting.predictions.proteinMPNN import readScoresToDataFrame
    except ImportError as error:
        raise ValueError(
            "Could not import bioprospecting, which provides ProteinMPNN. It is "
            "installed with the plugin's dependencies; reinstall them from the "
            "Horus Plugin Manager if this persists."
        ) from error
    # pylint: enable=import-outside-toplevel

    dataframe = readScoresToDataFrame(folder, read_until=(read_until or None))
    if dataframe is None or dataframe.empty:
        raise ValueError(
            f"No ProteinMPNN scores were found in '{folder}'. Check that the "
            "scoring block finished and that its results were downloaded."
        )

    # The frame is indexed by (Model, Sample); reset so Model is a column we can
    # group on.
    table = dataframe.reset_index()

    if score_column not in table.columns:
        raise ValueError(
            f"The ProteinMPNN results have no '{score_column}' column. "
            f"Available columns: {sorted(table.columns)}."
        )

    if source_filter != "all" and "source" in table.columns:
        is_score_only = table["source"].astype(str).str.startswith("score_only")
        table = table[is_score_only] if source_filter == "score_only" else table[~is_score_only]
        if table.empty:
            raise ValueError(
                f"No rows are left after filtering for '{source_filter}' sources. "
                "Try the 'all' source filter."
            )

    grouped = table.groupby("Model")[score_column].agg(aggregation)
    scores = {str(model): float(value) for model, value in grouped.items()}

    sequences_path = block.inputs.get(sequencesFile.id, None)
    if sequences_path and sequences_path != "None":
        known = set(read_sequences(sequences_path))
        dropped = [model for model in scores if model not in known]
        scores = {model: value for model, value in scores.items() if model in known}
        if dropped:
            print(f"Dropped {len(dropped)} model(s) absent from the sequences file "
                  f"(e.g. {dropped[:3]}).")
        if not scores:
            raise ValueError(
                "No scored model appears in the sequences file. Check that the model "
                "names match the structure file names."
            )

    print(f"Read {len(table)} row(s) for {len(scores)} model(s); "
          f"aggregated '{score_column}' with '{aggregation}'.")

    scores_output = "proteinmpnn_scores.json"
    with open(scores_output, "w") as jf:
        json.dump(scores, jf, indent=2)

    table_output = "proteinmpnn_scores_table.csv"
    table.to_csv(table_output, index=False)

    ranked = sorted(scores.items(), key=lambda item: item[1])
    show_table_html(
        [(model, f"{value:.4f}") for model, value in ranked],
        ["Model", score_column],
        f"ProteinMPNN scores ({aggregation}, lower is better)",
    )

    block.setOutput(scoresFile.id, scores_output)
    block.setOutput(scoresTableFile.id, table_output)


readProteinMPNNScoresBlock = PluginBlock(
    category="ProteinMPNN",
    name="Read ProteinMPNN Scores",
    id="read_proteinmpnn_scores",
    description="Aggregate a ProteinMPNN run into a per-model scores file for the "
    "clustering and selection blocks.",
    inputs=[pmpnnFolder, sequencesFile],
    variables=[
        aggregationVariable,
        scoreColumnVariable,
        sourceFilterVariable,
        readUntilVariable,
    ],
    outputs=[scoresFile, scoresTableFile],
    action=read_proteinmpnn_scores,
)
