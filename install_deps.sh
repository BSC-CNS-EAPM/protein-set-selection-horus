#!/bin/bash
#
# Guide the installation of the external tools the Protein Set Selection plugin
# drives, outside Horus.
#
# The plugin's own Python dependencies (plugin.meta) are installed by Horus into
# ProtSelect/deps/ and are not handled here. This script covers everything that
# cannot go there: MMseqs2, MAFFT, the torch environment ProteinMPNN runs in,
# PyRosetta, BioEmu and CodonTransformer, each in its own conda environment so a
# CUDA-specific torch never clashes with Horus, plus Rosetta and SMOG 2.
#
# Neither Rosetta nor SMOG 2 needs credentials. Rosetta's binary bundles download
# freely but are licensed for non-commercial use only, so the script asks the
# user to confirm that instead. SMOG 2 is GPL; it runs from its official
# container when podman or docker is present, otherwise from a perl environment.
#
# It mirrors what the in-app Environment Setup page does (Include/env_manager.py)
# for machines where Horus is not running yet, or where a terminal is easier.
#
# Usage:
#   ./install_deps.sh                  check each tool and ask before installing
#   ./install_deps.sh --check          only report what is found
#   ./install_deps.sh --yes            install everything missing without asking
#                                      (Rosetta still needs --rosetta-noncommercial)
#   ./install_deps.sh --config FILE    also merge the resulting paths into a
#                                      Horus config, normally
#                                      <appSupport>/config/protselect/protselect_Local.json
#   --rosetta-noncommercial            confirm your use of Rosetta is academic or
#                                      non-commercial, for unattended installs
#   --rosetta-archive FILE             use (or download to, and keep) this Rosetta
#                                      bundle instead of a temporary download; for
#                                      offline machines and repeated installs
#   --only TOOL[,TOOL...]              handle only these: mmseqs, mafft, torch,
#                                      pyrosetta, bioemu, codontransformer,
#                                      rosetta, smog
#   --tools-dir DIR                    where downloaded tools go
#                                      (default ~/.local/share/protselect)
#
# Exits 1 when a required tool is still missing at the end, so --check doubles
# as a test (Devtools/test_install_deps.sh runs the whole thing in a container).

set -u

CHECK_ONLY=0
ASSUME_YES=0
ROSETTA_NONCOMMERCIAL=0
CONFIG_FILE=""
ONLY=""
ROSETTA_ARCHIVE=""
TOOLS_DIR="${PROTSELECT_TOOLS_DIR:-$HOME/.local/share/protselect}"
PYTHON_VERSION="3.11"
ROSETTA_VERSION="${ROSETTA_VERSION:-3.15}"
SMOG_IMAGE="docker.io/smogserver/smog2:stable"

# Run as root, tar restores each archive's owner uid, which fails wherever only
# one uid is mapped (rootless containers); this script and cpanm both untar.
export TAR_OPTIONS="${TAR_OPTIONS:+$TAR_OPTIONS }--no-same-owner"

usage() {
    sed -n '/^# Usage:/,/^$/p' "$0" | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
    case "$1" in
        --check) CHECK_ONLY=1 ;;
        --yes|-y) ASSUME_YES=1 ;;
        --rosetta-noncommercial) ROSETTA_NONCOMMERCIAL=1 ;;
        --config) CONFIG_FILE="${2:-}"; shift ;;
        --tools-dir) TOOLS_DIR="${2:-}"; shift ;;
        --only) ONLY=",${2:-},"; shift ;;
        --rosetta-archive) ROSETTA_ARCHIVE="${2:-}"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1"; usage; exit 1 ;;
    esac
    shift
done

# ==========================#
# Output helpers
# ==========================#
if [ -t 1 ]; then
    BOLD=$'\e[1m'; GREEN=$'\e[32m'; YELLOW=$'\e[33m'; RED=$'\e[31m'; DIM=$'\e[2m'; RESET=$'\e[0m'
else
    BOLD=""; GREEN=""; YELLOW=""; RED=""; DIM=""; RESET=""
fi

