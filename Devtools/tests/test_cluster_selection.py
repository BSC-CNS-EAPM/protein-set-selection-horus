"""
Tests for what the cluster-representative selection actually guarantees.

The guarantee is *one representative per cluster per score set*, not one per
cluster. The block ranks clusters and takes each one's best member, does that
once for the vanilla ProteinMPNN scores and once for the soluble ones, and by
default keeps the **union** of the two selections. When the two score sets
disagree about which member of a cluster is best, the union keeps both -- so
two members of one cluster reach the next stage.

That is the intended behaviour: the two weight sets are different criteria, and
the workflow deliberately keeps what either one favours. It is the wording that
was wrong, which is what makes the one-cluster/two-opposing-scores fixture
below worth keeping: it is the check that the documented guarantee and the code
still agree.

The real block action runs here, against a stub block, writing its outputs into
a temporary working directory. Nothing is submitted anywhere.
"""

import json
import os

import horusapi_stub
import pytest
from horusapi_stub import FakeActionBlock

horusapi_stub.install()

from Blocks.select_cluster_representatives import (  # noqa: E402  pylint: disable=wrong-import-position
    select_representatives,
)


def write_json(path, payload):
    with open(path, "w") as handle:
        json.dump(payload, handle)
    return str(path)


def run_selection(tmp_path, monkeypatch, clusters, vanilla=None, soluble=None, **variables):
    """Run the real action in tmp_path and return its parsed outputs."""
    inputs = {"clusters_file": write_json(tmp_path / "clusters.json", clusters)}
    if vanilla is not None:
        inputs["vanilla_scores_file"] = write_json(tmp_path / "vanilla.json", vanilla)
    if soluble is not None:
        inputs["soluble_scores_file"] = write_json(tmp_path / "soluble.json", soluble)

    settings = {"top_n_clusters": 100, "maximize": False, "score_column": ""}
    settings.update(variables)

    block = FakeActionBlock(inputs=inputs, variables=settings)
    monkeypatch.chdir(tmp_path)
    select_representatives(block)

    with open(os.path.join(tmp_path, "selected_models.json")) as handle:
        chosen = json.load(handle)
    with open(os.path.join(tmp_path, "selected_origin.json")) as handle:
        origin = json.load(handle)
    return block, chosen, origin


# ==========================#
# One cluster, two opposing score sets
# ==========================#
#: Lower is better by default, so vanilla prefers A and soluble prefers B.
ONE_CLUSTER = {"C1": ["A", "B"]}
VANILLA_PREFERS_A = {"A": 1.0, "B": 2.0}
SOLUBLE_PREFERS_B = {"A": 2.0, "B": 1.0}


def test_the_union_keeps_two_members_of_one_cluster(tmp_path, monkeypatch):
    """
    The behaviour the docs used to deny: one cluster can contribute two models.

    This is intended. It is the reason the stage cannot be described as one
    representative per cluster.
    """
    _, chosen, _ = run_selection(
        tmp_path, monkeypatch, ONE_CLUSTER,
        vanilla=VANILLA_PREFERS_A, soluble=SOLUBLE_PREFERS_B,
    )

    assert sorted(chosen) == ["A", "B"]


def test_each_score_set_still_picks_one_member_of_that_cluster(tmp_path, monkeypatch):
    """The per-score-set guarantee, which does hold."""
    _, _, origin = run_selection(
        tmp_path, monkeypatch, ONE_CLUSTER,
        vanilla=VANILLA_PREFERS_A, soluble=SOLUBLE_PREFERS_B,
    )

    assert origin == {"A": "vanilla only", "B": "soluble only"}


def test_the_selection_table_shows_one_row_per_cluster_per_score_set(tmp_path, monkeypatch):
    run_selection(
        tmp_path, monkeypatch, ONE_CLUSTER,
        vanilla=VANILLA_PREFERS_A, soluble=SOLUBLE_PREFERS_B,
    )

    with open(os.path.join(tmp_path, "selection_table.csv")) as handle:
        rows = [line for line in handle.read().splitlines()[1:] if line.strip()]

    assert len(rows) == 2
    assert all(row.startswith("C1,") for row in rows)


# ==========================#
# When the score sets agree
# ==========================#
def test_agreeing_score_sets_keep_one_model_per_cluster(tmp_path, monkeypatch):
    clusters = {"C1": ["A", "B"], "C2": ["C", "D"]}
    scores = {"A": 1.0, "B": 2.0, "C": 1.0, "D": 2.0}

    _, chosen, origin = run_selection(
        tmp_path, monkeypatch, clusters, vanilla=scores, soluble=scores,
    )

    assert sorted(chosen) == ["A", "C"]
    assert set(origin.values()) == {"common"}


# ==========================#
# Restricting to one score set
# ==========================#
@pytest.mark.parametrize(
    "keep,expected",
    [("vanilla", ["A"]), ("soluble", ["B"])],
)
def test_keeping_one_weight_set_gives_one_model_per_cluster(
    tmp_path, monkeypatch, keep, expected
):
    """``model_selection`` is how a caller asks for a strict one-per-cluster set."""
    _, chosen, _ = run_selection(
        tmp_path, monkeypatch, ONE_CLUSTER,
        vanilla=VANILLA_PREFERS_A, soluble=SOLUBLE_PREFERS_B,
        model_selection=keep,
    )

    assert chosen == expected


# ==========================#
# A single score set
# ==========================#
def test_one_score_set_alone_gives_one_model_per_cluster(tmp_path, monkeypatch):
    clusters = {"C1": ["A", "B"], "C2": ["C", "D"]}

    _, chosen, _ = run_selection(
        tmp_path, monkeypatch, clusters,
        vanilla={"A": 1.0, "B": 2.0, "C": 5.0, "D": 4.0},
    )

    assert sorted(chosen) == ["A", "D"]


def test_top_n_limits_how_many_clusters_contribute(tmp_path, monkeypatch):
    clusters = {"C1": ["A"], "C2": ["B"], "C3": ["C"]}

    _, chosen, _ = run_selection(
        tmp_path, monkeypatch, clusters,
        vanilla={"A": 1.0, "B": 2.0, "C": 3.0}, top_n_clusters=2,
    )

    assert chosen == ["A", "B"]
