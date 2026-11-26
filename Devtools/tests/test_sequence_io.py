"""
Tests for the FASTA/JSON reading helpers in ``sequence_io``.

Model names are the join key across the whole pipeline -- ProteinMPNN scores,
MMseqs2 clusters, PDB basenames, Rosetta and BioEmu metric rows are all keyed by
the string ``read_sequences`` returns. A header collision that silently resolves
to one record therefore does not lose one sequence; it reattributes every
downstream metric of one protein to another protein's name.

Run them with an interpreter that has pytest, for example the one running Horus:

    ~/micromamba/envs/horus/bin/python -m pytest Devtools/tests -q
"""

import pytest

from sequence_io import read_sequences, write_fasta


# ==========================#
# Identifier collisions
# ==========================#
COLLIDING_FASTA = """>same first
AAAA
>same second
CCCC
"""
"""Two distinct proteins whose headers both normalise to the ID ``same``."""


def test_colliding_ids_with_different_sequences_raise(tmp_path):
    fasta = tmp_path / "colliding.fasta"
    fasta.write_text(COLLIDING_FASTA)

    with pytest.raises(ValueError):
        read_sequences(str(fasta))


def test_collision_error_names_the_conflicting_id(tmp_path):
    fasta = tmp_path / "colliding.fasta"
    fasta.write_text(COLLIDING_FASTA)

    with pytest.raises(ValueError) as raised:
        read_sequences(str(fasta))

    assert "same" in str(raised.value)


def test_collision_error_names_both_record_positions(tmp_path):
    fasta = tmp_path / "colliding.fasta"
    fasta.write_text(COLLIDING_FASTA)

    with pytest.raises(ValueError) as raised:
        read_sequences(str(fasta))

    message = str(raised.value)
    assert "1" in message and "2" in message


def test_collision_error_quotes_both_headers(tmp_path):
    fasta = tmp_path / "colliding.fasta"
    fasta.write_text(COLLIDING_FASTA)

    with pytest.raises(ValueError) as raised:
        read_sequences(str(fasta))

    message = str(raised.value)
    assert "same first" in message and "same second" in message


def test_colliding_ids_never_return_a_single_merged_record(tmp_path):
    """The defect this guards: one record, ``same: CCCC``, and no error."""
    fasta = tmp_path / "colliding.fasta"
    fasta.write_text(COLLIDING_FASTA)

    try:
        result = read_sequences(str(fasta))
    except ValueError:
        return
    pytest.fail(f"a colliding file was read without error, as {result!r}")


# ==========================#
# Repeated identical records
# ==========================#
REDUNDANT_FASTA = """>same first
AAAA
>same second
AAAA
"""
"""One protein written twice: the same ID carrying the same sequence."""


def test_repeated_identical_sequence_collapses_to_one_record(tmp_path):
    fasta = tmp_path / "redundant.fasta"
    fasta.write_text(REDUNDANT_FASTA)

    assert read_sequences(str(fasta)) == {"same": "AAAA"}


def test_repeated_identical_sequence_is_reported(tmp_path, capsys):
    fasta = tmp_path / "redundant.fasta"
    fasta.write_text(REDUNDANT_FASTA)

    read_sequences(str(fasta))

    out = capsys.readouterr().out
    assert "same" in out and "Warning" in out


# ==========================#
# Ordinary distinct identifiers
# ==========================#
def test_distinct_ids_are_read_unchanged(tmp_path):
    fasta = tmp_path / "distinct.fasta"
    fasta.write_text(">first\nAAAA\n>second\nCCCC\n")

    assert read_sequences(str(fasta)) == {"first": "AAAA", "second": "CCCC"}


def test_header_is_truncated_at_the_first_whitespace(tmp_path):
    fasta = tmp_path / "described.fasta"
    fasta.write_text(">ABC123 some description\nAAAA\n")

    assert read_sequences(str(fasta)) == {"ABC123": "AAAA"}


def test_unique_ids_survive_a_write_then_read_roundtrip(tmp_path):
    sequences = {"ABC123": "AAAA", "DEF456": "CCCC", "GHI789": "GGGG"}
    fasta = tmp_path / "roundtrip.fasta"

    write_fasta(sequences, str(fasta))

    assert read_sequences(str(fasta)) == sequences


def test_wrapped_sequence_lines_are_joined(tmp_path):
    fasta = tmp_path / "wrapped.fasta"
    fasta.write_text(">ABC123\nAAAA\nCCCC\n")

    assert read_sequences(str(fasta)) == {"ABC123": "AAAACCCC"}


# ==========================#
# JSON sequences
# ==========================#
def test_json_sequences_are_read_as_a_mapping(tmp_path):
    source = tmp_path / "sequences.json"
    source.write_text('{"ABC123": "AAAA", "DEF456": "CCCC"}')

    assert read_sequences(str(source)) == {"ABC123": "AAAA", "DEF456": "CCCC"}


def test_json_sequences_keep_file_order(tmp_path):
    source = tmp_path / "sequences.json"
    source.write_text('{"second": "CCCC", "first": "AAAA"}')

    assert list(read_sequences(str(source))) == ["second", "first"]


def test_json_that_is_not_an_object_is_rejected(tmp_path):
    source = tmp_path / "sequences.json"
    source.write_text('["AAAA", "CCCC"]')

    with pytest.raises(ValueError):
        read_sequences(str(source))


# ==========================#
# JSON duplicate keys
# ==========================#
# Python's ``json`` keeps the last of two equal keys without a word, so these
# files have to be caught while they are parsed, not after.
COLLIDING_JSON = '{"same": "AAAA", "other": "GGGG", "same": "CCCC"}'
"""Two distinct proteins written under the one key ``same``."""

REDUNDANT_JSON = '{"same": "AAAA", "other": "GGGG", "same": "AAAA"}'
"""One protein written twice under the same key."""


def test_json_duplicate_key_with_different_sequences_raises(tmp_path):
    source = tmp_path / "colliding.json"
    source.write_text(COLLIDING_JSON)

    with pytest.raises(ValueError):
        read_sequences(str(source))


def test_json_collision_error_names_the_key_and_both_sequences(tmp_path):
    source = tmp_path / "colliding.json"
    source.write_text(COLLIDING_JSON)

    with pytest.raises(ValueError) as raised:
        read_sequences(str(source))

    message = str(raised.value)
    assert "'same'" in message
    assert "AAAA" in message and "CCCC" in message


def test_json_colliding_keys_never_return_a_single_merged_record(tmp_path):
    """The defect this guards: ``{'same': 'CCCC', 'other': 'GGGG'}`` and no error."""
    source = tmp_path / "colliding.json"
    source.write_text(COLLIDING_JSON)

    try:
        result = read_sequences(str(source))
    except ValueError:
        return
    pytest.fail(f"a colliding file was read without error, as {result!r}")


def test_json_duplicate_key_with_identical_sequence_collapses(tmp_path):
    source = tmp_path / "redundant.json"
    source.write_text(REDUNDANT_JSON)

    assert read_sequences(str(source)) == {"same": "AAAA", "other": "GGGG"}


def test_json_duplicate_key_with_identical_sequence_is_reported(tmp_path, capsys):
    source = tmp_path / "redundant.json"
    source.write_text(REDUNDANT_JSON)

    read_sequences(str(source))

    out = capsys.readouterr().out
    assert "same" in out and "Warning" in out


def test_json_without_duplicates_reads_silently(tmp_path, capsys):
    source = tmp_path / "sequences.json"
    source.write_text('{"ABC123": "AAAA", "DEF456": "CCCC"}')

    read_sequences(str(source))

    assert "Warning" not in capsys.readouterr().out
