"""
Module containing the MMseqs2 clustering block.

Wraps ``mmseqs easy-cluster`` (the same call used by
``bioprospecting.alignment.mmseqs2.clusterSequences``) so a set of protein
sequences can be clustered at a given identity threshold from within a Horus
flow. The clustering logic is ported here so the block does not depend on the
``bioprospecting`` library.
"""

from HorusAPI import PluginBlock, PluginVariable, VariableTypes
from sequence_io import read_sequences, require_local, resolve_executable

# ==========================#
# Variable inputs
# ==========================#
sequencesFile = PluginVariable(
    id="sequences_file",
    name="Sequences file",
    description="Sequences to cluster. Either a FASTA file or a JSON file mapping "
    "sequence name to sequence.",
    type=VariableTypes.FILE,
    allowedValues=["fasta", "fa", "faa", "json"],
)

# ==========================#
# Variables (parameters)
# ==========================#
minSeqIdVariable = PluginVariable(
    id="min_seq_id",
    name="Minimum sequence identity",
    description="List matches above this sequence identity for clustering "
    "(--min-seq-id, range 0.0-1.0).",
    type=VariableTypes.FLOAT,
    defaultValue=0.5,
)
coverageVariable = PluginVariable(
    id="coverage",
    name="Coverage",
    description="Minimum alignment coverage (-c, range 0.0-1.0).",
    type=VariableTypes.FLOAT,
    defaultValue=0.8,
)
covModeVariable = PluginVariable(
    id="cov_mode",
    name="Coverage mode",
    description="MMseqs2 coverage mode (--cov-mode). 0: bidirectional, "
    "1: target coverage, 2: query coverage.",
    type=VariableTypes.INTEGER,
    defaultValue=1,
)
verboseVariable = PluginVariable(
    id="verbose",
    name="Verbose",
    description="Show the MMseqs2 stdout/stderr in the logs.",
    type=VariableTypes.BOOLEAN,
    defaultValue=False,
)

# ==========================#
# Variable outputs
# ==========================#
clustersFile = PluginVariable(
    id="clusters_file",
    name="Clusters file",
    description="JSON file mapping each cluster representative to the list of its members.",
    type=VariableTypes.FILE,
    allowedValues=["json"],
)
representativesFile = PluginVariable(
    id="representatives_file",
    name="Representatives FASTA",
    description="FASTA file with one representative sequence per cluster.",
    type=VariableTypes.FILE,
    allowedValues=["fasta"],
)


def cluster_sequences(block: PluginBlock):
    """
    Cluster the input sequences with ``mmseqs easy-cluster``.

    Args:
        block (PluginBlock): The PluginBlock object representing the current block.
    """
    # pylint: disable=import-outside-toplevel
    import json
    import os
    import shutil
    import subprocess
    import tempfile

    # pylint: enable=import-outside-toplevel

    require_local(block, "MMseqs2 Clustering")

    sequences_path = block.inputs.get(sequencesFile.id, None)
    if not sequences_path or not os.path.isfile(sequences_path):
        raise ValueError("A valid sequences file (FASTA or JSON) must be provided.")

    min_seq_id = block.variables.get(minSeqIdVariable.id, 0.5)
    coverage = block.variables.get(coverageVariable.id, 0.8)
    cov_mode = block.variables.get(covModeVariable.id, 1)
    verbose = block.variables.get(verboseVariable.id, False)

    # resolve_executable raises with a message naming the config entry and the
    # Environment Setup page if MMseqs2 is missing.
    mmseqs_executable = resolve_executable(block, "mmseqs_path", "mmseqs")

    sequences = read_sequences(sequences_path)
    print(f"Clustering {len(sequences)} sequences at min_seq_id={min_seq_id}, "
          f"coverage={coverage}, cov_mode={cov_mode}...")

    std = None if verbose else subprocess.DEVNULL

    # Run MMseqs2 inside an isolated temporary directory so we never clobber
    # anything in the flow working directory.
    tmp_dir = tempfile.mkdtemp(prefix="mmseqs_")
    try:
        input_fasta = os.path.join(tmp_dir, "input.fasta")
        with open(input_fasta, "w") as of:
            for name, seq in sequences.items():
                of.write(f">{name}\n{seq}\n")

        result_prefix = os.path.join(tmp_dir, "clusterRes")
        mmseqs_tmp = os.path.join(tmp_dir, "tmp")

        command = [
            mmseqs_executable,
            "easy-cluster",
            input_fasta,
            result_prefix,
            mmseqs_tmp,
            "--min-seq-id",
            str(min_seq_id),
            "-c",
            str(coverage),
            "--cov-mode",
            str(cov_mode),
        ]

        completed = subprocess.run(command, stdout=std, stderr=std, check=False)
        if completed.returncode != 0:
            raise ValueError(
                f"MMseqs2 failed (exit code {completed.returncode}). "
                "Re-run with 'Verbose' enabled to see the MMseqs2 output."
            )

        cluster_tsv = result_prefix + "_cluster.tsv"
        if not os.path.isfile(cluster_tsv):
            raise ValueError("MMseqs2 did not produce a clustering result.")

        # Read clustering results: each line is "representative\tmember"
        clusters: dict = {}
        with open(cluster_tsv) as cr:
            for line in cr:
                if not line.strip():
                    continue
                representative, member = line.split()
                clusters.setdefault(representative, []).append(member)

        # Write outputs into the flow working directory
        clusters_output = "mmseqs_clusters.json"
        with open(clusters_output, "w") as jf:
            json.dump(clusters, jf, indent=2)

        representatives_output = "mmseqs_representatives.fasta"
        rep_seq_fasta = result_prefix + "_rep_seq.fasta"
        if os.path.isfile(rep_seq_fasta):
            shutil.copyfile(rep_seq_fasta, representatives_output)
        else:
            # Fall back to writing the representatives from the input sequences
            with open(representatives_output, "w") as of:
                for representative in clusters:
                    of.write(f">{representative}\n{sequences.get(representative, '')}\n")

        print(f"Found {len(clusters)} clusters "
              f"({len(sequences)} sequences -> {len(clusters)} representatives).")

        block.setOutput(clustersFile.id, clusters_output)
        block.setOutput(representativesFile.id, representatives_output)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


mmseqsClusterBlock = PluginBlock(
    category="Clustering & Selection",
    name="MMseqs2 Clustering",
    id="mmseqs2_cluster",
    description="Cluster protein sequences by identity with MMseqs2 (easy-cluster).",
    inputs=[sequencesFile],
    variables=[minSeqIdVariable, coverageVariable, covModeVariable, verboseVariable],
    outputs=[clustersFile, representativesFile],
    action=cluster_sequences,
)
