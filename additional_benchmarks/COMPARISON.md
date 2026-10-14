# This work and TopoLS through TQEC BlockGraph

## Scope and reading order

We use the original mqt_max_parallel and mqt_min_parallel inputs: each has six
qubits and 24 CNOT gates. SAT trials and the three-qubit pilot are excluded.
This note documents the current comparison separately from the manuscript.
The current manuscript has not been assessed here.

Read scripts/run_comparison.py for the complete workflow, scripts/ours_cnot.cpp
for the call to the existing native implementation, scripts/run_topols.py
for upstream compiler options, then scripts/tqec_interop.py for conversion,
validation, and accounting. No core compiler headers or external submodule code
are changed. Setup and commands are in [README.md](README.md).

This work uses one layer, SA seed 1 and 1,000,000 iterations, Double look-ahead
and CareKinkParity. The CNOT-only wrapper removes the MSF outer ring before
scheduling and translates data coordinates by (-1,-1), producing a 7x7 grid
with six data sites, no MSF sites and 43 empty routing sites. TopoLS uses
three input qubits per row (-l 3), giving a 7x5 footprint (35 sites versus our 49);
fixed data locations, ZX optimization and search budgets still differ. TopoLS uses its supplied docs/prog.py with
block size 10, ZX and direction optimization, Python engine, seed 0 and five
internal seeds. The ZX audit wrapper only records counts around the original
optimization call. These are fixed reproducibility settings, not matched
optimization budgets.

## Conversion and sources

This work's data positions become persistent time-directed ZX wires. Each CNOT
path attaches a Z spider to its control and an X spider to its target. Intermediate
degree-two, zero-phase spiders preserve the wire's meaning. Their colors are
chosen to satisfy the transverse cube-wall constraints at bends. The small
backtracking routine assigns these colors; it neither reschedules paths nor
optimizes a new circuit. Unsupported geometry fails instead of being repaired.
TQEC's positioned-ZX synthesis then constructs the BlockGraph.

