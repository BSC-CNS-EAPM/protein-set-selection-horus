"""
Module containing the MMseqs2 threshold-sweep analysis block.

Reproduces the exploratory threshold analysis of the reference workflow: cluster a
set of sequences with MMseqs2 across a range of ``--min-seq-id`` thresholds,
keep the top-N clusters by their best member score at each threshold, and plot
the distribution of the selected representatives' scores as a boxplot. Useful for
choosing the identity threshold before running the 'Select Cluster
Representatives' block.

Runs MMseqs2 locally once per threshold, so a wider range / finer step means more
clustering runs.
"""

from HorusAPI import PluginBlock, PluginVariable, VariableTypes
from sequence_io import (
    load_scores,
    read_sequences,
    require_local,
    resolve_executable,
    show_plot_html,
)

# ==========================#
# Variable inputs
# ==========================#
sequencesFile = PluginVariable(
    id="sequences_file",
    name="Sequences file",
    description="Sequences to cluster. Either a FASTA file or a JSON file mapping "
    "sequence name to sequence.",
    type=VariableTypes.FILE,
    allowedValues=["fasta", "fa", "faa", "json"],
)
scoresFile = PluginVariable(
    id="scores_file",
    name="Scores file",
    description="Per-model scores. Either a JSON file mapping model name to score, "
    "or a CSV with a name column and a score column (e.g. 'mean_score').",
    type=VariableTypes.FILE,
    allowedValues=["json", "csv"],
)

