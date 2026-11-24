"""
Tests for what ``build_plugin.sh`` puts into the installable ``.hp`` archive.

An ``.hp`` is a zip of the plugin folder, and the folder it zips sits below the
repository root. Anything the distribution needs but that lives at the root --
the licence above all -- therefore has to be staged into the archive
deliberately; it does not arrive by being in the repository.

The build runs against a copy of the tree in a temporary directory, so these
tests never write an archive into the working copy. The copy has no ``.git``,
which is deliberate: ``build_plugin.sh`` falls back to version ``0.0.1`` when
``git describe`` finds nothing, so the build needs no repository.
"""

import os
import shutil
import subprocess
import zipfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN = "ProtSelect"


@pytest.fixture(scope="module")
def built_archive(tmp_path_factory):
    """
    Build the plugin from a throwaway copy of the tree and return the zip.

    The copy is seeded with the three things the build is meant to leave out --
    a populated ``deps/``, a machine-specific ``config/`` and a ``__pycache__``
    -- because the working copy does not always have them and their exclusion
    is part of what the archive has to get right.
    """
    stage = tmp_path_factory.mktemp("package")

    shutil.copytree(os.path.join(REPO, PLUGIN), stage / PLUGIN)
    for name in ("LICENSE", "NOTICE", "CITATION.cff", "build_plugin.sh"):
        source = os.path.join(REPO, name)
        if os.path.exists(source):
            shutil.copy(source, stage / name)

    (stage / PLUGIN / "deps").mkdir(exist_ok=True)
    (stage / PLUGIN / "deps" / "installed_package.py").write_text("# several GB of this\n")
    (stage / PLUGIN / "config").mkdir(exist_ok=True)
    (stage / PLUGIN / "config" / "paths.json").write_text('{"rosetta": "/home/someone/rosetta"}\n')
    (stage / PLUGIN / "Include" / "__pycache__").mkdir(exist_ok=True)
    (stage / PLUGIN / "Include" / "__pycache__" / "sequence_io.cpython-311.pyc").write_bytes(b"\x00")

    build = subprocess.run(
        ["bash", "build_plugin.sh"],
        cwd=stage, capture_output=True, text=True, check=False,
    )
    assert build.returncode == 0, f"build_plugin.sh failed:\n{build.stdout}\n{build.stderr}"

    archives = [p for p in os.listdir(stage) if p.endswith(".hp")]
    assert len(archives) == 1, f"expected one .hp, got {archives}"

    with zipfile.ZipFile(stage / archives[0]) as archive:
        yield archive


@pytest.fixture(scope="module")
def names(built_archive):
    return built_archive.namelist()


# ==========================#
# Licensing
# ==========================#
def test_archive_carries_a_licence_file(names):
    """The defect this guards: the published v0.3.1 .hp held no LICENSE."""
    assert f"{PLUGIN}/LICENSE" in names


def test_packaged_licence_is_the_repository_licence(built_archive):
    with open(os.path.join(REPO, "LICENSE"), "rb") as root_copy:
        expected = root_copy.read()

    assert built_archive.read(f"{PLUGIN}/LICENSE") == expected


def test_packaged_licence_is_the_gpl(built_archive):
    text = built_archive.read(f"{PLUGIN}/LICENSE").decode()

    assert "GNU GENERAL PUBLIC LICENSE" in text
    assert "Version 3, 29 June 2007" in text


def test_root_licence_is_still_in_the_repository():
    """Staging a copy into the archive must not move the root copy."""
    assert os.path.isfile(os.path.join(REPO, "LICENSE"))


# ==========================#
# Attribution and source pointers
# ==========================#
def test_archive_carries_an_attribution_notice(names):
    assert f"{PLUGIN}/NOTICE" in names


def test_notice_points_at_the_upstream_repository(built_archive):
    text = built_archive.read(f"{PLUGIN}/NOTICE").decode()

    assert "github.com/BSC-CNS-EAPM/protein-set-selection-horus" in text


def test_notice_names_the_plugin_licence(built_archive):
    text = built_archive.read(f"{PLUGIN}/NOTICE").decode()

    assert "GPL-3.0" in text


def test_notice_records_the_packaged_version(built_archive):
    """The build substitutes the version it stamped into plugin.meta."""
    text = built_archive.read(f"{PLUGIN}/NOTICE").decode()

    assert "@VERSION@" not in text
    assert "0.0.1" in text


def test_archive_carries_the_citation_metadata(names):
    """An installed copy should be citable without the repository."""
    assert f"{PLUGIN}/CITATION.cff" in names


def test_packaged_citation_names_the_authors_and_the_grant(built_archive):
    text = built_archive.read(f"{PLUGIN}/CITATION.cff").decode()

    assert "orcid.org/0000-0001-8120-888X" in text
    assert "orcid.org/0000-0001-8453-0815" in text
    assert "101135119" in text


def test_notice_says_the_external_tools_are_not_covered(built_archive):
    """
    The plugin ships none of the tools it drives, and Rosetta's terms in
    particular are not this licence's to grant.
    """
    text = built_archive.read(f"{PLUGIN}/NOTICE").decode()

    assert "Rosetta" in text
    assert "not" in text.lower()


# ==========================#
# Exclusions that must survive
# ==========================#
def test_installed_dependencies_are_excluded(names):
    assert not [n for n in names if n.startswith(f"{PLUGIN}/deps/")]


def test_machine_specific_config_is_excluded(names):
    assert not [n for n in names if n.startswith(f"{PLUGIN}/config/")]


def test_bytecode_caches_are_excluded(names):
    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]


# ==========================#
# What the archive is for
# ==========================#
def test_archive_still_carries_the_plugin_itself(names):
    assert f"{PLUGIN}/plugin.meta" in names
    assert f"{PLUGIN}/ProtSelect.py" in names
    assert f"{PLUGIN}/Include/sequence_io.py" in names
