"""
Generate the block and configuration reference from the plugin source.

Every block's inputs, parameters and outputs, and every plugin configuration,
are read from the ``PluginVariable`` / ``PluginBlock`` / ``SlurmBlock`` /
``PluginConfig`` definitions in ``ProtSelect/Include``, so the reference cannot
drift from what the blocks do.

The modules are parsed with ``ast`` rather than imported: HorusAPI ships with
Horus and is not installable in CI, and the blocks import heavy science
packages at module level.

Runs on ``builder-inited`` and writes ``reference/`` next to ``conf.py``. That
folder is generated; do not edit it by hand.
"""

import ast
import os
import re
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.dirname(HERE)
INCLUDE = os.path.join(os.path.dirname(DOCS), "ProtSelect", "Include")
OUT = os.path.join(DOCS, "reference")

# Pipeline order: the order a reader meets the blocks in the workflow.
BLOCK_ORDER = [
    "proteinmpnn_scoring",
    "read_proteinmpnn_scores",
    "mmseqs2_cluster_slurm",
    "mmseqs2_threshold_sweep",
    "select_cluster_representatives",
    "sequence_length_distribution",
    "trim_alphafold_models",
    "collect_selected_pdbs",
    "rosetta_relax",
    "analyse_rosetta_relax",
    "bioemu_sampling",
    "analyse_bioemu",
    "pareto_selection",
    "codon_transformer",
    "mafft_msa",
    "phylogenetic_tree",
]

SHARED_SLURM = "BSC_JOB_VARIABLES"


class _Unresolved:
    """A value that could not be evaluated statically; rendered as its source."""

    def __init__(self, text):
        self.text = text

    def __repr__(self):
        return self.text


def _evaluate(node, symbols, source):
    """Best-effort static evaluation of a keyword value."""
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        if node.value.id == "VariableTypes":
            return node.attr
    if isinstance(node, ast.Name):
        if node.id in symbols:
            return symbols[node.id]
        if node.id in ("None", "True", "False"):
            return {"None": None, "True": True, "False": False}[node.id]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_evaluate(e, symbols, source) for e in node.elts]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _evaluate(node.left, symbols, source)
        right = _evaluate(node.right, symbols, source)
        if isinstance(left, list) and isinstance(right, list):
            return left + right
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return _Unresolved(ast.get_source_segment(source, node) or "?")


def _parse_module(path, symbols):
    """Collect module-level PluginVariable/VariableList/block/config definitions."""
    with open(path) as fh:
        source = fh.read()
    tree = ast.parse(source)
    found = []
    for stmt in tree.body:
        if not (isinstance(stmt, ast.Assign) and len(stmt.targets) == 1):
            continue
        target = stmt.targets[0]
        if not isinstance(target, ast.Name):
            continue
        value = stmt.value
        if isinstance(value, ast.Call) and isinstance(value.func, (ast.Name, ast.Attribute)):
            kind = value.func.id if isinstance(value.func, ast.Name) else value.func.attr
            if kind in ("PluginVariable", "VariableList", "PluginBlock", "SlurmBlock",
                        "PluginConfig"):
                spec = {"_kind": kind, "_symbol": target.id}
                for keyword in value.keywords:
                    spec[keyword.arg] = _evaluate(keyword.value, symbols, source)
                symbols[target.id] = spec
                found.append(spec)
                continue
        if target.id == SHARED_SLURM or target.id.isupper():
            symbols[target.id] = _evaluate(value, symbols, source)
    return found


def _collect():
    symbols = {}
    # utils first: the blocks import the shared Slurm variables from it.
    _parse_module(os.path.join(INCLUDE, "utils.py"), symbols)
    shared = [v for v in symbols.get(SHARED_SLURM, []) if isinstance(v, dict)]
    shared_ids = {v.get("id") for v in shared}

    blocks, configs = [], []
    for folder, sink, kinds in (("Blocks", blocks, ("PluginBlock", "SlurmBlock")),
                                ("Configs", configs, ("PluginConfig",))):
        directory = os.path.join(INCLUDE, folder)
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".py") or name.startswith("_"):
                continue
            module_symbols = dict(symbols)
            for spec in _parse_module(os.path.join(directory, name), module_symbols):
                if spec["_kind"] in kinds:
                    spec["_module"] = f"{folder}/{name}"
                    sink.append(spec)

    order = {bid: i for i, bid in enumerate(BLOCK_ORDER)}
    blocks.sort(key=lambda b: (order.get(b.get("id"), len(order)), b.get("name", "")))
    return blocks, configs, shared, shared_ids


