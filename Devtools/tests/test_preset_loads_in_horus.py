"""
Loads the shipped preset with Horus's own reader, where Horus is available.

The other preset test reads the ``.flow`` as data. This one hands it to
``Server.FlowManager.flow_manager.Flow.read`` -- the function Horus itself calls
when someone opens a flow -- and asks what the blocks come back holding. That is
the question that matters: a saved value is restored into ``block.variables``,
``cluster_setting`` reads it from there, and a value always beats the MareNostrum
5 fallback. Reading the JSON can show what the file says; only the real loader
shows what a block is handed.

Horus is not on PyPI and ships with the application, so these tests **skip**
unless the Horus source tree is pointed at explicitly:

    HORUS_REPO=/path/to/horus pytest Devtools/tests

Verified against Horus 1.0.3 (``1.0.3-5-g685478f``), where the published v0.3.1
preset hands 13 site fields a MareNostrum 5 value and this branch's preset
hands none.
"""

import json
import os
import subprocess
import sys
import zipfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRESET = os.path.join(REPO, "ProtSelect", "Flows", "ProteSel_Pipeline.flow")
BASELINE_COMMIT = "1cdb293e2efa892ee2de6e7bda6f473aba841c79"

SITE_FIELDS = (
    "partition", "cluster_env", "cluster_modules",
    "colabfold_bin", "hf_cache", "mmseqs_path", "msa_database",
)


@pytest.fixture(scope="module")
def flow_reader():
    """Horus's own flow reader, or skip."""
    horus_repo = os.environ.get("HORUS_REPO")
    if not horus_repo:
        pytest.skip("set HORUS_REPO to the Horus source tree to run this")
    if not os.path.isdir(horus_repo):
        pytest.skip(f"HORUS_REPO is not a directory: {horus_repo}")

    if horus_repo not in sys.path:
        sys.path.insert(0, horus_repo)
    try:
        import logging

        from Server.FlowManager.flow_manager import Flow
    except Exception as error:  # pylint: disable=broad-except
        pytest.skip(f"could not import Horus from {horus_repo}: {error}")

    logging.disable(logging.ERROR)  # Horus logs read failures at ERROR

    # Reading a flow goes through the PluginManager and AppDelegate singletons,
    # which resolve "AppSupport" relative to the working directory -- Horus's own
    # fixtures construct FlowManager("AppSupport") the same way. So the reader
    # only works from the Horus tree, and the preset is passed as an absolute
    # path. The directory is restored afterwards.
    previous = os.getcwd()
    os.chdir(horus_repo)
    try:
        # Refuse to run if Horus cannot resolve the plugin's blocks.
        #
        # PluginManager and AppDelegate are process-wide singletons. If anything
        # built them before this fixture changed directory, they resolved
        # "AppSupport" against the wrong tree, found no plugins, and every block
        # comes back as a GhostBlock -- a placeholder whose variables are not
        # visible. The site-field assertions would then pass by seeing nothing,
        # which is worse than failing. So check first and skip instead.
        probe = Flow.read(PRESET)
        kinds = {type(block).__name__ for block in probe.blocks}
        if "GhostBlock" in kinds:
            pytest.skip(
                "Horus returned GhostBlocks, so the ProtSelect blocks were not "
                "resolved and their variables cannot be inspected. The "
                "PluginManager singleton was most likely initialised before this "
                "fixture ran; run this file on its own: pytest "
                "Devtools/tests/test_preset_loads_in_horus.py"
            )
        yield Flow
    finally:
        os.chdir(previous)


def site_values(flow):
    """Every site field a loaded flow's blocks come back holding."""
    found = []
    for block in flow.blocks:
        variables = getattr(block, "variables", None)
        if not isinstance(variables, dict):
            continue
        for field in SITE_FIELDS:
            value = variables.get(field)
            if isinstance(value, str) and value.strip():
                found.append((getattr(block, "name", "?"), field, value))
    return found


# ==========================#
# This branch's preset
# ==========================#
def test_the_preset_loads(flow_reader):
    flow = flow_reader.read(PRESET)

    assert flow.name == "ProteSel Pipeline"
    assert len(flow.blocks) == 17


def test_the_blocks_come_back_as_real_horus_blocks(flow_reader):
    """Deserialization produced block objects, not raw dictionaries."""
    flow = flow_reader.read(PRESET)
    kinds = {type(block).__name__ for block in flow.blocks}

    assert "SlurmBlock" in kinds
    assert kinds <= {"SlurmBlock", "PluginBlock", "InputBlock"}, kinds


def test_no_block_is_handed_a_site_value(flow_reader):
    """The point of the whole exercise."""
    leaked = site_values(flow_reader.read(PRESET))

    assert not leaked, "Horus handed blocks site-specific values:\n" + "\n".join(
        f"  {name}.{field} = {value!r}" for name, field, value in leaked
    )


def test_the_connections_survive_a_horus_re_encode(flow_reader):
    encoded = flow_reader.read(PRESET).encode()
    connections = sum(
        len(block.get("variableConnections") or []) for block in encoded.get("blocks", [])
    )

    assert connections == 24


def test_the_example_inputs_survive_a_horus_load(flow_reader):
    flow = flow_reader.read(PRESET)
    paths = []
    for block in flow.blocks:
        variables = getattr(block, "variables", None)
        if isinstance(variables, dict):
            for key in ("folder", "file"):
                value = variables.get(key)
                if isinstance(value, str) and value.strip():
                    paths.append(value)

    assert sorted(paths) == sorted([
        "ExampleData/lysozyme/structures", "ExampleData/lysozyme/structures",
        "ExampleData/lysozyme/sequences.json", "ExampleData/lysozyme/sequences.json",
    ])


# ==========================#
# The defect, through the same reader
# ==========================#
def test_the_published_preset_did_hand_blocks_mn5_values(flow_reader, tmp_path):
    """
    The baseline's own behaviour, so the fix is measured and not asserted.

    Reads the preset as it is in v0.3.1 and shows Horus handing the blocks
    MareNostrum 5 values -- the state this branch changed.
    """
    blob = subprocess.run(
        ["git", "-C", REPO, "show", f"{BASELINE_COMMIT}:ProtSelect/Flows/ProteSel_Pipeline.flow"],
        capture_output=True, check=False,
    )
    if blob.returncode != 0:
        pytest.skip("the baseline commit is not in this checkout")

    baseline = tmp_path / "baseline.flow"
    baseline.write_bytes(blob.stdout)

    leaked = site_values(flow_reader.read(str(baseline)))
    names = {field for _, field, _ in leaked}

    assert len(leaked) == 13, [f"{n}.{f}={v}" for n, f, v in leaked]
    assert "partition" in names and "msa_database" in names
    assert any("/gpfs" in value for _, _, value in leaked)


def test_the_preset_is_a_zip_holding_flow_json():
    """Horus's reader expects that shape; keep the file in it."""
    with zipfile.ZipFile(PRESET) as archive:
        assert archive.namelist() == ["flow.json"]
        json.loads(archive.read("flow.json").decode("utf-8"))
