"""
Shared IO and presentation helpers for the Protein Set Selection blocks.

Horus puts ``<pluginRoot>/Include`` on ``sys.path`` before importing the plugin,
so blocks reach this module as ``from sequence_io import read_sequences``.

Every block in this plugin speaks the same three file formats, so the parsing
lives here rather than being copy-pasted per block:

* **sequences** - a FASTA file, or a JSON object mapping name to sequence.
* **scores** - a JSON object mapping model name to a number, or a CSV whose
  name and score columns are sniffed from the header.
* **model lists** - a JSON array, a JSON object (keys are taken), or a FASTA.

Model names are the join key across the whole pipeline: the ProteinMPNN scores,
the MMseqs2 clusters, the PDB basenames in a structures folder and the rows of
the Rosetta and BioEmu metrics tables are all keyed by the same string. Parsing
them in one place keeps that agreement.

Heavy third-party imports (matplotlib, seaborn, pandas) are deliberately made
inside the functions that need them. Blocks import this module at definition
time, which Horus does for every block when it loads the plugin, and that must
stay cheap and must not fail when an optional dependency is missing.
"""

import csv
import json
import os


# ==========================#
# Sequences
# ==========================#
def read_sequences(sequences_path: str) -> dict:
    """
    Read sequences from a FASTA or JSON file.

    Parameters
    ==========
    sequences_path : str
        Path to a FASTA file, or to a JSON file mapping name to sequence.

    Returns
    =======
    dict
        Mapping of sequence name to sequence. FASTA headers are truncated at
        the first whitespace, so ">ABC123 some description" becomes "ABC123".
    """
    if not sequences_path:
        raise ValueError("No sequences file was given.")
    if not os.path.isfile(sequences_path):
        raise ValueError(f"The sequences file '{sequences_path}' does not exist.")

    if sequences_path.lower().endswith(".json"):
        with open(sequences_path) as jf:
            data = json.load(jf)
        if not isinstance(data, dict):
            raise ValueError("The JSON sequences file must map sequence names to sequences.")
        return {str(name): str(seq) for name, seq in data.items()}

    sequences: dict = {}
    name = None
    chunks: list = []
    with open(sequences_path) as ff:
        for line in ff:
            line = line.rstrip("\n")
            if line.startswith(">"):
                if name is not None:
                    sequences[name] = "".join(chunks)
                name = line[1:].split()[0]
                chunks = []
            elif line:
                chunks.append(line.strip())
    if name is not None:
        sequences[name] = "".join(chunks)
    if not sequences:
        raise ValueError(f"No sequences found in '{sequences_path}'.")
    return sequences


def write_fasta(sequences: dict, path: str, line_width: int = 0) -> str:
    """
    Write a {name: sequence} mapping to a FASTA file.

    Parameters
    ==========
    sequences : dict
        Mapping of sequence name to sequence.
    path : str
        Destination path.
    line_width : int
        Wrap sequences at this many characters. 0 writes each sequence on a
        single line, which is what the tools downstream of this plugin expect.

    Returns
    =======
    str
        The path written.
    """
    with open(path, "w") as of:
        for name, seq in sequences.items():
            of.write(f">{name}\n")
            if line_width and line_width > 0:
                for start in range(0, len(seq), line_width):
                    of.write(seq[start:start + line_width] + "\n")
            else:
                of.write(f"{seq}\n")
    return path


def read_model_list(models_path: str) -> list:
    """
    Read a list of model names from a JSON array, JSON object or FASTA file.

    Accepting all three matters because upstream blocks emit different shapes:
    ``select_cluster_representatives`` writes a JSON array, ``combine_selected_
    sequences`` writes both an array and a FASTA, and ``pareto_selection``
    writes an array. Order is preserved and duplicates are dropped.
    """
    if not models_path:
        raise ValueError("No models file was given.")
    if not os.path.isfile(models_path):
        raise ValueError(f"The models file '{models_path}' does not exist.")

    if models_path.lower().endswith(".json"):
        with open(models_path) as jf:
            data = json.load(jf)
        if isinstance(data, dict):
            names = [str(name) for name in data]
        elif isinstance(data, list):
            names = [str(name) for name in data]
        else:
            raise ValueError("The JSON models file must contain a list or an object.")
    else:
        names = list(read_sequences(models_path))

    seen = set()
    unique = []
    for name in names:
        if name not in seen:
            seen.add(name)
            unique.append(name)
    if not unique:
        raise ValueError(f"No model names found in '{models_path}'.")
    return unique