# ---------------------------------------------------------------- rendering


def _text(value):
    if value is None:
        return ""
    return " ".join(str(value).split())


def _esc(value):
    """Plain source text as reStructuredText: escape inline markup characters."""
    text = _text(value)
    for char in ("\\", "*", "`", "|"):
        text = text.replace(char, "\\" + char)
    # "word_" is a hyperlink reference in reST whenever the underscore is not
    # followed by a word character ("gp_*", "acc_*" from partition names).
    return re.sub(r"_(?=[^\w]|$)", r"\\_", text)


def _literal(value):
    if value is None or value == "":
        return "—"
    if isinstance(value, _Unresolved):
        return f"``{value.text}``"
    if isinstance(value, bool):
        return f"``{value}``"
    if isinstance(value, list):
        if value and all(isinstance(v, dict) for v in value):
            return "; ".join(
                ", ".join(f"{k}={_literal(x)}" for k, x in item.items()) for item in value
            )
        return ", ".join(f"``{v}``" for v in value) or "—"
    return f"``{value}``"


def _type(var):
    if var.get("_kind") == "VariableList":
        return "list"
    kind = var.get("type")
    return str(kind).lower().replace("_", " ") if kind else "—"


def _cell(text):
    # list-table cells are indented blocks; keep each on one logical line.
    # Descriptions are escaped where they are built (_esc); the other cells hold
    # markup generated here.
    return _text(text) or "—"


def _table(title, rows, header, widths=None):
    if not rows:
        return ""
    widths = " ".join(str(w) for w in (widths or [1] * len(header)))
    out = [f".. list-table:: {title}", "   :header-rows: 1", f"   :widths: {widths}", ""]
    out.append("   * - " + "\n     - ".join(header))
    for row in rows:
        out.append("   * - " + "\n     - ".join(_cell(c) for c in row))
    return "\n".join(out) + "\n"


def _extensions(var):
    allowed = var.get("allowedValues")
    if isinstance(allowed, list) and allowed and var.get("type") in ("FILE", "FOLDER"):
        return ", ".join(f".{a}" if a != "*" else "any" for a in allowed)
    return "—" if var.get("type") in ("FILE", "FOLDER") else ""


def _input_rows(variables):
    rows = []
    for var in variables:
        required = "no" if var.get("required") is False else "yes"
        rows.append([f"**{_text(var.get('name'))}** (``{var.get('id')}``)", _type(var),
                     _extensions(var) or "—", required, _esc(var.get("description"))])
    return rows


def _output_rows(variables):
    return [[f"**{_text(v.get('name'))}** (``{v.get('id')}``)", _type(v),
             _extensions(v) or "—", _esc(v.get("description"))] for v in variables]


def _parameter_rows(variables):
    rows = []
    for var in variables:
        allowed = var.get("allowedValues")
        description = _esc(var.get("description"))
        if var.get("type") == "STRING_LIST" and isinstance(allowed, list) and allowed:
            description += f" Choices: {_literal(allowed)}."
        if var.get("_kind") == "VariableList":
            fields = ", ".join(
                f"``{p.get('id')}`` ({_type(p)})" for p in var.get("prototypes") or []
                if isinstance(p, dict)
            )
            description += f" Each entry has: {fields}." if fields else ""
        rows.append([f"**{_text(var.get('name'))}** (``{var.get('id')}``)", _type(var),
                     _literal(var.get("defaultValue")), description])
    return rows


def _heading(text, char):
    return f"{text}\n{char * len(text)}\n"


