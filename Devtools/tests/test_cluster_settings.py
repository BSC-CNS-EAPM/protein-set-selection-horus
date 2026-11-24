"""
Tests that MareNostrum 5 defaults reach MN5 jobs and nowhere else.

``cluster_setting`` is the single place that decides whether a site's value
applies: a setting the user filled in always wins, an empty one becomes the MN5
value when the job goes to MN5, and stays empty on any other cluster. These
tests pin that down against a stub block, which is enough to see what a job
would be built from without submitting anything.
"""

import horusapi_stub
from horusapi_stub import FakeBlock, FakeRemote

horusapi_stub.install()

from utils import (  # noqa: E402  pylint: disable=wrong-import-position
    cluster_modules,
    cluster_setting,
    is_mn5,
    is_mn5_host,
)

MN5_VALUE = "/gpfs/projects/bsc72/conda_envs/bioemu"
MN5_MODULES = "bsc/1.0, anaconda, intel/2025.1"

MN5 = FakeRemote(name="MN5 GPU", host="glogin1.bsc.es")
OTHER_CLUSTER = FakeRemote(name="Our cluster", host="login.othersite.example")
LOCAL = FakeRemote(name="Local", host="", is_local=True)


# ==========================#
# Recognising the site
# ==========================#
def test_mn5_login_nodes_are_recognised():
    assert is_mn5_host("glogin1.bsc.es")
    assert is_mn5_host("alogin2.bsc.es")


def test_another_cluster_is_not_mn5():
    assert not is_mn5_host("login.othersite.example")


def test_the_local_remote_is_not_mn5():
    assert not is_mn5(FakeBlock(remote=LOCAL))


# ==========================#
# An empty setting
# ==========================#
def test_an_empty_setting_takes_the_mn5_value_on_mn5():
    block = FakeBlock({"cluster_env": ""}, remote=MN5)

    assert cluster_setting(block, "cluster_env", MN5_VALUE) == MN5_VALUE


def test_an_empty_setting_stays_empty_on_another_cluster():
    """The defect this guards: MN5 paths reaching a cluster that has none."""
    block = FakeBlock({"cluster_env": ""}, remote=OTHER_CLUSTER)

    assert cluster_setting(block, "cluster_env", MN5_VALUE) == ""


def test_an_empty_setting_stays_empty_on_the_local_remote():
    block = FakeBlock({"cluster_env": ""}, remote=LOCAL)

    assert cluster_setting(block, "cluster_env", MN5_VALUE) == ""


def test_a_missing_setting_stays_empty_on_another_cluster():
    block = FakeBlock({}, remote=OTHER_CLUSTER)

    assert cluster_setting(block, "cluster_env", MN5_VALUE) == ""


def test_whitespace_counts_as_empty():
    block = FakeBlock({"cluster_env": "   "}, remote=MN5)

    assert cluster_setting(block, "cluster_env", MN5_VALUE) == MN5_VALUE


# ==========================#
# A setting the user filled in
# ==========================#
def test_the_users_value_wins_on_mn5():
    block = FakeBlock({"cluster_env": "/home/me/envs/bioemu"}, remote=MN5)

    assert cluster_setting(block, "cluster_env", MN5_VALUE) == "/home/me/envs/bioemu"


def test_the_users_value_wins_on_another_cluster():
    block = FakeBlock({"cluster_env": "/scratch/envs/bioemu"}, remote=OTHER_CLUSTER)

    assert cluster_setting(block, "cluster_env", MN5_VALUE) == "/scratch/envs/bioemu"


# ==========================#
# Module lists
# ==========================#
def test_modules_are_split_and_stripped():
    block = FakeBlock({"cluster_modules": " gcc/13 , openmpi "}, remote=OTHER_CLUSTER)

    assert cluster_modules(block, "cluster_modules", MN5_MODULES) == ["gcc/13", "openmpi"]


def test_no_modules_are_loaded_on_another_cluster_when_unset():
    """A generic remote must not inherit MN5's module tree."""
    block = FakeBlock({"cluster_modules": ""}, remote=OTHER_CLUSTER)

    assert cluster_modules(block, "cluster_modules", MN5_MODULES) == []


def test_the_mn5_module_tree_is_loaded_on_mn5_when_unset():
    block = FakeBlock({"cluster_modules": ""}, remote=MN5)

    assert cluster_modules(block, "cluster_modules", MN5_MODULES) == [
        "bsc/1.0", "anaconda", "intel/2025.1",
    ]
