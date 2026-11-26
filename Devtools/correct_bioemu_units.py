#!/usr/bin/env python3
"""
Convert BioEmu RMSD and RMSF tables produced before v0.3.1 from nm to Å.

Why this exists
---------------

``prepare_proteins`` returns RMSD and RMSF from mdtraj in nanometres. Until
v0.3.1 the Analyse BioEmu block published those numbers while labelling them
ångström, so every value was ten times too small. Commit ``dafc343`` fixed it by
applying ``NM_TO_ANGSTROM`` where the raw values are normalised; the metrics CSV
is built from the converted lists, so its mean and standard deviation carry the
same factor.

Tables already written by an earlier analysis are still in nanometres. The
proper remedy is to re-run Analyse BioEmu under v0.3.1 against the surviving
samples, which also regenerates the plot. Where that is not practical, this
script applies the identical arithmetic: the fix is a single multiplication, and
both the mean and the standard deviation of a scaled series scale by the same
factor, so ×10 on ``RMSD_Average``, ``RMSD_StdDev`` and ``RMSF_Average`` is
exactly what the fixed code would compute from the same ensemble.

What it does **not** do: re-read any trajectory. It is a unit conversion of a
recorded result, not a reanalysis, and it is labelled as such in the manifest it
writes. Q, dGf and sequence lengths are dimensionless or unaffected and are
copied through untouched.

Originals are never modified. Everything is written to an output directory.

Usage
-----

    Devtools/correct_bioemu_units.py RUN_DIR -o OUT_DIR
    Devtools/correct_bioemu_units.py RUN_DIR -o OUT_DIR --label v0.3.1-units

It reads whichever of ``bioemu_rmsd.json``, ``bioemu_rmsf.json`` and
``bioemu_metrics.csv`` are present in RUN_DIR, and writes a converted copy of
each plus ``correction_manifest.json`` recording the originals' checksums, the
factor, the columns touched and the provenance of the correction.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

#: The factor the fixed block applies. Kept equal to analyse_bioemu's constant.
NM_TO_ANGSTROM = 10.0

#: Metrics columns derived from the RMSD/RMSF series, so scaled by the factor.
SCALED_COLUMNS = ("RMSD_Average", "RMSD_StdDev", "RMSF_Average", "RMSF_StdDev")

#: Dimensionless or unrelated; copied through.
UNTOUCHED_NOTE = (
    "Q_Average, Q_StdDev, dGf and Sequence_Length are dimensionless or unrelated "
    "to the unit defect and are copied unchanged."
)

RMSD_JSON = "bioemu_rmsd.json"
RMSF_JSON = "bioemu_rmsf.json"
METRICS_CSV = "bioemu_metrics.csv"


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def scale_json(source, destination, factor):
    """Scale every number in a {model: [values]} mapping."""
    with open(source) as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{source}: expected an object mapping model to values")

    converted, count = {}, 0
    for model, values in data.items():
        if not isinstance(values, list):
            raise ValueError(f"{source}: {model} does not hold a list")
        converted[model] = [float(v) * factor for v in values]
        count += len(values)

    with open(destination, "w") as handle:
        json.dump(converted, handle, indent=2)
    return {"models": len(converted), "values_scaled": count}


def scale_csv(source, destination, factor):
    """Scale the metrics columns derived from the RMSD/RMSF series."""
    with open(source, newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{source}: no rows")

    present = [c for c in SCALED_COLUMNS if c in rows[0]]
    for row in rows:
        for column in present:
            if row[column] not in (None, ""):
                row[column] = repr(float(row[column]) * factor)

    with open(destination, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {"rows": len(rows), "columns_scaled": present}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__.split("Usage", maxsplit=1)[0].strip()
    )
    parser.add_argument("run_dir", help="the finished run folder to read")
    parser.add_argument("-o", "--out-dir", required=True,
                        help="where to write the converted copies")
    parser.add_argument("--label", default="v0.3.1-units",
                        help="suffix for the converted file names")
    args = parser.parse_args(argv)

    if os.path.abspath(args.run_dir) == os.path.abspath(args.out_dir):
        parser.error("the output directory must differ from the run folder; "
                     "originals are never modified")

    os.makedirs(args.out_dir, exist_ok=True)

    manifest = {
        "corrected_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corrected_by": "Devtools/correct_bioemu_units.py",
        "correction": {
            "kind": "unit conversion of a recorded result, NOT a reanalysis",
            "from_unit": "nm",
            "to_unit": "Angstrom",
            "factor": NM_TO_ANGSTROM,
            "equivalent_to": "commit dafc343 (Report BioEmu RMSD and RMSF in Å), "
                             "released in v0.3.1",
            "reasoning": "the fix applies one multiplication where the raw series "
                         "are normalised, and the metrics CSV is derived from the "
                         "converted series; mean and standard deviation of a scaled "
                         "series scale by the same factor",
            "not_done": "no trajectory was re-read and no plot was regenerated; "
                        "a re-run of Analyse BioEmu under v0.3.1 is the fuller "
                        "remedy and should reproduce these values exactly",
            "untouched": UNTOUCHED_NOTE,
        },
        "run_dir": args.run_dir,
        "files": {},
    }

    work = [(RMSD_JSON, scale_json), (RMSF_JSON, scale_json), (METRICS_CSV, scale_csv)]
    found = 0
    for name, handler in work:
        source = os.path.join(args.run_dir, name)
        if not os.path.isfile(source):
            manifest["files"][name] = {"present": False}
            continue
        found += 1
        stem, extension = os.path.splitext(name)
        destination = os.path.join(args.out_dir, f"{stem}.{args.label}{extension}")
        detail = handler(source, destination, NM_TO_ANGSTROM)
        manifest["files"][name] = {
            "present": True,
            "original_bytes": os.path.getsize(source),
            "original_sha256": sha256(source),
            "corrected_file": os.path.basename(destination),
            "corrected_bytes": os.path.getsize(destination),
            "corrected_sha256": sha256(destination),
            **detail,
        }
        print(f"{name} -> {os.path.basename(destination)}  ({detail})")

    if not found:
        print(f"No BioEmu tables found in {args.run_dir}", file=sys.stderr)
        return 1

    manifest_path = os.path.join(args.out_dir, "correction_manifest.json")
    with open(manifest_path, "w") as handle:
        json.dump(manifest, handle, indent=2)
    print(f"Wrote {manifest_path}")
    print("Originals were not modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