def _block_page(block, shared_ids):
    name = _text(block.get("name"))
    is_slurm = block["_kind"] == "SlurmBlock"
    variables = [v for v in block.get("variables") or [] if isinstance(v, dict)]
    own = [v for v in variables if v.get("id") not in shared_ids]
    uses_shared = len(own) != len(variables)

    parts = [f".. _block-{block.get('id')}:\n", _heading(name, "=")]
    parts.append(textwrap.dedent(f"""\
        :Block id: ``protselect.{block.get('id')}``
        :Category: {_text(block.get('category'))}
        :Runs on: {"the Local remote or a SLURM cluster remote" if is_slurm
                   else "the machine running Horus"}
        :Source: ``ProtSelect/Include/{block['_module']}``
        """))
    parts.append(_esc(block.get("description")) + "\n")

    inputs = [v for v in block.get("inputs") or [] if isinstance(v, dict)]
    outputs = [v for v in block.get("outputs") or [] if isinstance(v, dict)]
    parts.append(_heading("Inputs", "-"))
    parts.append(_table("", _input_rows(inputs),
                        ["Input", "Type", "Accepts", "Required", "Description"],
                        [6, 3, 3, 3, 12])
                 or "This block takes no inputs.\n")
    parts.append(_heading("Parameters", "-"))
    parts.append(_table("", _parameter_rows(own),
                        ["Parameter", "Type", "Default", "Description"], [6, 3, 4, 12])
                 or "This block has no parameters of its own.\n")
    if uses_shared:
        parts.append("\nAs a cluster-capable block it also has the shared "
                     ":ref:`cluster job settings <cluster-job-settings>` "
                     "(CPUs, partition, walltime, job grouping, ...).\n")
    parts.append(_heading("Outputs", "-"))
    parts.append(_table("", _output_rows(outputs), ["Output", "Type", "Format", "Description"],
                        [6, 3, 3, 12])
                 or "This block produces no outputs.\n")
    return "\n".join(parts)


def _slurm_page(shared):
    parts = [".. _cluster-job-settings:\n", _heading("Cluster job settings", "="),
             "Every block that can run as a SLURM job (ProteinMPNN Scoring, MMseqs2 "
             "Clustering, Rosetta Relax, BioEmu Sampling) has these settings, shown "
             "under *Slurm configuration* in the block. On the Local remote only "
             "**CPUs** matters: it sets how many jobs run in parallel. See "
             ":doc:`../remotes` for how to choose values.\n",
             _table("", _parameter_rows(shared),
                    ["Setting", "Type", "Default", "Description"], [6, 3, 4, 12])]
    return "\n".join(parts)


def _configs_page(configs):
    parts = [".. _configurations:\n", _heading("Configurations", "="),
             "Tool locations, set once per remote under the plugin's configuration "
             "in Horus (or filled in by the :doc:`Environment Setup page "
             "<../configuration>`). Each configuration has a check that runs when "
             "you save it and reports whether the tool was found.\n"]
    for config in sorted(configs, key=lambda c: _text(c.get("name"))):
        variables = [v for v in config.get("variables") or [] if isinstance(v, dict)]
        parts.append(_heading(_text(config.get("name")), "-"))
        parts.append(_esc(config.get("description")) + "\n")
        parts.append(_table("", [[f"**{_text(v.get('name'))}** (``{v.get('id')}``)", _type(v),
                                  _literal(v.get("defaultValue")), _esc(v.get("description"))]
                                 for v in variables],
                            ["Setting", "Type", "Default", "Description"], [6, 3, 4, 12]))
    return "\n".join(parts)


def _index_page(blocks):
    parts = [_heading("Block reference", "="),
             "Generated from the block definitions in ``ProtSelect/Include/Blocks``. "
             "Blocks are listed in pipeline order; see :doc:`../workflow` for how they "
             "connect.\n",
             _table("", [[f":ref:`{_text(b.get('name'))} <block-{b.get('id')}>`",
                          _text(b.get("category")),
                          "Local or SLURM" if b["_kind"] == "SlurmBlock" else "Local"]
                         for b in blocks],
                    ["Block", "Category", "Runs on"], [3, 2, 2]),
             ".. toctree::\n   :hidden:\n\n"
             + "".join(f"   blocks/{b.get('id')}\n" for b in blocks)
             + "   cluster_job_settings\n   configurations\n"]
    return "\n".join(parts)


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Only rewrite on change so Sphinx does not rebuild every page every time.
    if os.path.exists(path):
        with open(path) as fh:
            if fh.read() == content:
                return
    with open(path, "w") as fh:
        fh.write(content)


def generate(_app=None):
    blocks, configs, shared, shared_ids = _collect()
    _write(os.path.join(OUT, "index.rst"), _index_page(blocks))
    for block in blocks:
        _write(os.path.join(OUT, "blocks", f"{block.get('id')}.rst"),
               _block_page(block, shared_ids))
    _write(os.path.join(OUT, "cluster_job_settings.rst"), _slurm_page(shared))
    _write(os.path.join(OUT, "configurations.rst"), _configs_page(configs))


def setup(app):
    app.connect("builder-inited", generate)
    return {"parallel_read_safe": True, "parallel_write_safe": True}


if __name__ == "__main__":
    generate()
    print(f"Wrote the reference to {OUT}")
