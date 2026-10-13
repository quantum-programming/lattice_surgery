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
with six data sites, no MSF sites and 43 empty routing sites. TopoLS retains
its default 9x5 footprint (45 sites). The total spatial budgets are close;
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
ports; non_port_bounding_box excludes them. Both count coordinate extents
(maximum minus minimum plus one), and their products include unoccupied sites.
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

| Input | Tool | Allocated footprint | Native depth | TQEC occupied volume | Box excluding ports |
| --- | --- | --- | ---: | ---: | --- |
| mqt_max_parallel | this_work | 7 x 7 | 11 | 178 | 7 x 5 x 11 |
| mqt_max_parallel | topols | 9 x 5 | 22 | 404 | 9 x 5 x 22 |
| mqt_min_parallel | this_work | 7 x 7 | 11 | 166 | 5 x 6 x 11 |
| mqt_min_parallel | topols | 9 x 5 | 16 | 303 | 9 x 5 x 15 |

Native depth units differ as described above; this is representation accounting,
not a calibrated physical-performance comparison. This work now reserves 49 sites
and no MSF sites. See comparison.json for allocated volume and density metrics.
The occupied-volume counts agree with the native scheduler for both inputs.
Both tools have 12 logical ports and 12 recorded correlation surfaces per input.

The previous 9x9/MSF comparison is retained in work/comparison-msf-baseline/.
The official TQEC HTML cube-and-pipe views are copied to figures/ with ours-
and topols- prefixes. Run python scripts/render_html_figures.py on Windows to
capture the four HTML views using an existing Chrome/Edge browser. Only viewer
controls are hidden in work copies. Model data, colors and camera are unchanged.
The generated PNGs and the two Q-circuit LaTeX bodies are included in topols_comparison.tex.
Each model is independently fitted to the viewport, so image height is not a
common execution-time scale.

## Structural analysis of the saved outputs

Read-only analysis of the four saved textual BGRAPHs classifies every non-port
cube by its incident pipes: degree >=3 is a junction; degree 2 is a straight
space segment, straight time segment, or bend. These are geometric categories,
not a reconstruction of individual gates. All category totals match comparison.json.

| Input | Tool | Junctions | Straight time | Straight space | Bends | Total |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| mqt_max_parallel | ours | 48 | 18 | 12 | 100 | 178 |
| mqt_max_parallel | topols | 45 | 63 | 82 | 214 | 404 |
| mqt_min_parallel | ours | 48 | 18 | 4 | 96 | 166 |
| mqt_min_parallel | topols | 39 | 42 | 75 | 147 | 303 |

The excess is in degree-two wire subdivisions, not in additional junctions:
max_parallel has 229 more wire cubes and 3 fewer junctions in TopoLS (net +226);
min_parallel has 146 more wire cubes and 9 fewer junctions (net +137).
The spatial/time unit-pipe counts are 110/98 versus 267/167 for max_parallel,
and 100/96 versus 205/124 for min_parallel. Pipes have zero occupied volume;
these counts measure geometric length, not an additive volume breakdown.
Both spatial routing and temporal extent contribute; extra time alone does not
explain the output geometry.

This work's exact native decomposition is 66 data-pillar cubes (6 x 11), plus
112 or 100 off-pillar CNOT-route cubes. CNOT endpoints belong to the pillars,
so this partition avoids double counting.

TopoLS's saved native paths have no complete mapping to original CNOTs after
ZX simplification. A matching <node>_old to <node> path identifies a wire lift,
including ceiling/fallback lifts. There are 48 such paths in max_parallel and
36 in min_parallel. Their union intersects 184 and 127 occupied export cubes,
respectively. This includes shared endpoints and is NOT an additive partition
or the volume that could be saved by removing lifts. Unmatched paths cannot
all be labelled CNOT routes or data storage from this metadata alone.

Sources: TopoLS embedding/ports.py ceiling and seal_brute_frontier;
driver.py _commit_layer/_seal; export/bgraph.py merge_idle_paths.
This work: scripts/tqec_interop.py build_ours_positioned_zx.
Run python scripts/analyze_structure.py to reproduce the table and counts.
The full counts by time coordinate are written to structure_analysis.json,
and the manuscript table is generated as figures/block_graph_breakdown.tex. The active
comparison code and results were not changed for this analysis.

The measured result supports shorter connecting geometry in this-work exports.
Why the compiler chooses it (placement, layer sealing, routing constraints or
search budget) remains a causal hypothesis. Tensor equivalence and local
BlockGraph validation do not establish matched global fault-tolerance conditions
or physical timing conventions; no factor-of-two physical speedup is inferred.

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
- tqecSoftware: https://github.com/tqec/tqec
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
