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
vanillaScoresFile = PluginVariable(
    id="vanilla_scores_file",
    name="Vanilla scores",
    description="JSON mapping each model to its aggregated score under the vanilla "
    "ProteinMPNN weights. Set when the scoring run included the vanilla set.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
solubleScoresFile = PluginVariable(
    id="soluble_scores_file",
    name="Soluble scores",
    description="JSON mapping each model to its aggregated score under the soluble "
    "ProteinMPNN weights. Set when the scoring run included the soluble set.",
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

    sequences_path = block.inputs.get(sequencesFile.id, None)
    known = None
    if sequences_path and sequences_path != "None":
        known = set(read_sequences(sequences_path))

    def read_one(source_folder, label):
        """Aggregate one ProteinMPNN job folder into {model: score}."""
        dataframe = readScoresToDataFrame(source_folder, read_until=(read_until or None))
        if dataframe is None or dataframe.empty:
            raise ValueError(
                f"No ProteinMPNN scores were found in '{source_folder}'. Check that "
                "the scoring block finished and that its results were downloaded."
            )

        # The frame is indexed by (Model, Sample); reset so Model is a column we
        # can group on.
        frame = dataframe.reset_index()

        if score_column not in frame.columns:
            raise ValueError(
                f"The ProteinMPNN results have no '{score_column}' column. "
                f"Available columns: {sorted(frame.columns)}."
            )

        if source_filter != "all" and "source" in frame.columns:
            is_score_only = frame["source"].astype(str).str.startswith("score_only")
            frame = frame[is_score_only] if source_filter == "score_only" \
                else frame[~is_score_only]
            if frame.empty:
                raise ValueError(
                    f"No rows are left after filtering for '{source_filter}' sources. "
                    "Try the 'all' source filter."
                )

        grouped = frame.groupby("Model")[score_column].agg(aggregation)
        found = {str(model): float(value) for model, value in grouped.items()}

        if known is not None:
            dropped = [m for m in found if m not in known]
            found = {m: v for m, v in found.items() if m in known}
            if dropped:
                print(f"  {label}: dropped {len(dropped)} model(s) absent from the "
                      f"sequences file (e.g. {dropped[:3]}).")
            if not found:
                raise ValueError(
                    "No scored model appears in the sequences file. Check that the "
                    "model names match the structure file names."
                )

        print(f"  {label}: {len(frame)} row(s) for {len(found)} model(s)")
        frame.insert(0, "weight_set", label)
        return found, frame

    # The scoring block writes each weight set to a subfolder named after it,
    # which is what lets each one land on the matching output here.
    sets = [
        (label, os.path.join(folder, label))
        for label in ("vanilla", "soluble")
        if os.path.isdir(os.path.join(folder, label))
    ]
    if not sets:
        # A folder from before the subfolder layout, or from outside this
        # plugin. Its weight set cannot be read from the layout, so treat it as
        # vanilla -- the ProteinMPNN default -- and say so.
        print("No 'vanilla' or 'soluble' subfolder found; reading the folder "
              "itself and treating it as the vanilla weight set.")
        sets = [("vanilla", folder)]

    print(f"Reading {len(sets)} weight set(s), aggregating '{score_column}' "
          f"with '{aggregation}'...")

    results, frames = [], []
    for label, source_folder in sets:
        found, frame = read_one(source_folder, label)
        results.append((label, found))
        frames.append(frame)

    import pandas as pd  # pylint: disable=import-outside-toplevel

    table = pd.concat(frames, ignore_index=True)
    table_output = "proteinmpnn_scores_table.csv"
    table.to_csv(table_output, index=False)

    output_for = {"vanilla": vanillaScoresFile, "soluble": solubleScoresFile}
    for label, found in results:
        name = f"proteinmpnn_scores_{label}.json"
        with open(name, "w") as jf:
            json.dump(found, jf, indent=2)
        block.setOutput(output_for[label].id, name)

        ranked = sorted(found.items(), key=lambda item: item[1])
        show_table_html(
            [(model, f"{value:.4f}") for model, value in ranked],
            ["Model", score_column],
            f"ProteinMPNN scores - {label} ({aggregation}, lower is better)",
        )

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
    outputs=[vanillaScoresFile, solubleScoresFile, scoresTableFile],
    action=read_proteinmpnn_scores,
)
