"""
Tests that the shipped ProteSel Pipeline preset carries no site configuration.

``utils.py`` states the contract: "The block settings default to nothing
site-specific, so the plugin runs on any SLURM cluster. The MareNostrum 5
values the plugin is tested with live in the blocks as fallbacks, read through
``cluster_setting``: they fill a setting left empty only when the job goes to
MN5." ``docs/remotes.rst`` promises the same to the reader.

A saved flow defeats that. Saving writes each setting's current value into the
file, so a preset saved on MareNostrum 5 freezes that site's queue, modules and
``/gpfs`` paths into the artifact. Reopening it hands ``cluster_setting`` a
value that is no longer empty, and a value always wins over the MN5 fallback --
which means it also wins on a cluster that is not MN5, where those paths do not
exist. Blanking the fields in the preset is what puts the fallback back in
charge: MN5 gets the same values from code, and every other site gets nothing.

A ``.flow`` is a zip holding ``flow.json``.
"""

import json
import os
import re
import zipfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESET = os.path.join(REPO, "ProtSelect", "Flows", "ProteSel_Pipeline.flow")

# Site configuration must reach the job from the block's settings or the MN5
# fallback in code, never from the saved preset.
SITE_FIELDS = {
    "partition",        # gp_bscls is MareNostrum 5's QOS
    "cluster_env",      # /gpfs/projects/bsc72/conda_envs/...
    "cluster_modules",  # bsc/1.0, ...
    "colabfold_bin",
    "hf_cache",
    "mmseqs_path",
    "msa_database",
}

# Anything that names one site. Matched against stored values only: a variable's
# description names the MN5 fallback on purpose, and should.
SITE_MARKERS = re.compile(r"/gpfs|/apps/|bsc72|bsc/1\.0|gp_bscls|glogin|alogin", re.I)

EXAMPLE_FOLDER = "ExampleData/lysozyme/structures"
EXAMPLE_FILE = "ExampleData/lysozyme/sequences.json"


@pytest.fixture(scope="module")
def flow():
    with zipfile.ZipFile(PRESET) as archive:
        assert archive.namelist() == ["flow.json"], archive.namelist()
        return json.loads(archive.read("flow.json").decode("utf-8", "replace"))


@pytest.fixture(scope="module")
def stored_values(flow):
    """Every (block name, variable id, field, value) actually saved in the preset."""
    rows = []
    for block in flow["blocks"]:
        for variable in block.get("variables") or []:
            for field in ("value", "defaultValue"):
                value = variable.get(field)
                if isinstance(value, str) and value.strip():
                    rows.append((block.get("name"), variable.get("id"), field, value))
    return rows


# ==========================#
# No site configuration
# ==========================#
def test_no_stored_value_names_a_site(stored_values):
    leaked = [row for row in stored_values if SITE_MARKERS.search(row[3])]

    assert not leaked, "site-specific values saved in the preset:\n" + "\n".join(
        f"  {name}.{vid}.{field} = {value!r}" for name, vid, field, value in leaked
    )


def test_site_fields_are_empty(stored_values):
    filled = [row for row in stored_values if row[1] in SITE_FIELDS]

    assert not filled, "site fields should be empty in a generic preset:\n" + "\n".join(
        f"  {name}.{vid}.{field} = {value!r}" for name, vid, field, value in filled
    )


def test_no_block_pins_a_remote(flow):
    """Remote names differ per installation, as docs/remotes.rst says."""
    pinned = [
        b.get("name") for b in flow["blocks"]
        if (b.get("selectedRemote") or "Local") != "Local"
    ]

    assert not pinned, f"blocks pinning a remote: {pinned}"


# ==========================#
# What the preset is for, preserved
# ==========================#
def test_the_four_example_inputs_are_preserved(flow):
    folders, files = [], []
    for block in flow["blocks"]:
        for variable in block.get("variables") or []:
            if variable.get("id") == "folder" and variable.get("value"):
                folders.append(variable["value"])
            if variable.get("id") == "file" and variable.get("value"):
                files.append(variable["value"])

    assert folders == [EXAMPLE_FOLDER, EXAMPLE_FOLDER]
    assert files == [EXAMPLE_FILE, EXAMPLE_FILE]


def test_every_pipeline_block_is_still_present(flow):
    ids = [b.get("id") for b in flow["blocks"]]

    assert len(ids) == 17
    assert ids.count("horus.folder") == 2
    assert ids.count("horus.file") == 2
    for expected in (
        "protselect.proteinmpnn_scoring",
        "protselect.mmseqs2_cluster_slurm",
        "protselect.select_cluster_representatives",
        "protselect.rosetta_relax",
        "protselect.bioemu_sampling",
        "protselect.pareto_selection",
        "protselect.codon_transformer",
    ):
        assert expected in ids, expected


def test_the_connections_are_intact(flow):
    assert sum(len(b.get("variableConnections") or []) for b in flow["blocks"]) == 24


def test_every_connection_points_at_a_block_in_the_flow(flow):
    by_placed_id = {b.get("placedID"): b for b in flow["blocks"]}
    broken = []

    for block in flow["blocks"]:
        for connection in block.get("variableConnections") or []:
            for end in ("origin", "destination"):
                side = connection[end]
                target = by_placed_id.get(side["placedID"])
                if target is None or target.get("id") != side["blockID"]:
                    broken.append(f"{end} {side['blockID']}#{side['placedID']}")

    assert not broken, f"connections pointing nowhere: {broken}"