The cube-wall and corner rules follow TQEC's pinned
[positioned synthesis](https://github.com/tqec/tqec/blob/8c352c0d605c90ca7eb877e02c777198407875e3/src/tqec/interop/pyzx/synthesis/positioned.py)
and [positioned ZX representation](https://github.com/tqec/tqec/blob/8c352c0d605c90ca7eb877e02c777198407875e3/src/tqec/interop/pyzx/positioned.py).
The adapter is limited to this one-layer CNOT-only setting; it does not cover
magic-state operations or inter-layer routing.

TopoLS uses its own [build_pipe_diagram/save_bigraph exporter](https://github.com/tqec/TopoLS/blob/78aab0ef1326bdf2041b519708f28741162f45c4/src/topols/export/bgraph.py)
and [load_block_graph loader](https://github.com/tqec/TopoLS/blob/78aab0ef1326bdf2041b519708f28741162f45c4/src/topols/tools/pipe_sim.py).
We do not implement a second TopoLS geometry conversion. Its native .bgraph is a
pickle of metadata; the final output is TQEC's textual BGRAPH. Only trusted local
compiler pickle outputs are read.

## Checks and accounting

For every output we run BlockGraph.validate(), label and order ports by logical
qubit, and compare its ZX tensor with the input circuit using PyZX 0.10.6.
Comparison is numerical and ignores a nonzero overall scalar. We save textual
BGRAPH, read it back, repeat equivalence checking, and require unchanged metrics.
The this-work occupied count must also equal its native scheduler count.

TQEC's [BlockGraph implementation](https://github.com/tqec/tqec/blob/8c352c0d605c90ca7eb877e02c777198407875e3/src/tqec/computation/block_graph.py)
defines occupied spacetime_volume: ordinary cubes count 1, ports and pipes 0,
and Y half-cubes 0.5. These CNOT exports have no Y cubes. bounding_box includes
ports and reports coordinate extents (maximum minus minimum plus one).
The bounding-box product includes unoccupied sites.
Correlation-surface count is recorded as additional representation information.
See also the official [BGRAPH guide](https://tqec.github.io/tqec/user_guide/bgraph.html).

Native allocated volume, native TopoLS bounding-box volume, TQEC occupied volume,
and TQEC bounding-box volume are distinct quantities. Native data-slot density
also differs from active-data density. Native depth units are retained in JSON
and are not silently equated with physical execution times.

These checks support circuit meaning and a shared representation/accounting.
They do not prove all global fault-tolerance conditions, compile these graphs to
physical noisy circuits, or establish identical hardware conventions. Reserved
but unused factory/storage sites are not represented by occupied BlockGraph
cubes. A resource advantage therefore needs its metric and scope stated.

## Results

Fresh run: work/tqec-comparison. All four outputs passed structural validation,
input-circuit tensor equivalence and textual BGRAPH roundtrip checks.

| Input | Tool | Allocated footprint | Native depth | TQEC occupied volume | Official box including ports |
| --- | --- | --- | ---: | ---: | --- |
| mqt_max_parallel | this_work | 7 x 7 | 11 | 178 | 7 x 5 x 13 |
| mqt_max_parallel | topols | 7 x 5 | 20 | 343 | 7 x 5 x 21 |
| mqt_min_parallel | this_work | 7 x 7 | 11 | 166 | 5 x 6 x 13 |
| mqt_min_parallel | topols | 7 x 5 | 16 | 261 | 7 x 5 x 17 |

Native depth units differ as described above; this is representation accounting,
not a calibrated physical-performance comparison. This work now reserves 49 sites
and no MSF sites. See comparison.json for allocated volume and density metrics.
The occupied-volume counts agree with the native scheduler for both inputs.
Both tools have 12 logical ports and 12 recorded correlation surfaces per input.

The previous 9x9/MSF comparison is retained in work/comparison-msf-baseline/.
Run python scripts/render_figures.py to draw the four saved BlockGraphs
with TopoLS's upstream Matplotlib renderer (export/visualize.py).
The adapter retains positions, cube types and connections, with ports drawn grey.
Both methods use upstream renderer defaults. PNGs are saved directly in figures/.
Each model is independently fitted to its axes, so displayed sizes do not share
a common scale. The PNGs and Q-circuit diagrams are included in topols_comparison.tex.

## Reproducing the official-metric table

The four textual BlockGraphs are preserved in results/*.bgraph together with
comparison.json. tqec_interop.py writes the graphs directly to their final paths
as each case completes. A failed run may update only some graphs.
Run python scripts/analyze_structure.py to generate figures/block_graph_comparison.tex.
The script uses BlockGraph.from_bgraph(), validate(), bounding_box_size() and
spacetime_volume from TQEC, and checks dimensions and volume against comparison.json.
Available sites come from compiler settings. No existing work/ data is required.
The table reports available sites, port-inclusive dimensions and spacetime volume.
The former geometric categories and their diagnostic JSON have been removed.

## Provisional citation keys for the added subsection

All keys remain provisional; bibliography files are managed through Zotero.
The numerical experiment compares only this work and TopoLS. Citation of the
other tools is contextual discussion, not a claim that they were benchmarked.

- watkinsHighPerformanceCompiler2024: A high performance compiler for very large scale surface code computations (Quantum 8, 1354, 2024).
- leblondDirectCliffordTCompilation2023: Realistic Cost to Execute Practical Quantum Circuits using Direct Clifford+T Lattice Surgery Compilation. Upstream citation guidance: https://github.com/latticesurgery-com/liblsqecc#citing
- robertsonResourceAllocatingCompiler2025: https://arxiv.org/abs/2506.04620
- herzogCompilationBeyondSurfaceCode2025: https://arxiv.org/abs/2504.10591
- zhouTopoLS2026: https://arxiv.org/abs/2601.23109
- molaviDependencyAwareCompilation2025: https://doi.org/10.1145/3720416
- molaviGeneratingCompilers2026: https://arxiv.org/abs/2508.10781 (PACMPL 10, POPL, 2026).
- kanSparo2025: https://arxiv.org/abs/2504.21854
- tanSATScalpel2024: https://arxiv.org/abs/2404.18369
- tqecSoftware: Suau et al., tqec: A Python package for topological quantum error correction (JOSS, 2026). https://doi.org/10.21105/joss.09142
- mqtQECCSoftware: https://github.com/munich-quantum-toolkit/qecc

TopoLS was selected because its ZX-before-placement approach is directly relevant
to the reviewer's storage-density question, the same QASM inputs are accepted,
and its official TQEC exporter supplies a shared geometry representation.
This does not assert that other tools cannot be compared after further work.

## Scope of the revised subsection for Reviewer 2

The subsection adds a TopoLS experiment and cites Molavi's two compiler works,
Sparo and SAT scalpel, connecting this work to broader automated compilation.
It places automated patch-resource optimization alongside workload-specific
bespoke estimates, with provisional keys gidneyFactoring2025 (arXiv:2505.15917)
and gidneyEkeraFactoring2021 (Quantum 5, 433, 2021).
The primitive-cost questions (mixed/high-weight Pauli measurements and H/S cost)
require treatment in the problem setup or additional experiments. The present
CNOT-only experiment supplies occupied geometry and numerical tensor equivalence.
ZX preprocessing followed by bounded-depth routing is a proposed integration
requiring lowering to supported measurement primitives, not an implemented
combined compiler in these results. Active density 6/49 and asymptotic slot
density 25% refer to different quantities.

## Input-generator parameter rationale

These are synthetic circuits from MQT QECC 2.0.0's public circuit_construction.py,
not canonical named algorithm circuits. Both calls use the upstream default random seed.
Herzog et al., Lattice Surgery Compilation Beyond the Surface Code,
Section VII.B and Figure 10 (https://arxiv.org/html/2504.10591v2), evaluate
sequential, random and maximal CNOT circuit families. Figure 10 uses 24 qubits
and 4q gates per circuit. Our six-qubit, 24-gate inputs retain that 4q scaling
and contrast low and maximal initial parallelism. This provides a published
benchmark-family rationale, rather than a claim that either generator is
the most standard benchmark throughout MQT QECC.
layer_size=2 is our choice: the smallest group size above the serial case of 1.
For q=6, the max-parallel function generates three disjoint CNOTs per group;
the min-parallel function generates two and enforces at least one shared qubit
between successive groups. The returned list has no barriers, so generated
groups do not impose a strict global bound of two concurrent operations.
min_depth=24 denotes the gate-count target here, yielding eight groups of three
or twelve groups of two for the saved instances, not a schedule depth of 24.
The defaults and public generator make the examples traceable and reproducible;
choice of family, size and layer_size remains an experimental design choice.
These two instances illustrate the comparison at fixed size.

## OpenQASM declarations used by the input writer

Source: Cross et al., Open Quantum Assembly Language (2017), OpenQASM 2.0
specification, https://arxiv.org/pdf/1707.03429v2. Section 2 and Table 1 define
the version header, include statement, register declarations and zero-based
indexing. Section 3.1 gives qelib1.inc, defining lowercase cx via built-in CX,
with control first and target second. The six-qubit register size is our
benchmark choice. The official OpenQASM repository identifies this document
as its 2.0 specification: https://github.com/openqasm/openqasm/tree/OpenQASM2.x
A local PDF copy is retained in ignored work/references/openqasm-2.0-spec.pdf.