header() { echo; echo "${BOLD}== $1 ==${RESET}"; }
ok()     { echo "  ${GREEN}found${RESET}    $1"; }
missing(){ echo "  ${RED}missing${RESET}  $1"; }
warn()   { echo "  ${YELLOW}note${RESET}     $1"; }
info()   { echo "  ${DIM}$1${RESET}"; }

# ask "question" -> 0 for yes. Defaults to no, except under --yes.
ask() {
    [ "$CHECK_ONLY" -eq 1 ] && return 1
    [ "$ASSUME_YES" -eq 1 ] && return 0
    local reply
    read -r -p "  $1 [y/N] " reply
    [[ "$reply" =~ ^[Yy] ]]
}

# Config values produced along the way, in "variable=value" form
CONFIG_VALUES=()
SUMMARY=()

record() {   # record <label> <state> [config_var value]
    SUMMARY+=("$1|$2")
    if [ $# -ge 4 ] && [ -n "$4" ]; then
        CONFIG_VALUES+=("$3=$4")
    fi
}

# ==========================#
# Environment discovery
# ==========================#
# Same search order as env_manager._conda_command and _conda_roots.
CONDA=""
for name in micromamba mamba conda; do
    if command -v "$name" >/dev/null 2>&1; then
        CONDA="$(command -v "$name")"
        break
    fi
done

conda_roots() {
    local roots=("${MAMBA_ROOT_PREFIX:-}" "$HOME/micromamba" "$HOME/miniforge3"
                 "$HOME/mambaforge" "$HOME/miniconda3" "$HOME/anaconda3")
    if [ -n "${CONDA_EXE:-}" ]; then
        roots+=("$(dirname "$(dirname "$CONDA_EXE")")")
    fi
    for root in "${roots[@]}"; do
        [ -n "$root" ] && [ -d "$root" ] && echo "$root"
    done
}

# env_bin <name> <program> -> path of that program in a named environment, or nothing
env_bin() {
    local root
    while read -r root; do
        if [ -x "$root/envs/$1/bin/$2" ]; then
            echo "$root/envs/$1/bin/$2"
            return
        fi
    done < <(conda_roots)
}

# env_python <name> -> path of that environment's interpreter, or nothing
env_python() {
    env_bin "$1" python
}

# Run an interpreter from another environment without Horus's PYTHONPATH leaking in
foreign_python() {
    env -u PYTHONPATH -u PYTHONHOME -u PYTHONSTARTUP -u PYTHONUSERBASE "$@"
}

# can_import <python> <module...> -> prints the first module's version on success
can_import() {
    local python="$1"; shift
    local imports
    imports="$(printf 'import %s; ' "$@")"
    foreign_python "$python" -c "${imports}print(getattr($1, '__version__', ''))" 2>/dev/null
}

require_conda() {
    if [ -n "$CONDA" ]; then
        return 0
    fi
    warn "No micromamba, mamba or conda on PATH, so environments cannot be created."
    info "Install micromamba with:  \"\${SHELL}\" <(curl -L micro.mamba.pm/install.sh)"
    info "then open a new shell and run this script again."
    return 1
}

# create_env <name> <pip packages...> -> prints the interpreter path
create_env() {
    local env_name="$1"; shift
    local python
    python="$(env_python "$env_name")"
    if [ -z "$python" ]; then
        echo "  Creating environment '$env_name' (python $PYTHON_VERSION)..." >&2
        "$CONDA" create -y -n "$env_name" -c conda-forge "python=$PYTHON_VERSION" >&2 || return 1
        python="$(env_python "$env_name")"
        if [ -z "$python" ]; then
            echo "  Created '$env_name' but could not find its interpreter." >&2
            return 1
        fi
    fi
    if [ $# -gt 0 ]; then
        echo "  Installing $* into '$env_name'..." >&2
        foreign_python "$python" -m pip install "$@" >&2 || return 1
    fi
    echo "$python"
}

# ==========================#
# Tools
# ==========================#
setup_mmseqs() {
    header "MMseqs2  (MMseqs2 Clustering, MMseqs2 Threshold Sweep)"
    local found
    found="$(command -v mmseqs 2>/dev/null || true)"
    [ -z "$found" ] && [ -x "$TOOLS_DIR/mmseqs/bin/mmseqs" ] && found="$TOOLS_DIR/mmseqs/bin/mmseqs"
    if [ -n "$found" ]; then
        ok "$found  ($("$found" version 2>/dev/null | head -1))"
        record "MMseqs2" ok mmseqs_path "$found"
        return
    fi
    missing "mmseqs is not on PATH"
    info "The official static build needs no conda; it goes to $TOOLS_DIR/mmseqs."
    if ! ask "Download and install MMseqs2?"; then
        record "MMseqs2" missing
        return
    fi

    # Same builds as env_manager._install_mmseqs, picked for this machine
    local build="mmseqs-linux-sse41"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        build="mmseqs-osx-universal"
    elif [ "$(uname -m)" = "aarch64" ]; then
        build="mmseqs-linux-arm64"
    elif grep -q avx2 /proc/cpuinfo 2>/dev/null; then
        build="mmseqs-linux-avx2"
    fi
    mkdir -p "$TOOLS_DIR"
    if curl -fL "https://mmseqs.com/latest/$build.tar.gz" | tar -xz -C "$TOOLS_DIR" \
        && [ -x "$TOOLS_DIR/mmseqs/bin/mmseqs" ]; then
        ok "$TOOLS_DIR/mmseqs/bin/mmseqs"
        record "MMseqs2" installed mmseqs_path "$TOOLS_DIR/mmseqs/bin/mmseqs"
    else
        missing "the download or extraction failed"
        record "MMseqs2" failed
    fi
}

setup_mafft() {
    header "MAFFT  (Multiple Sequence Alignment)"
    local found
    found="$(command -v mafft 2>/dev/null || true)"
    [ -z "$found" ] && found="$(env_bin mafft mafft)"
    if [ -n "$found" ] && [ -x "$found" ]; then
        ok "$found  ($("$found" --version 2>&1 | head -1))"
        record "MAFFT" ok mafft_path "$found"
        return
    fi
    missing "mafft is not on PATH"
    info "Alternatively: 'sudo apt install mafft' (Debian/Ubuntu) or 'brew install mafft'."
    if ! require_conda || ! ask "Install MAFFT from bioconda into an environment 'mafft'?"; then
        record "MAFFT" missing
        return
    fi
    if "$CONDA" create -y -n mafft -c conda-forge -c bioconda mafft; then
        found="$(env_bin mafft mafft)"
        ok "$found"
        record "MAFFT" installed mafft_path "$found"
    else
        record "MAFFT" failed
    fi
}

setup_torch() {
    header "PyTorch for ProteinMPNN  (ProteinMPNN Scoring)"
    local python version
    python="$(env_python proteinmpnn)"
    if [ -n "$python" ] && version="$(can_import "$python" torch numpy)"; then
        ok "$python  (torch $version)"
        record "PyTorch (ProteinMPNN)" ok proteinmpnn_python "$python"
        return
    fi
    missing "no environment 'proteinmpnn' with torch"
    info "Only needed to score locally; on a cluster the block's conda environment is used."

    local index="https://download.pytorch.org/whl/cpu"
    if command -v nvidia-smi >/dev/null 2>&1; then
        local cuda
        cuda="$(nvidia-smi 2>/dev/null | grep -o 'CUDA Version: [0-9.]*' | awk '{print $3}')"
        info "NVIDIA driver found (supports CUDA ${cuda:-unknown})."
        index="https://download.pytorch.org/whl/cu124"
    else
        info "No NVIDIA GPU found: the CPU build works but is slow."
    fi
    if [ "$CHECK_ONLY" -eq 0 ] && [ "$ASSUME_YES" -eq 0 ]; then
        local reply
        read -r -p "  torch wheel index [$index]: " reply
        index="${reply:-$index}"
    fi
    if ! require_conda || ! ask "Create 'proteinmpnn' with torch from $index?"; then
        record "PyTorch (ProteinMPNN)" missing
        return
    fi
    if python="$(create_env proteinmpnn numpy)" \
        && foreign_python "$python" -m pip install torch --index-url "$index"; then
        ok "$python  (torch $(can_import "$python" torch))"
        record "PyTorch (ProteinMPNN)" installed proteinmpnn_python "$python"
    else
        record "PyTorch (ProteinMPNN)" failed
    fi
}

setup_pyrosetta() {
    header "PyRosetta  (Analyse Rosetta Relax)"
    local python version
    python="$(env_python pyrosetta)"
    if [ -n "$python" ] && version="$(can_import "$python" pyrosetta)"; then
        ok "$python  (pyrosetta $version)"
        record "PyRosetta" ok pyrosetta_python "$python"
        return
    fi
    missing "no environment 'pyrosetta' with PyRosetta"
    info "Installed with pyrosetta-installer, which needs no credentials (~1.5 GB download)."
    info "PyRosetta is free for non-commercial use; commercial use needs a licence."
    if ! require_conda || ! ask "Create 'pyrosetta' and install PyRosetta?"; then
        record "PyRosetta" missing
        return
    fi
    if python="$(create_env pyrosetta numpy pandas pyrosetta-installer)" \
        && PATH="$(dirname "$python"):$PATH" foreign_python "$python" -c \
            "import pyrosetta_installer; pyrosetta_installer.install_pyrosetta()" \
        && can_import "$python" pyrosetta >/dev/null; then
        ok "$python"
        record "PyRosetta" installed pyrosetta_python "$python"
    else
        record "PyRosetta" failed
    fi
}

setup_bioemu() {
    header "BioEmu  (BioEmu Sampling)"
    local python version
    python="$(env_python bioemu)"
    if [ -n "$python" ] && version="$(can_import "$python" bioemu)"; then
        ok "$python  (bioemu $version)"
        record "BioEmu" ok bioemu_env "$(dirname "$(dirname "$python")")"
        return
    fi
    missing "no environment 'bioemu'"
    info "Only needed to sample locally (wants a GPU); on a cluster the block's environment is used."
    if ! require_conda || ! ask "Create 'bioemu' and install BioEmu?"; then
        record "BioEmu" missing
        return
    fi
    if python="$(create_env bioemu bioemu)"; then
        ok "$python"
        record "BioEmu" installed bioemu_env "$(dirname "$(dirname "$python")")"
    else
        record "BioEmu" failed
    fi
}

setup_codontransformer() {
    header "CodonTransformer  (CodonTransformer)"
    local python version
    python="$(env_python codontransformer)"
    if [ -n "$python" ] && version="$(can_import "$python" CodonTransformer torch)"; then
        ok "$python"
        record "CodonTransformer" ok codontransformer_env "$(dirname "$(dirname "$python")")"
        return
    fi
    missing "no environment 'codontransformer'"
    if ! require_conda || ! ask "Create 'codontransformer' and install CodonTransformer?"; then
        record "CodonTransformer" missing
        return
    fi
    if python="$(create_env codontransformer CodonTransformer torch)"; then
        ok "$python"
        record "CodonTransformer" installed codontransformer_env "$(dirname "$(dirname "$python")")"
    else
        record "CodonTransformer" failed
    fi
}

# pick_rosetta_scripts <bin dir> -> the rosetta_scripts build to use locally:
# the MPI build when MPI is installed and that build can load it, otherwise the
# serial (static) one. mpirun on PATH is not enough on its own: the bundle is
# linked against one MPI library (MPICH for the Ubuntu bundle), and with another
# installed (Open MPI) the binary cannot even start.
pick_rosetta_scripts() {
    local bin="$1" candidate
    if command -v mpirun >/dev/null 2>&1; then
        candidate="$(compgen -G "$bin/rosetta_scripts.mpi.*release" | head -1)"
        if [ -n "$candidate" ] && mpi_build_loads "$candidate"; then
            echo "$candidate"
            return
        fi
    fi
    for candidate in static default; do
        compgen -G "$bin/rosetta_scripts.$candidate.*release" | head -1 && return
    done
}

# mpi_build_loads <binary> -> whether every shared library it needs resolves.
# Where that cannot be checked (no ldd, as on macOS) the answer is no, so the
# serial build is used.
mpi_build_loads() {
    command -v ldd >/dev/null 2>&1 || return 1
    local libs
    libs="$(ldd "$1" 2>&1)" || return 1
    ! grep -q "not found" <<< "$libs"
}

# link_on_path <executable> -> offer a link in ~/.local/bin, since Horus looks
# smog2 and the Rosetta executable up on PATH
link_on_path() {
    local target="$1" name
    name="$(basename "$target")"
    command -v "$name" >/dev/null 2>&1 && return
    if [ -e "$HOME/.local/bin/$name" ]; then
        warn "$HOME/.local/bin/$name exists but is not on PATH."
        return
    fi
    if ask "Link $name into ~/.local/bin so Horus finds it on PATH?"; then
        mkdir -p "$HOME/.local/bin"
        ln -s "$target" "$HOME/.local/bin/$name" && ok "$HOME/.local/bin/$name -> $target"
        case ":$PATH:" in
            *":$HOME/.local/bin:"*) ;;
            *) warn "~/.local/bin is not on PATH; add it in your shell profile." ;;
        esac
    fi
}

