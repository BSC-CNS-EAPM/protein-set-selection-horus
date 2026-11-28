#!/usr/bin/env bash
# Fill in the Zenodo concept DOI once the first archived release exists.
#
#   Devtools/set_zenodo_doi.sh 10.5281/zenodo.1234567
#   Devtools/set_zenodo_doi.sh 1234567          # the record number alone
#
# Pass the *concept* DOI ("Cite all versions" on the Zenodo record), not the
# DOI of one release: the concept DOI stays valid as releases are added.
#
# It uncomments the prepared blocks in CITATION.cff, README.md and
# docs/index.rst, substitutes the DOI, and refuses to leave a placeholder
# behind. It edits the working tree only; review and commit the result.
set -euo pipefail

if [ $# -ne 1 ]; then
    echo "usage: $0 <concept DOI | Zenodo record number>" >&2
    exit 2
fi

arg="$1"
arg="${arg#https://doi.org/}"
arg="${arg#doi:}"
case "$arg" in
    10.5281/zenodo.*) number="${arg#10.5281/zenodo.}" ;;
    *) number="$arg" ;;
esac
if ! [[ "$number" =~ ^[0-9]+$ ]]; then
    echo "error: '$1' is not a Zenodo DOI or record number" >&2
    exit 2
fi

cd "$(dirname "$0")/.."

for f in CITATION.cff README.md docs/index.rst; do
    if ! grep -q 'zenodo\.CONCEPT' "$f"; then
        echo "error: no placeholder in $f -- already filled in?" >&2
        exit 1
    fi
done

# CITATION.cff: uncomment the one marked line.
sed -i -E 's|^# (doi: "10\.5281/zenodo\.)CONCEPT("  )# zenodo-doi$|\1'"$number"'"|' CITATION.cff

# README.md: drop the HTML comment markers around the prepared block.
sed -i -E -e '/^<!-- zenodo-doi:/d' -e '/^zenodo-doi -->$/d' \
    -e 's|zenodo\.CONCEPT|zenodo.'"$number"'|g' README.md

# docs/index.rst: drop the markers and un-comment the lines between them.
sed -i -E -e '/^\.\. zenodo-doi: /,/^\.\. zenodo-doi end$/{
        /^\.\. zenodo-doi/d
        s/^\.\. ?//
    }' -e 's|zenodo\.CONCEPT|zenodo.'"$number"'|g' docs/index.rst

if grep -n 'CONCEPT\|zenodo-doi' CITATION.cff README.md docs/index.rst; then
    echo "error: placeholder or marker left behind (lines above)" >&2
    exit 1
fi

echo "Concept DOI 10.5281/zenodo.$number written to CITATION.cff, README.md and docs/index.rst."
echo "Review with 'git diff', then commit."
