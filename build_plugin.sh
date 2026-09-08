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

# Zip the plugin folder.
#
# deps/ and config/ are excluded deliberately. deps/ is the per-plugin
# site-packages that Horus populates from plugin.meta at install time and can
# run to several GB; config/ holds machine-specific paths. Shipping either
# would bloat the artifact and leak local state onto other people's machines.
zip -r "$name" "$PLUGIN_DIR" \
    -x '*/__pycache__/*' \
    -x '*.pyc' \
    -x "$PLUGIN_DIR/deps/*" \
    -x "$PLUGIN_DIR/config/*"

echo
echo "Done: $name"
echo "Contents summary:"
unzip -l "$name" | tail -1
