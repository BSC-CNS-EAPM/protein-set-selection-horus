"""
Module containing the MAFFT multiple sequence alignment block.

Reproduces the alignment step of the reference workflow::

    msa = bioprospecting.alignment.mafft.multipleSequenceAlignment(sequences,
                                                                   stderr=False)

This is a rewrite rather than a port. The EAPM block it replaces was broken in
four separate ways, none of which could have worked:

* ``old_subprocess = subprocess.run(check=True)`` *called* ``subprocess.run``
  with no command instead of aliasing it, raising before anything else ran.
* It wrote the result with ``bioprospecting.alignment.mafft.writeMSAToFile``,
  which does not exist -- the function is commented out upstream.
* It took a folder of PDB structures and went through
  ``prepare_proteins.proteinModels.calculateMSA()``, while the workflow aligns a
  set of sequences. Every other block here passes sequences, so a structure
  folder could not be wired to it without a detour.
* Its "must run locally" guard sat after the code that crashed.

So this block takes a sequences file like the rest of the pipeline, calls MAFFT
directly, and writes both FASTA and Clustal so the phylogenetic tree block can
consume either.
"""

from HorusAPI import PluginBlock, PluginVariable, VariableTypes
from sequence_io import read_sequences, require_local, resolve_executable

# ==========================#
# Variable inputs
# ==========================#
sequencesFile = PluginVariable(
    id="sequences_file",
    name="Sequences file",
    description="Sequences to align. A FASTA file or a JSON {name: sequence} mapping.",
    type=VariableTypes.FILE,
    allowedValues=["fasta", "fa", "faa", "json"],
)

# ==========================#
# Variables (parameters)
# ==========================#
methodVariable = PluginVariable(
    id="method",
    name="Method",
    description="MAFFT strategy. 'auto' lets MAFFT choose; linsi is the most "
    "accurate and slowest, and fftns the fastest.",
    type=VariableTypes.STRING_LIST,
    defaultValue="auto",
    allowedValues=["auto", "linsi", "ginsi", "einsi", "fftns", "fftnsi"],
)
anysymbolVariable = PluginVariable(
    id="anysymbol",
    name="Allow any symbol",
    description="Pass --anysymbol, so unusual residue codes (X, U, B, Z) do not "
    "abort the alignment.",
    type=VariableTypes.BOOLEAN,
    defaultValue=True,
)
maxiterateVariable = PluginVariable(
    id="maxiterate",
    name="Max iterations",
    description="Number of iterative refinement cycles. 0 leaves it to MAFFT.",
    type=VariableTypes.INTEGER,
    defaultValue=0,
)
threadsVariable = PluginVariable(
    id="threads",
    name="Threads",
    description="Threads MAFFT may use. 0 leaves it to MAFFT.",
    type=VariableTypes.INTEGER,
    defaultValue=0,
)

# ==========================#
# Variable outputs
# ==========================#
msaFile = PluginVariable(
    id="msa_file",
    name="MSA (FASTA)",
    description="The alignment in aligned FASTA format.",
    type=VariableTypes.FILE,
    allowedValues=["fasta"],
)
msaClustalFile = PluginVariable(
    id="msa_clustal_file",
    name="MSA (Clustal)",
    description="The same alignment in Clustal format.",
    type=VariableTypes.FILE,
    allowedValues=["aln"],
)


def calculate_msa(block: PluginBlock):
    """
    Align a set of sequences with MAFFT.

    Args:
        block (PluginBlock): The PluginBlock object representing the current block.
    """
    # pylint: disable=import-outside-toplevel
    import os

    from Bio import AlignIO

    # pylint: enable=import-outside-toplevel

    require_local(block, "Multiple Sequence Alignment")

    sequences_path = block.inputs.get(sequencesFile.id, None)
    if not sequences_path:
        raise ValueError("A valid sequences file (FASTA or JSON) must be provided.")

    sequences = read_sequences(sequences_path)
    if len(sequences) < 2:
        raise ValueError(
            f"An alignment needs at least two sequences, but only {len(sequences)} "
            "was given."
        )

    mafft_executable = resolve_executable(block, "mafft_path", "mafft")

    method = block.variables.get(methodVariable.id) or "auto"
    anysymbol = block.variables.get(anysymbolVariable.id, True)
    maxiterate = int(block.variables.get(maxiterateVariable.id, 0) or 0)
    threads = int(block.variables.get(threadsVariable.id, 0) or 0)

    print(f"Aligning {len(sequences)} sequences with MAFFT ({method})...")

    # bioprospecting invokes a bare 'mafft', so put the configured executable's
    # folder at the front of PATH for the call. The block this replaces patched
    # subprocess.run globally instead, which is both riskier and, as written,
    # broken.
    mafft_dir = os.path.dirname(os.path.abspath(mafft_executable))
    old_path = os.environ.get("PATH", "")
    os.environ["PATH"] = mafft_dir + os.pathsep + old_path

    try:
        # pylint: disable=import-outside-toplevel
        try:
            from bioprospecting.alignment import mafft, writeMsaToFastaFile
        except ImportError as error:
            raise ValueError(
                "Could not import bioprospecting, which provides the MAFFT wrapper. "
                "It is installed with the plugin's dependencies; reinstall them from "
                "the Horus Plugin Manager if this persists."
            ) from error
        # pylint: enable=import-outside-toplevel

        kwargs = {
            "stdout": False,
            "stderr": False,
            "anysymbol": bool(anysymbol),
            "method": method,
        }
        if maxiterate:
            kwargs["maxiterate"] = maxiterate
        if threads:
            kwargs["thread"] = threads

        msa = mafft.multipleSequenceAlignment(sequences, **kwargs)
    finally:
        os.environ["PATH"] = old_path

    if msa is None or len(msa) == 0:
        raise ValueError("MAFFT produced an empty alignment.")

    fasta_output = "msa.fasta"
    writeMsaToFastaFile(msa, fasta_output)

    clustal_output = "msa.aln"
    with open(clustal_output, "w") as cf:
        AlignIO.write(msa, cf, "clustal")

    print(f"Aligned {len(msa)} sequences to {msa.get_alignment_length()} columns.")

    block.setOutput(msaFile.id, fasta_output)
    block.setOutput(msaClustalFile.id, clustal_output)


multipleSequenceAlignmentBlock = PluginBlock(
    category="Sequence Alignment",
    name="Multiple Sequence Alignment (MAFFT)",
    id="mafft_msa",
    description="Align a set of sequences with MAFFT, writing both FASTA and Clustal.",
    inputs=[sequencesFile],
    variables=[methodVariable, anysymbolVariable, maxiterateVariable, threadsVariable],
    outputs=[msaFile, msaClustalFile],
    action=calculate_msa,
)