# ==========================#
# Scores
# ==========================#
def load_scores(scores_path: str) -> dict:
    """
    Read per-model scores from a JSON or CSV file.

    JSON must map model name to a number. For CSV the name column is sniffed
    from (model, description, name, id) and the score column from (mean_score,
    score, avg_score), falling back to the first and second columns.

    Note that the CSV branch keeps the last value it sees for a repeated model
    name; it does no aggregation. Producers of multi-row-per-model data (a raw
    ProteinMPNN score table, for instance) must aggregate before writing, which
    is why ``read_proteinmpnn_scores`` emits JSON as its primary output.

    Returns
    =======
    dict
        Mapping of model name to score.
    """
    if not scores_path:
        raise ValueError("No scores file was given.")
    if not os.path.isfile(scores_path):
        raise ValueError(f"The scores file '{scores_path}' does not exist.")

    if scores_path.lower().endswith(".json"):
        with open(scores_path) as jf:
            data = json.load(jf)
        if not isinstance(data, dict):
            raise ValueError("The JSON scores file must map model names to scores.")
        return {str(name): float(value) for name, value in data.items()}

    with open(scores_path, newline="") as cf:
        rows = list(csv.reader(cf))
    if not rows:
        raise ValueError(f"The scores file '{scores_path}' is empty.")

    header = [h.strip().lower() for h in rows[0]]
    name_idx = 0
    for label in ("model", "description", "name", "id"):
        if label in header:
            name_idx = header.index(label)
            break
    score_idx = None
    for label in ("mean_score", "score", "avg_score"):
        if label in header:
            score_idx = header.index(label)
            break
    if score_idx is None:
        score_idx = 1 if len(rows[0]) > 1 else None
    if score_idx is None:
        raise ValueError(
            f"Could not find a score column in '{scores_path}'. Expected one of "
            "'mean_score', 'score' or 'avg_score', or at least two columns."
        )

    scores: dict = {}
    for row in rows[1:]:
        if len(row) <= max(name_idx, score_idx):
            continue
        name, raw = row[name_idx].strip(), row[score_idx].strip()
        if not name or not raw:
            continue
        try:
            scores[name] = float(raw)
        except ValueError:
            continue
    if not scores:
        raise ValueError(f"No valid (name, score) pairs were read from '{scores_path}'.")
    return scores


# ==========================#
# Subprocess environment
# ==========================#
def foreign_python_env(extra=None) -> dict:
    """
    Environment for invoking a Python interpreter other than this one.

    Horus puts the plugin's own ``deps/lib/pythonX.Y/site-packages`` on
    ``PYTHONPATH`` before importing the plugin, and a subprocess inherits it.
    That is right for a child running *this* interpreter and wrong for any
    other: PyRosetta, CodonTransformer, BioEmu and the torch used by ProteinMPNN
    all live in their own environments, usually on a different Python version,
    and a 3.12 site-packages on the path of a 3.10 interpreter breaks the very
    imports we are checking for -- numpy fails first, with a message about
    ``numpy._core._multiarray_umath`` that says nothing about the real cause.

    So strip the variables that redirect module lookup, and leave the rest of
    the environment alone.
    """
    env = dict(os.environ)
    for name in ("PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONUSERBASE"):
        env.pop(name, None)
    if extra:
        env.update(extra)
    return env


# ==========================#
# Execution guards
# ==========================#
def require_local(block, what: str = "This block") -> None:
    """
    Raise unless the block is running on the local machine.

    The analysis blocks read and write files in the flow's working directory
    and render results into the Horus UI, neither of which survives being run
    over SSH on a cluster. The compute blocks (ProteinMPNN, Rosetta, BioEmu)
    are the ones that submit remotely.
    """
    if block.remote.name != "Local":
        raise ValueError(
            f"{what} must run on the local machine, but the selected remote is "
            f"'{block.remote.name}'. Set the block's remote to 'Local'."
        )


