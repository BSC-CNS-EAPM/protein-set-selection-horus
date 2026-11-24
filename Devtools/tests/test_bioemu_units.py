"""
Tests that Analyse BioEmu reports RMSD and RMSF in ångström.

``prepare_proteins`` returns both from mdtraj in nanometres. The block's plot
said Å, so every value it published was ten times too small until v0.3.1
converted them (commit dafc343). The conversion is one constant applied where
the raw values are normalised, and the metrics CSV is derived from the
converted lists, so mean and standard deviation carry the same factor.

These tests exist to stop that drifting apart again, in either direction: the
values could lose the conversion, or a description could stop naming the unit
while the values keep it. The second failure mode is the one that caused the
original defect -- the label and the number disagreed, and the label was right.

The analysis action itself is not run here: it needs prepare_proteins and
mdtraj, which live in their own environment. What is tested is the conversion
the block applies and the unit its outputs claim.
"""

import horusapi_stub

horusapi_stub.install()

from Blocks import analyse_bioemu  # noqa: E402  pylint: disable=wrong-import-position


# ==========================#
# The conversion
# ==========================#
def test_the_nm_to_angstrom_factor_is_ten():
    assert analyse_bioemu.NM_TO_ANGSTROM == 10.0


def test_values_are_scaled_by_the_factor():
    """0.08 nm is 0.8 Å; the defect published 0.08 and called it Å."""
    assert analyse_bioemu._to_list([0.08, 0.4], analyse_bioemu.NM_TO_ANGSTROM) == [0.8, 4.0]


def test_an_unscaled_call_leaves_values_alone():
    """Q and other dimensionless quantities must not be scaled."""
    assert analyse_bioemu._to_list([0.99, 0.5]) == [0.99, 0.5]


def test_an_empty_series_stays_empty():
    assert analyse_bioemu._to_list(None) == []


def test_objects_exposing_tolist_are_scaled_too():
    """numpy arrays and pandas Series arrive via tolist()."""

    class Arrayish:
        def tolist(self):
            return [0.1, 0.2]

    assert analyse_bioemu._to_list(Arrayish(), analyse_bioemu.NM_TO_ANGSTROM) == [1.0, 2.0]


# ==========================#
# The unit the outputs claim
# ==========================#
def test_the_rmsd_output_names_angstrom():
    assert "Å" in analyse_bioemu.rmsdFile.description


def test_the_rmsf_output_names_angstrom():
    assert "Å" in analyse_bioemu.rmsfFile.description


def test_the_metrics_output_names_angstrom():
    assert "Å" in analyse_bioemu.metricsFile.description
