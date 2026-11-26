#!/bin/bash
#
# Build the Protein Set Selection Horus plugin into a distributable .hp file.
#
# An .hp is simply a zip of the plugin folder. Nothing is compiled: the plugin
# drives external tools (ProteinMPNN, MMseqs2, Rosetta, BioEmu, MAFFT,
# CodonTransformer) through configured interpreters and cluster jobs, so it
# stays "universal" with no per-OS build.

set -e

PLUGIN_DIR="ProtSelect"

echo "Building Protein Set Selection Horus plugin..."

# Remove any existing hp file
rm -f ./*.hp

# Get the current git tag (otherwise 0.0.1 will be used)
git_tag=$(git describe --tags 2>/dev/null || echo "")
if [ -z "$git_tag" ]; then
    echo "No git tag found, using default version"
    git_tag="0.0.1"
fi
echo "Building plugin with tag: $git_tag"

# Pick sed (gsed on macOS to get GNU-style -i behaviour)
sed_program="sed"
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed_program="gsed"
fi

# Update the "version" field in plugin.meta
$sed_program -i 's/"version": *"[^"]*"/"version": "'"$git_tag"'"/' "$PLUGIN_DIR/plugin.meta"

name="protselect-$git_tag.hp"
echo "Building $name"

# Stage the archive in a temporary folder.
#
# An .hp is a zip of the plugin folder, so anything the distribution needs that
# lives at the repository root -- the licence above all -- has to be put inside
# that folder on purpose. Staging a copy is what lets the archive carry the
# root LICENSE and NOTICE while the repository keeps its own copies in place
# and no duplicate ever appears in the working tree.
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT

cp -r "$PLUGIN_DIR" "$stage/$PLUGIN_DIR"

# The licence shipped is the repository's licence, copied rather than retyped,
# so the two cannot drift apart.
cp LICENSE "$stage/$PLUGIN_DIR/LICENSE"

# Citation metadata travels with the plugin for the same reason: someone with an
# installed copy and no repository should still be able to cite it correctly.
[ -f CITATION.cff ] && cp CITATION.cff "$stage/$PLUGIN_DIR/CITATION.cff"

# The notice records where this build came from, so an installed plugin can be
# traced back to a version and a commit without the repository at hand.
commit=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
$sed_program -e "s|@VERSION@|$git_tag|g" -e "s|@COMMIT@|$commit|g" \
    NOTICE > "$stage/$PLUGIN_DIR/NOTICE"

# Zip the plugin folder.
#
# deps/ and config/ are excluded deliberately. deps/ is the per-plugin
# site-packages that Horus populates from plugin.meta at install time and can
# run to several GB; config/ holds machine-specific paths. Shipping either
# would bloat the artifact and leak local state onto other people's machines.
(
    cd "$stage"
    zip -r "$name" "$PLUGIN_DIR" \
        -x '*/__pycache__/*' \
        -x '*.pyc' \
        -x "$PLUGIN_DIR/deps/*" \
        -x "$PLUGIN_DIR/config/*"
)
mv "$stage/$name" .

echo
echo "Done: $name"
echo "Contents summary:"
unzip -l "$name" | tail -1
echo "Licensing in the archive:"
unzip -l "$name" | grep -E "LICENSE|NOTICE"
echo "SHA256:"
sha256sum "$name" 2>/dev/null || shasum -a 256 "$name"