def resolve_executable(block, config_key: str, default: str) -> str:
    """
    Resolve an external executable from the plugin configuration.

    Returns the configured value if it is an existing file or resolvable on
    PATH, and raises with a message naming the config entry otherwise, so the
    user is pointed at the Environment Setup page rather than at a bare
    "command not found" from a subprocess.
    """
    import shutil

    command = (block.config.get(config_key) or default or "").strip()
    if not command:
        raise ValueError(
            f"No value is configured for '{config_key}'. Set it on the plugin's "
            "Environment Setup page or in the plugin configuration."
        )
    if os.path.isfile(command):
        return command
    found = shutil.which(command)
    if found:
        return found
    raise ValueError(
        f"Could not find the executable '{command}' (from the '{config_key}' "
        "configuration entry). Install it or correct the path on the plugin's "
        "Environment Setup page."
    )


def resolve_interpreter(block, config_key: str, module: str, default: str = "") -> str:
    """
    Resolve a Python interpreter that can import ``module``.

    Used for the tools that live in their own environment (PyRosetta,
    CodonTransformer, torch for ProteinMPNN) rather than in the plugin's
    ``deps/`` folder. Falls back to the interpreter running Horus.
    """
    import subprocess
    import sys

    interpreter = (block.config.get(config_key) or default or sys.executable).strip()
    if os.path.isdir(interpreter):
        candidate = os.path.join(interpreter, "bin", "python")
        if os.path.isfile(candidate):
            interpreter = candidate

    probe = subprocess.run(
        [interpreter, "-c", f"import {module}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=False,
        env=foreign_python_env(),
    )
    if probe.returncode != 0:
        raise ValueError(
            f"The interpreter '{interpreter}' (from the '{config_key}' configuration "
            f"entry) cannot import '{module}'. Install it or point the entry at an "
            "environment that has it, on the plugin's Environment Setup page."
        )
    return interpreter


# ==========================#
# Presentation
# ==========================#
def show_plot_html(png_path: str, title: str, caption: str = "") -> None:
    """
    Render a saved PNG into the Horus UI as an extension panel.

    The image is inlined as a data URI because the extension HTML is not served
    from the flow's working directory, so a relative <img src> would not load.
    """
    import base64

    from HorusAPI import Extensions

    with open(png_path, "rb") as img:
        encoded = base64.b64encode(img.read()).decode("ascii")

    caption_html = f"<p>{caption}</p>" if caption else ""
    html = (
        f'<div style="text-align:center">'
        f"<h3>{title}</h3>"
        f'<img src="data:image/png;base64,{encoded}" style="max-width:100%"/>'
        f"{caption_html}"
        f"</div>"
    )
    Extensions().loadHTML(html, title=title)


def show_table_html(rows: list, columns: list, title: str, max_rows: int = 200) -> None:
    """
    Render tabular data into the Horus UI as an extension panel.

    Parameters
    ==========
    rows : list
        Sequence of row sequences, already ordered and formatted.
    columns : list
        Column headers.
    title : str
        Panel title.
    max_rows : int
        Truncate to this many rows, with a note saying how many were dropped.
        Large tables are written to CSV outputs anyway, and pushing thousands
        of rows through the extension payload makes the UI crawl.
    """
    from HorusAPI import Extensions

    def escape(value):
        return (
            str(value)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )

    shown = rows[:max_rows] if max_rows and len(rows) > max_rows else rows
    header_html = "".join(f"<th>{escape(c)}</th>" for c in columns)
    body_html = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in shown
    )
    note = ""
    if len(shown) < len(rows):
        note = (
            f"<p><em>Showing the first {len(shown)} of {len(rows)} rows. "
            "The full table is in this block's CSV output.</em></p>"
        )

    html = (
        "<div>"
        f"<h3>{escape(title)}</h3>"
        '<div style="overflow-x:auto">'
        '<table style="border-collapse:collapse;width:100%;font-size:0.9em">'
        f'<thead><tr style="background:#eee;text-align:left">{header_html}</tr></thead>'
        f"<tbody>{body_html}</tbody>"
        "</table></div>"
        f"{note}"
        "</div>"
    )
    Extensions().loadHTML(html, title=title)


def save_plot(figure, path: str, dpi: int = 150) -> str:
    """Save a matplotlib figure and close it, returning the path."""
    import matplotlib.pyplot as plt

    figure.savefig(path, dpi=dpi)
    plt.close(figure)
    return path


def use_headless_matplotlib() -> None:
    """
    Select the non-interactive matplotlib backend.

    Horus runs blocks in a process with no display, where the default backend
    would fail. Call this before importing ``pyplot`` in a block.
    """
    import matplotlib

    matplotlib.use("Agg")