# download_resumable <url> <file>: a large download that survives both a
# dropped connection and a stalled one. Some servers leave a single connection
# crawling at a tenth of the speed a fresh one gets, so a transfer slower than
# 100 KB/s for a minute is abandoned and resumed (-C -) on a new connection.
download_resumable() {
    local attempt
    for attempt in $(seq 1 20); do
        # Resuming a file that is already complete also returns 0
        curl -fL -C - --speed-limit 102400 --speed-time 60 -o "$2" "$1" && return 0
        echo "  Download slow or interrupted; reconnecting (attempt $((attempt + 1)) of 20)..." >&2
        sleep 5
    done
    return 1
}

setup_rosetta() {
    header "Rosetta  (Rosetta Relax)  -- optional"
    local found root
    found="$(compgen -c rosetta_scripts. 2>/dev/null | head -1)"
    [ -n "$found" ] && found="$(command -v "$found")"
    if [ -z "$found" ]; then
        for root in "$TOOLS_DIR"/rosetta/*/main/source/bin; do
            [ -d "$root" ] && found="$(pick_rosetta_scripts "$root")" && [ -n "$found" ] && break
        done
    fi
    if [ -n "$found" ]; then
        ok "$found"
        record "Rosetta" ok rosetta_path "$found"
        return
    fi
    warn "rosetta_scripts is not on PATH."
    info "Not needed if relax runs on a cluster that provides Rosetta as a module."

    local bundle
    case "$OSTYPE-$(uname -m)" in
        linux*-x86_64)  bundle="ubuntu" ;;
        darwin*-arm64)  bundle="m1" ;;
        darwin*-x86_64) bundle="mac" ;;
        *)
            info "No Rosetta binary bundle for this platform; build it from"
            info "https://github.com/RosettaCommons/rosetta"
            record "Rosetta" optional-missing
            return ;;
    esac
    local url="https://downloads.rosettacommons.org/downloads/academic/$ROSETTA_VERSION/rosetta_binary_${bundle}_${ROSETTA_VERSION}_bundle.tar.bz2"

    info "Rosetta $ROSETTA_VERSION downloads without credentials, but it is licensed for"
    info "academic and non-commercial use only. Commercial use, including fee-for-service"
    info "work by academic groups, needs a licence: https://rosettacommons.org/software/license-and-download/"
    info "The bundle is ~21.5 GB to download and ~52 GB extracted, so ~75 GB while installing."
    if [ "$CHECK_ONLY" -eq 1 ]; then
        record "Rosetta" optional-missing
        return
    fi
    if [ "$ROSETTA_NONCOMMERCIAL" -eq 0 ]; then
        if [ "$ASSUME_YES" -eq 1 ]; then
            info "Skipped: pass --rosetta-noncommercial to install it unattended."
            record "Rosetta" optional-missing
            return
        fi
        local reply
        read -r -p "  Is your use of Rosetta academic or non-commercial? [y/N] " reply
        if [[ ! "$reply" =~ ^[Yy] ]]; then
            record "Rosetta" optional-missing
            return
        fi
    fi

    mkdir -p "$TOOLS_DIR/rosetta"
    local free_gb need_gb=75
    [ -n "$ROSETTA_ARCHIVE" ] && [ -f "$ROSETTA_ARCHIVE" ] && need_gb=55
    free_gb="$(df -Pk "$TOOLS_DIR/rosetta" | awk 'NR==2 {print int($4 / 1048576)}')"
    info "Free space in $TOOLS_DIR: ${free_gb} GB"
    [ "$free_gb" -lt "$need_gb" ] && warn "That is less than the ~$need_gb GB the install needs."
    if ! ask "Download and extract Rosetta $ROSETTA_VERSION ($bundle) into $TOOLS_DIR/rosetta?"; then
        record "Rosetta" optional-missing
        return
    fi

    # Downloaded to a file rather than streamed into tar, so a dropped
    # connection resumes (-C -) instead of starting 21 GB over.
    # A parallel bzip2 cuts extraction from an hour to minutes where available;
    # plain -j otherwise, since bsdtar on macOS reads -I as something else.
    # A bundle given with --rosetta-archive is kept: it is the user's copy, and
    # the point of giving one is not to download 21 GB again. When it exists the
    # download only tops it up if it is partial, and an offline machine (no
    # server to ask) goes straight to extracting it.
    local archive="$TOOLS_DIR/rosetta/$(basename "$url")" keep_archive=0
    if [ -n "$ROSETTA_ARCHIVE" ]; then
        archive="$ROSETTA_ARCHIVE"
        keep_archive=1
        mkdir -p "$(dirname "$archive")"
    fi
    local untar=(tar -xjf)
    command -v lbzip2 >/dev/null 2>&1 && untar=(tar -I lbzip2 -xf)
    command -v pbzip2 >/dev/null 2>&1 && untar=(tar -I pbzip2 -xf)
    local fetched=1
    if [ "$keep_archive" -eq 1 ] && [ -f "$archive" ]; then
        info "Using $archive"
        curl -fsI "$url" >/dev/null 2>&1 && download_resumable "$url" "$archive"
    else
        download_resumable "$url" "$archive" || fetched=0
    fi
    if [ "$fetched" -eq 1 ] \
        && echo "  Extracting (this takes a while)..." \
        && "${untar[@]}" "$archive" -C "$TOOLS_DIR/rosetta"; then
        [ "$keep_archive" -eq 0 ] && rm -f "$archive"
        for root in "$TOOLS_DIR"/rosetta/*/main/source/bin; do
            [ -d "$root" ] && found="$(pick_rosetta_scripts "$root")" && [ -n "$found" ] && break
        done
    fi
    if [ -n "$found" ]; then
        ok "$found"
        info "In the Rosetta Relax block set 'Rosetta executable' to $(basename "$found"),"
        info "and 'Rosetta path' to ${found%/main/source/bin/*} if you use symmetry."
        record "Rosetta" installed rosetta_path "$found"
        link_on_path "$found"
    else
        missing "the download or extraction failed; rerunning resumes the download"
        record "Rosetta" failed
    fi
}

