#!/usr/bin/env python3
"""
Blank the site-specific settings saved in a Horus flow.

Why this exists
---------------

Saving a flow writes every setting's current value into the file. Save the
ProteSel Pipeline preset on MareNostrum 5 and the artifact comes away carrying
that site's queue, module tree and ``/gpfs`` paths -- not as documentation, but
as values that apply.

That defeats the design. The blocks default these settings to empty and read
them through ``cluster_setting``, which fills an empty one with the MN5 value
only when the job goes to MN5 (``ProtSelect/Include/utils.py``). A value the
user gave always wins, and a value restored from a saved flow is
indistinguishable from one the user typed -- so the frozen MN5 paths win on
every other cluster too, where they do not exist.

Blanking the fields puts the fallback back in charge: MN5 gets the same values
from code, every other site gets nothing, and the preset stops claiming to know
where anyone's software lives.

The preset needs this run again after any save made on a cluster.

Usage
-----

    Devtools/strip_site_settings.py                      # fix the shipped preset
    Devtools/strip_site_settings.py --check              # report, change nothing
    Devtools/strip_site_settings.py path/to/other.flow

A ``.flow`` is a zip holding ``flow.json``, indented with four spaces;
rewriting it with ``json.dumps(..., indent=4)`` reproduces the original byte
for byte, so nothing but the blanked fields changes.
"""

import argparse
import json
import os
import sys
import zipfile

#: Settings that name one site. Each is read through ``cluster_setting`` (or, for
#: ``partition``, resolved per site at submission), so an empty value is not a
#: loss of function on MareNostrum 5: the value comes from the block instead.
SITE_FIELDS = (
    "partition",        # gp_bscls is MN5's QOS, not a portable queue name
    "cluster_env",      # /gpfs/projects/bsc72/conda_envs/...
    "cluster_modules",  # bsc/1.0 and friends exist only on MN5
    "colabfold_bin",
    "hf_cache",
    "mmseqs_path",
    "msa_database",
)

ENTRY = "flow.json"
DEFAULT_PRESET = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "ProtSelect", "Flows", "ProteSel_Pipeline.flow",
)


def strip(flow: dict) -> list:
    """Blank every site field in place, returning what was changed."""
    changed = []
    for block in flow.get("blocks") or []:
        for variable in block.get("variables") or []:
            if variable.get("id") not in SITE_FIELDS:
                continue
            for field in ("value", "defaultValue"):
                current = variable.get(field)
                if isinstance(current, str) and current.strip():
                    changed.append((block.get("name"), variable["id"], field, current))
                    variable[field] = ""
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("Usage", maxsplit=1)[0].strip()
    )
    parser.add_argument("flow", nargs="?", default=DEFAULT_PRESET,
                        help="the .flow to rewrite (default: the shipped preset)")
    parser.add_argument("--check", action="store_true",
                        help="report what would change and exit non-zero if anything would")
    args = parser.parse_args(argv)

    with zipfile.ZipFile(args.flow) as archive:
        entries = archive.namelist()
        if entries != [ENTRY]:
            print(f"{args.flow}: expected a zip holding only {ENTRY}, found {entries}",
                  file=sys.stderr)
            return 2
        flow = json.loads(archive.read(ENTRY).decode("utf-8"))

    changed = strip(flow)

    if not changed:
        print(f"{os.path.basename(args.flow)}: no site-specific settings saved.")
        return 0

    verb = "would blank" if args.check else "blanked"
    print(f"{os.path.basename(args.flow)}: {verb} {len(changed)} field(s)")
    for name, variable_id, field, old in changed:
        print(f"  {name}: {variable_id}.{field} = {old!r}")

    if args.check:
        return 1

    with zipfile.ZipFile(args.flow, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(ENTRY, json.dumps(flow, indent=4))
    print(f"Rewrote {args.flow}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
