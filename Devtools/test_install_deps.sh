#!/bin/bash
#
# Test install_deps.sh on a clean machine: a fresh Ubuntu container with only
# curl, bzip2 and python3 (what a Horus user is expected to have) and a bare
# micromamba binary. No podman inside, so SMOG 2 takes the native route.
#
# Passes when:
#   1. install_deps.sh --yes exits 0 (every required tool installed),
#   2. a second run with --check, from a fresh shell, finds all of them,
#   3. every tool actually runs (versions, imports, a SMOG 2 model of an
#      example structure),
#   4. the config file it wrote holds a path for every tool.
#
# Downloads several GB (torch, BioEmu, PyRosetta) into the container, so expect
# 20-40 minutes; the container is removed afterwards. Rosetta is skipped unless
# --rosetta is given, which adds ~52 GB of disk while the test runs. Its 21.5 GB
# bundle is downloaded once into a cache on the host
# (~/.cache/protselect-install-test, or $PROTSELECT_TEST_CACHE) and reused by
# every later run; delete that folder to test the download itself again.
#
# Usage:
#   Devtools/test_install_deps.sh                 run the test (podman, else docker)
#   Devtools/test_install_deps.sh --rosetta       include the Rosetta bundle
#   Devtools/test_install_deps.sh --only LIST     install and check only these tools
#                                                 (install_deps.sh --only names)
#   Devtools/test_install_deps.sh --image IMAGE   base image (default ubuntu:24.04)
#   Devtools/test_install_deps.sh --shell         drop into the container afterwards

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="${PROTSELECT_TEST_CACHE:-${XDG_CACHE_HOME:-$HOME/.cache}/protselect-install-test}"
IMAGE="ubuntu:24.04"
INSTALL_FLAGS="--yes"
SHELL_AFTER=0
ONLY=""

while [ $# -gt 0 ]; do
    case "$1" in
        --rosetta) INSTALL_FLAGS="--yes --rosetta-noncommercial" ;;
        --image) IMAGE="$2"; shift ;;
        --only) ONLY="$2"; shift ;;
        --shell) SHELL_AFTER=1 ;;
        -h|--help) sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

ENGINE="$(command -v podman || command -v docker || true)"
if [ -z "$ENGINE" ]; then
    echo "Needs podman or docker."
    exit 1
fi

[ -n "$ONLY" ] && INSTALL_FLAGS="$INSTALL_FLAGS --only $ONLY"

# The extracted bundle (~52 GB) lands in container storage; the 21.5 GB archive
# in the host cache, once.
if [[ "$INSTALL_FLAGS" == *--rosetta-noncommercial* ]]; then
    bundle="rosetta_binary_ubuntu_3.15_bundle.tar.bz2"   # install_deps.sh's default
    mkdir -p "$CACHE"
    INSTALL_FLAGS="$INSTALL_FLAGS --rosetta-archive /cache/$bundle"
    need_gb=55
    [ -f "$CACHE/$bundle" ] || need_gb=80
    storage="$("$ENGINE" info --format '{{.Store.GraphRoot}}' 2>/dev/null \
        || "$ENGINE" info --format '{{.DockerRootDir}}' 2>/dev/null || echo "$HOME")"
    free_gb="$(df -Pk "$storage" | awk 'NR==2 {print int($4 / 1048576)}')"
    if [ "$free_gb" -lt "$need_gb" ]; then
        echo "Only ${free_gb} GB free under $storage; the Rosetta test needs ~${need_gb} GB."
        exit 1
    fi
fi

LOG="$REPO/test_install_deps.log"
echo "Engine: $ENGINE   Image: $IMAGE   Log: $LOG"

# Everything below runs inside the container. The repo is mounted read-only,
# so the test cannot depend on anything it would write there.
read -r -d '' INSIDE <<'EOF' || true
set -uo pipefail
step() { echo; echo "######## $1"; }
fail() { echo "TEST FAILED: $1"; exit 1; }

step "Base system"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq curl bzip2 ca-certificates python3 >/dev/null \
    || fail "apt-get"
curl -fsL https://micro.mamba.pm/api/micromamba/linux-64/latest \
    | tar -xj -C /usr/local bin/micromamba || fail "micromamba download"
export MAMBA_ROOT_PREFIX=/root/micromamba
export PATH="/root/.local/bin:$PATH"
CONFIG=/root/config/protselect/protselect_Local.json

step "install_deps.sh $INSTALL_FLAGS"
/repo/install_deps.sh $INSTALL_FLAGS --config "$CONFIG" || fail "install run exited $?"

