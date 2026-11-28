"""
Tests that the two citation records agree, and that no placeholder DOI ships.

Zenodo's GitHub integration reads ``.zenodo.json`` when it exists and then
ignores ``CITATION.cff`` entirely, while GitHub's "Cite this repository" button
reads only ``CITATION.cff``. The same people, licence and grant therefore live
in two files, and these tests keep them from drifting apart.

The DOI is filled in after the first archived release by
``Devtools/set_zenodo_doi.sh``. Until then it sits commented out, and a DOI
that is present must be a real one.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

yaml = pytest.importorskip("yaml")

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="module")
def cff():
    with open(os.path.join(REPO, "CITATION.cff"), encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def zenodo():
    with open(os.path.join(REPO, ".zenodo.json"), encoding="utf-8") as fh:
        return json.load(fh)


def _orcid(value):
    return value.rsplit("/", 1)[-1]


def test_same_creators_in_the_same_order(cff, zenodo):
    from_cff = [
        (f"{a['family-names']}, {a['given-names']}", _orcid(a["orcid"]), a["affiliation"])
        for a in cff["authors"]
    ]
    from_zenodo = [(c["name"], c["orcid"], c["affiliation"]) for c in zenodo["creators"]]
    assert from_zenodo == from_cff


def test_same_licence(cff, zenodo):
    # CITATION.cff uses the deprecated SPDX id GPL-3.0, which SPDX defines as
    # GPL-3.0-only; Zenodo's vocabulary uses the lower-case current id.
    assert cff["license"] in ("GPL-3.0", "GPL-3.0-only")
    assert zenodo["license"] == "gpl-3.0-only"


def test_zenodo_record_carries_grant_and_community(zenodo):
    assert zenodo["upload_type"] == "software"
    assert {"id": "10.13039/501100000780::101135119"} in zenodo["grants"]
    assert {"identifier": "robustoo"} in zenodo["communities"]


def test_zenodo_does_not_pin_a_version(zenodo):
    """Zenodo takes the version from the release tag unless this overrides it."""
    assert "version" not in zenodo


def test_doi_is_absent_or_real(cff):
    doi = cff.get("doi")
    if doi is None:
        return
    assert re.fullmatch(r"10\.5281/zenodo\.\d+", doi), doi


def test_no_placeholder_outside_its_comment():
    """``CONCEPT`` may only appear inside the commented, prepared blocks."""
    for name in ("CITATION.cff", "README.md", os.path.join("docs", "index.rst")):
        with open(os.path.join(REPO, name), encoding="utf-8") as fh:
            text = fh.read()
        if name == "README.md":
            text = re.sub(r"<!-- zenodo-doi:.*?zenodo-doi -->", "", text, flags=re.S)
        else:
            text = "\n".join(line for line in text.splitlines() if not line.lstrip().startswith(("#", "..")))
        assert "zenodo.CONCEPT" not in text, name


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_set_zenodo_doi_fills_every_slot(tmp_path):
    for name in ("CITATION.cff", "README.md"):
        shutil.copy(os.path.join(REPO, name), tmp_path / name)
    (tmp_path / "docs").mkdir()
    shutil.copy(os.path.join(REPO, "docs", "index.rst"), tmp_path / "docs" / "index.rst")
    (tmp_path / "Devtools").mkdir()
    shutil.copy(os.path.join(REPO, "Devtools", "set_zenodo_doi.sh"), tmp_path / "Devtools")

    subprocess.run(
        ["bash", str(tmp_path / "Devtools" / "set_zenodo_doi.sh"), "https://doi.org/10.5281/zenodo.1234567"],
        check=True,
        capture_output=True,
    )

    with open(tmp_path / "CITATION.cff", encoding="utf-8") as fh:
        assert yaml.safe_load(fh)["doi"] == "10.5281/zenodo.1234567"
    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.1234567.svg)]" in readme
    assert "zenodo-doi" not in readme
    index = (tmp_path / "docs" / "index.rst").read_text(encoding="utf-8")
    assert "`doi:10.5281/zenodo.1234567\n<https://doi.org/10.5281/zenodo.1234567>`_" in index
    assert "zenodo-doi" not in index and "CONCEPT" not in index

    # A second run must refuse rather than double-edit.
    second = subprocess.run(
        ["bash", str(tmp_path / "Devtools" / "set_zenodo_doi.sh"), "1234567"], capture_output=True
    )
    assert second.returncode != 0