# ==========================#
# Variables (parameters)
# ==========================#
startVariable = PluginVariable(
    id="min_seq_id_start",
    name="min_seq_id start",
    description="First --min-seq-id value in the sweep (inclusive).",
    type=VariableTypes.FLOAT,
    defaultValue=0.2,
)
stopVariable = PluginVariable(
    id="min_seq_id_stop",
    name="min_seq_id stop",
    description="End of the --min-seq-id sweep (exclusive, as in numpy.arange).",
    type=VariableTypes.FLOAT,
    defaultValue=1.0,
)
stepVariable = PluginVariable(
    id="min_seq_id_step",
    name="min_seq_id step",
    description="Step between consecutive --min-seq-id values.",
    type=VariableTypes.FLOAT,
    defaultValue=0.05,
)
topNVariable = PluginVariable(
    id="top_n_clusters",
    name="Top N clusters",
    description="Number of best-scoring clusters kept at each threshold.",
    type=VariableTypes.INTEGER,
    defaultValue=100,
)
coverageVariable = PluginVariable(
    id="coverage",
    name="Coverage",
    description="Minimum alignment coverage (-c, 0.0-1.0).",
    type=VariableTypes.FLOAT,
    defaultValue=0.8,
)
covModeVariable = PluginVariable(
    id="cov_mode",
    name="Coverage mode",
    description="MMseqs2 coverage mode (--cov-mode).",
    type=VariableTypes.INTEGER,
    defaultValue=1,
)
maximizeVariable = PluginVariable(
    id="maximize",
    name="Maximize score",
    description="If enabled, higher scores are better. By default lower scores are "
    "better, as with ProteinMPNN scores.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)

# ==========================#
# Variable outputs
# ==========================#
plotFile = PluginVariable(
    id="plot_file",
    name="Boxplot",
    description="PNG boxplot of the best-model score distributions across thresholds.",
    type=VariableTypes.FILE,
    allowedValues=["png"],
)
scoreDistributionsFile = PluginVariable(
    id="score_distributions_file",
    name="Score distributions",
    description="JSON mapping each threshold to the list of selected representatives' scores.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
selectedPerThresholdFile = PluginVariable(
    id="selected_per_threshold_file",
    name="Selected models per threshold",
    description="JSON mapping each threshold to the list of selected representative models.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)


def _run_mmseqs_cluster(sequences: dict, mmseqs_cmd, min_seq_id, coverage, cov_mode) -> dict:
    """Cluster ``sequences`` with ``mmseqs easy-cluster`` and return {rep: [members]}."""
    import os
    import shutil
    import subprocess
    import tempfile

    tmp_dir = tempfile.mkdtemp(prefix="mmseqs_sweep_")
    try:
        input_fasta = os.path.join(tmp_dir, "input.fasta")
        with open(input_fasta, "w") as of:
            for name, seq in sequences.items():
                of.write(f">{name}\n{seq}\n")

        prefix = os.path.join(tmp_dir, "clusterRes")
        command = [
            mmseqs_cmd, "easy-cluster", input_fasta, prefix, os.path.join(tmp_dir, "tmp"),
            "--min-seq-id", str(min_seq_id), "-c", str(coverage), "--cov-mode", str(cov_mode),
        ]
        completed = subprocess.run(command, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, check=False)
        if completed.returncode != 0:
            raise ValueError(f"MMseqs2 failed at min_seq_id={min_seq_id} "
                             f"(exit code {completed.returncode}).")

        clusters: dict = {}
        with open(prefix + "_cluster.tsv") as cr:
            for line in cr:
                if not line.strip():
                    continue
                representative, member = line.split()
                clusters.setdefault(representative, []).append(member)
        return clusters
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def sweep_thresholds(block: PluginBlock):
    """
    Sweep MMseqs2 ``min_seq_id`` thresholds and plot the top-N score distributions.

    Args:
        block (PluginBlock): The PluginBlock object representing the current block.
    """
    # pylint: disable=import-outside-toplevel

    import json
    import os

    import numpy as np

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # pylint: enable=import-outside-toplevel

    require_local(block, "MMseqs2 Threshold Sweep")

    sequences_path = block.inputs.get(sequencesFile.id, None)
    if not sequences_path or not os.path.isfile(sequences_path):
        raise ValueError("A valid sequences file (FASTA or JSON) must be provided.")
    scores_path = block.inputs.get(scoresFile.id, None)
    if not scores_path or not os.path.isfile(scores_path):
        raise ValueError("A valid scores file (JSON or CSV) must be provided.")

    start = block.variables.get(startVariable.id, 0.2)
    stop = block.variables.get(stopVariable.id, 1.0)
    step = block.variables.get(stepVariable.id, 0.05)
    top_n = int(block.variables.get(topNVariable.id, 100))
    coverage = block.variables.get(coverageVariable.id, 0.8)
    cov_mode = block.variables.get(covModeVariable.id, 1)
    maximize = block.variables.get(maximizeVariable.id, False)

    # resolve_executable raises with a message naming the config entry and the
    # Environment Setup page if MMseqs2 is missing.
    mmseqs_cmd = resolve_executable(block, "mmseqs_path", "mmseqs")

    sequences = read_sequences(sequences_path)
    scores = load_scores(scores_path)

    # numpy.arange accumulates floating point error with a non-integer step, so
    # it can emit a value at (or fractionally past) the exclusive stop: with
    # start=0.3, stop=0.9, step=0.2 it yields 0.9 as well as 0.3/0.5/0.7. Drop
    # anything that is not strictly below stop, so the range honours the
    # "exclusive" contract in this variable's description.
    min_seq_id_values = [
        rounded
        for rounded in (round(float(v), 2) for v in np.arange(start, stop, step))
        if rounded < stop
    ]
    if not min_seq_id_values:
        raise ValueError("The threshold range is empty. Check start/stop/step.")

    print(f"Sweeping {len(min_seq_id_values)} thresholds "
          f"({min_seq_id_values[0]}..{min_seq_id_values[-1]}) over {len(sequences)} sequences...")

    score_distributions: dict = {}
    selected_per_threshold: dict = {}

    for min_seq_id in min_seq_id_values:
        clusters = _run_mmseqs_cluster(sequences, mmseqs_cmd, min_seq_id, coverage, cov_mode)

        cluster_scores = {
            c: [scores[m] for m in members if m in scores]
            for c, members in clusters.items()
        }

        def _cluster_key(c, _cs=cluster_scores):
            vals = _cs[c]
            if not vals:
                return float("inf")
            return -max(vals) if maximize else min(vals)

        sorted_clusters = sorted(clusters.keys(), key=_cluster_key)
        top_clusters = sorted_clusters[:top_n]

        best_models = []
        best_models_scores = []
        for c in top_clusters:
            if not cluster_scores[c]:
                continue
            members = clusters[c]
            if maximize:
                best_model = max((m for m in members if m in scores), key=lambda m: scores[m])
            else:
                best_model = min((m for m in members if m in scores), key=lambda m: scores[m])
            best_models.append(best_model)
            best_models_scores.append(scores[best_model])

        key = f"{min_seq_id:.2f}"
        score_distributions[key] = best_models_scores
        selected_per_threshold[key] = best_models
        print(f"  min_seq_id={key}: {len(clusters)} clusters -> "
              f"{len(best_models)} selected representatives")

    # ---- Boxplot (skip thresholds that produced no scored representatives) ----
    plot_labels = [k for k in score_distributions if score_distributions[k]]
    plot_data = [score_distributions[k] for k in plot_labels]
    if not plot_data:
        raise ValueError("No threshold produced any scored representatives; nothing to plot. "
                         "Check that the scores file matches the sequence names.")

    plt.figure(figsize=(12, 6))
    plt.boxplot(plot_data, patch_artist=True)
    plt.xticks(range(1, len(plot_labels) + 1), plot_labels, rotation=45)
    plt.xlabel("min_seq_id")
    plt.ylabel(f"Top {top_n} best-representative scores")
    plt.title(f"Best-representative score distribution across min_seq_id (top {top_n} clusters)")
    plt.tight_layout()

    plot_output = "mmseqs_threshold_sweep.png"
    plt.savefig(plot_output, dpi=150)
    plt.close()

    # Show the plot inline in Horus
    show_plot_html(
        plot_output,
        f"MMseqs2 threshold sweep (top {top_n} clusters)",
        caption=f"{len(sequences)} sequences swept across "
                f"{len(min_seq_id_values)} thresholds.",
    )

    # ---- Write data outputs ----
    distributions_output = "mmseqs_score_distributions.json"
    with open(distributions_output, "w") as jf:
        json.dump(score_distributions, jf, indent=2)

    selected_output = "mmseqs_selected_per_threshold.json"
    with open(selected_output, "w") as jf:
        json.dump(selected_per_threshold, jf, indent=2)

    block.setOutput(plotFile.id, plot_output)
    block.setOutput(scoreDistributionsFile.id, distributions_output)
    block.setOutput(selectedPerThresholdFile.id, selected_output)


mmseqsThresholdSweepBlock = PluginBlock(
    category="Clustering & Selection",
    name="MMseqs2 Threshold Sweep",
    id="mmseqs2_threshold_sweep",
    description="Cluster sequences across a range of MMseqs2 identity thresholds and "
    "plot the top-N representatives' score distribution to help choose a threshold.",
    inputs=[sequencesFile, scoresFile],
    variables=[
        startVariable,
        stopVariable,
        stepVariable,
        topNVariable,
        coverageVariable,
        covModeVariable,
        maximizeVariable,
    ],
    outputs=[plotFile, scoreDistributionsFile, selectedPerThresholdFile],
    action=sweep_thresholds,
)