step "install_deps.sh --check (fresh shell)"
bash -lc "PATH=$PATH MAMBA_ROOT_PREFIX=$MAMBA_ROOT_PREFIX /repo/install_deps.sh --check ${ONLY:+--only $ONLY}" \
    || fail "check run did not find every tool"

step "Each tool runs"
cfg() { python3 -c "import json,sys; print(json.load(open('$CONFIG')).get('$1',''))"; }
envpy() { echo "$(cfg "$1")/bin/python"; }
# want <tool> -> whether this run covers it (all tools unless --only was given)
want() { [ -z "$ONLY" ] || [[ ",$ONLY," == *",$1,"* ]]; }
PDB="$(ls /repo/ProtSelect/ExampleData/*/structures/*.pdb | head -1)"

if want mmseqs; then "$(cfg mmseqs_path)" version || fail "mmseqs"; fi
if want mafft; then "$(cfg mafft_path)" --version || fail "mafft"; fi
if want torch; then
    "$(cfg proteinmpnn_python)" -c "import torch, numpy; print('torch', torch.__version__)" \
        || fail "torch"
fi
if want pyrosetta; then
    "$(cfg pyrosetta_python)" -c "import pyrosetta; pyrosetta.init('-mute all'); print('pyrosetta ok')" \
        || fail "pyrosetta"
fi
if want bioemu; then
    "$(envpy bioemu_env)" -c "import bioemu; print('bioemu ok')" || fail "bioemu"
fi
if want codontransformer; then
    "$(envpy codontransformer_env)" -c "import CodonTransformer, torch; print('CodonTransformer ok')" \
        || fail "codontransformer"
fi

if want smog; then
    # The call prepare_proteins makes for Analyse BioEmu, on a shipped structure
    mkdir -p /tmp/smog && cd /tmp/smog && cp "$PDB" model.pdb
    smog2 -i model.pdb -s model -CA > smog.log 2>&1 && [ -s smog.top ] \
        || { tail -20 smog.log; fail "smog2 (on PATH) could not build a model"; }
    echo "smog2 ok"
fi

if [[ "$INSTALL_FLAGS" == *--rosetta-noncommercial* ]] && want rosetta; then
    # Score a shipped structure with an empty protocol: proves the binary runs
    # and finds its database without being told where it is.
    rosetta="$(cfg rosetta_path)"
    [ -x "$rosetta" ] || fail "no rosetta_scripts in the config"
    mkdir -p /tmp/rosetta && cd /tmp/rosetta && cp "$PDB" model.pdb
    echo '<ROSETTASCRIPTS><MOVERS/><PROTOCOLS/></ROSETTASCRIPTS>' > empty.xml
    "$rosetta" -s model.pdb -parser:protocol empty.xml -nstruct 1 -ignore_unrecognized_res \
        > rosetta.log 2>&1 && grep -q "^SCORE:" score.sc \
        || { tail -20 rosetta.log; fail "rosetta_scripts could not score a structure"; }
    echo "rosetta_scripts ok ($(basename "$rosetta"))"
fi

step "Config file"
cat "$CONFIG"
for pair in mmseqs:mmseqs_path mafft:mafft_path torch:proteinmpnn_python \
            pyrosetta:pyrosetta_python bioemu:bioemu_env \
            codontransformer:codontransformer_env smog:smog_path; do
    want "${pair%%:*}" || continue
    [ -n "$(cfg "${pair#*:}")" ] || fail "config has no ${pair#*:}"
done

echo
echo "TEST PASSED"
EOF

if [ "$SHELL_AFTER" -eq 1 ]; then
    # A subshell, so a failing check still lands in the shell for a look around
    INSIDE="( $INSIDE )"$'\necho "(test exited $?; container is removed on exit)"\nexec bash'
    TTY=(-it)
else
    TTY=()
fi

CACHE_MOUNT=()
[ -d "$CACHE" ] && CACHE_MOUNT=(-v "$CACHE:/cache")

set +e
"$ENGINE" run --rm "${TTY[@]}" \
    -v "$REPO:/repo:ro" \
    ${CACHE_MOUNT[@]+"${CACHE_MOUNT[@]}"} \
    -e INSTALL_FLAGS="$INSTALL_FLAGS" -e ONLY="$ONLY" \
    "$IMAGE" bash -c "$INSIDE" 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}
set -e

echo
if [ "$status" -eq 0 ] && grep -q "^TEST PASSED" "$LOG"; then
    echo "Passed. Full log: $LOG"
else
    echo "Failed (exit $status). Full log: $LOG"
    exit 1
fi