# SMOG 2 through its official container: a wrapper that runs the image in the
# current directory, which is what prepare_proteins calls smog2 from.
install_smog_container() {
    local engine="$1" user_flag wrapper="$TOOLS_DIR/bin/smog2"
    # Under rootless podman only the container's root maps onto the calling
    # user; under docker, running as the caller keeps output files theirs.
    if [ "$(basename "$engine")" = "podman" ]; then
        user_flag="--user root"
    else
        user_flag="--user $(id -u):$(id -g)"
    fi
    "$engine" pull "$SMOG_IMAGE" >&2 || return 1
    mkdir -p "$TOOLS_DIR/bin"
    cat > "$wrapper" <<EOF
#!/bin/sh
# Run SMOG 2 from its official container as if it were installed locally.
# Written by protein-set-selection-horus/install_deps.sh.
exec $engine run --rm $user_flag -v "\$PWD:/work" -w /work $SMOG_IMAGE smog2 "\$@"
EOF
    chmod 755 "$wrapper"
    echo "$wrapper"
}

# SMOG 2 natively: perl and its XML modules from conda, PDL built by cpanm (the
# conda PDL builds are for long-gone perl versions), then SMOG's own configure.
install_smog_native() {
    local env_name="smog2" perl tag dir
    perl="$(env_bin "$env_name" perl)"
    if [ -z "$perl" ]; then
        # conda-forge's perl 5.32 headers include xlocale.h, which glibc dropped
        # after 2.25, so compiled modules need the older Linux sysroot.
        local sysroot=()
        [[ "$OSTYPE" == linux* ]] && sysroot=("sysroot_linux-64=2.17")
        "$CONDA" create -y -n "$env_name" -c conda-forge -c bioconda \
            perl perl-xml-simple perl-xml-libxml perl-app-cpanminus openjdk compilers make \
            "${sysroot[@]}" >&2 \
            || return 1
        perl="$(env_bin "$env_name" perl)"
        [ -z "$perl" ] && return 1
    fi
    # cpanm's shebang is '/usr/bin/env perl', which finds the system perl and
    # then installs into ~/perl5, so run it with the environment's perl. Conda's
    # perl locates its compilers' sysroot from $CC, $PREFIX or $_, in that
    # order; without PREFIX it falls back to $_ (here /usr/bin/env) and every
    # compiled module fails to link.
    local prefix
    prefix="$(dirname "$(dirname "$perl")")"
    echo "  Building PDL and the remaining perl modules (several minutes)..." >&2
    env -u PERL5LIB -u PERL_LOCAL_LIB_ROOT -u PERL_MB_OPT -u PERL_MM_OPT -u CC \
        PREFIX="$prefix" PATH="$prefix/bin:$PATH" \
        "$perl" "$prefix/bin/cpanm" --notest PDL String::Util XML::Validator::Schema >&2 \
        || return 1

    tag="$(curl -fsL https://api.github.com/repos/smog-server/SMOG2/releases/latest \
        | grep -o '"tag_name": *"[^"]*"' | sed 's/.*"\([^"]*\)"$/\1/')"
    tag="${tag:-v2.6.3}"
    dir="$TOOLS_DIR/smog2-${tag#v}"
    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        curl -fL "https://github.com/smog-server/SMOG2/archive/refs/tags/$tag.tar.gz" \
            | tar -xz -C "$dir" --strip-components=1 >&2 || return 1
    fi
    # configure.smog2 has to be sourced by bash. It exits 0 even when its own
    # test fails, so success is judged by rerunning that test (test-config,
    # which compares topologies against shipped benchmarks) for its exit code.
    (cd "$dir" && perl4smog="$perl" smog2dir="$dir" bash -c 'source ./configure.smog2') >&2
    [ -x "$dir/bin/smog2" ] || return 1
    # SMOG 2 shells out to 'java', and the openjdk installed for it lives in the
    # environment, so the generated wrappers need that on PATH. A system java
    # hides this; a clean machine does not.
    local wrapper
    for wrapper in "$dir"/bin/*; do
        grep -q "^export PATH=$prefix/bin:" "$wrapper" && continue
        { head -1 "$wrapper"; echo "export PATH=$prefix/bin:\$PATH"; tail -n +2 "$wrapper"; } \
            > "$wrapper.tmp" && cat "$wrapper.tmp" > "$wrapper" && rm "$wrapper.tmp"
    done
    # The test gets a PATH without the environment, as Horus would call it
    if ! (cd "$dir" && PATH="$dir/bin:$PATH" SMOG_PATH="$dir" perl4smog="$perl" \
            ./test-config) >&2; then
        echo "  smog2 was configured but failed its own test; see $dir/test-config-tmp" >&2
        return 1
    fi
    echo "$dir/bin/smog2"
}

setup_smog() {
    header "SMOG 2  (Analyse BioEmu, native contacts only)  -- optional"
    local found
    found="$(command -v smog2 2>/dev/null || true)"
    [ -z "$found" ] && [ -x "$TOOLS_DIR/bin/smog2" ] && found="$TOOLS_DIR/bin/smog2"
    if [ -n "$found" ]; then
        ok "$found"
        record "SMOG 2" ok smog_path "$found"
        return
    fi
    warn "smog2 is not on PATH."
    info "Without it the BioEmu analysis still gives RMSD and RMSF, but not Q or the"
    info "folding free energy. SMOG 2 is GPL and needs no registration."

    local engine="" attempted=0
    for name in podman docker; do
        command -v "$name" >/dev/null 2>&1 && engine="$(command -v "$name")" && break
    done
    if [ -n "$engine" ]; then
        info "$(basename "$engine") found: SMOG 2 can run from its official container."
        if ask "Pull $SMOG_IMAGE and install a smog2 wrapper?"; then
            attempted=1
            found="$(install_smog_container "$engine")"
        fi
    elif require_conda; then
        info "No podman or docker: SMOG 2 can be installed natively with a perl environment."
        if ask "Create 'smog2' and install SMOG 2 natively?"; then
            attempted=1
            found="$(install_smog_native)"
        fi
    fi

    if [ -n "$found" ]; then
        ok "$found"
        record "SMOG 2" installed smog_path "$found"
        link_on_path "$found"
    elif [ "$attempted" -eq 1 ]; then
        missing "the installation failed"
        record "SMOG 2" failed
    else
        record "SMOG 2" optional-missing
    fi
}

# ==========================#
# Config file
# ==========================#
# Read-modify-write, like env_manager.write_config: the file is shared by every
# config the plugin declares and Horus may have written other entries into it.
write_config() {
    local python
    python="$(command -v python3 || command -v python)"
    if [ -z "$python" ]; then
        warn "No python found to write $CONFIG_FILE; set the values by hand."
        return 1
    fi
    mkdir -p "$(dirname "$CONFIG_FILE")"
    "$python" - "$CONFIG_FILE" "${CONFIG_VALUES[@]}" <<'EOF'
import json, os, sys
path, pairs = sys.argv[1], sys.argv[2:]
current = {}
if os.path.isfile(path):
    try:
        with open(path, encoding="utf-8") as handle:
            current = json.load(handle)
    except ValueError:
        current = {}
current.update(pair.split("=", 1) for pair in pairs)
with open(path, "w", encoding="utf-8") as handle:
    json.dump(current, handle, indent=4)
EOF
}

# ==========================#
# Main
# ==========================#
echo "${BOLD}Protein Set Selection: external tool setup${RESET}"
echo "Conda frontend: ${CONDA:-none found}"
echo "Tools folder:   $TOOLS_DIR"
[ "$CHECK_ONLY" -eq 1 ] && echo "Check only: nothing will be installed."

for tool in mmseqs mafft torch pyrosetta bioemu codontransformer rosetta smog; do
    if [ -z "$ONLY" ] || [[ "$ONLY" == *",$tool,"* ]]; then
        "setup_$tool"
    fi
done

header "Summary"
for row in "${SUMMARY[@]}"; do
    label="${row%%|*}"; state="${row##*|}"
    case "$state" in
        ok|installed)     colour="$GREEN" ;;
        optional-missing) colour="$YELLOW" ;;
        *)                colour="$RED" ;;
    esac
    printf "  %-24s %s%s%s\n" "$label" "$colour" "$state" "$RESET"
done

if [ ${#CONFIG_VALUES[@]} -gt 0 ]; then
    header "Plugin configuration values"
    for pair in "${CONFIG_VALUES[@]}"; do
        printf "  %-22s %s\n" "${pair%%=*}" "${pair#*=}"
    done
    if [ -n "$CONFIG_FILE" ] && [ "$CHECK_ONLY" -eq 0 ]; then
        write_config && echo && echo "  Saved into $CONFIG_FILE"
    else
        echo
        info "Enter these in the plugin's configurations in Horus (Local remote),"
        info "or press 'Save detected paths' on its Environment Setup page."
        info "Rosetta, BioEmu and SMOG 2 are read from block parameters, not from these."
    fi
fi

# Exit status for scripted use: 1 when a required tool is missing or failed to
# install. Rosetta and SMOG 2 are optional and never fail the run.
for row in "${SUMMARY[@]}"; do
    case "${row##*|}" in
        missing|failed) exit 1 ;;
    esac
done
exit 0
