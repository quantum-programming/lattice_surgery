# This work and TopoLS through TQEC BlockGraph

## Scope and reading order

We use the original mqt_max_parallel and mqt_min_parallel inputs: each has six
qubits and 24 CNOT gates. SAT trials and the three-qubit pilot are excluded.
This note is separate from the reviewer response; npj_reviewer1.md is untouched.
The current manuscript has not been assessed here.

Read scripts/run_comparison.py for the complete workflow, scripts/utils/ours_cnot.cpp
for the call to the existing native implementation, scripts/utils/run_topols.py
for upstream compiler options, then scripts/utils/tqec_interop.py for conversion,
validation, and accounting. No core compiler headers or external submodule code
are changed. Setup and commands are in [README.md](README.md).

This work uses one layer, outer factories, SA seed 1 and 1,000,000 iterations,
Double look-ahead and CareKinkParity. TopoLS uses its supplied docs/prog.py with
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

| Input | Tool | Native depth | TQEC occupied volume | Box including ports | Box excluding ports |
| --- | --- | ---: | ---: | --- | --- |
| mqt_max_parallel | this_work | 11 | 178 | 7 x 5 x 13 | 7 x 5 x 11 |
| mqt_max_parallel | topols | 22 | 404 | 9 x 5 x 23 | 9 x 5 x 22 |
| mqt_min_parallel | this_work | 11 | 166 | 5 x 6 x 13 | 5 x 6 x 11 |
| mqt_min_parallel | topols | 16 | 303 | 9 x 5 x 17 | 9 x 5 x 15 |

Native depth units differ as described above. The table is representation
accounting, not a calibrated physical-performance comparison. This work reserves
81 sites for 11 beats (allocated volume 891) in both cases. TopoLS reports
native bounding-box volumes 990 and 720; these are not occupied volumes.
The this-work TQEC occupied volumes, 178 and 166, equal native occupied counts.
Both tools have 12 logical ports and 12 recorded correlation surfaces per input.

The same TQEC viewer writes four HTML files beside the BGRAPH exports.
figures/structure_comparison.png shows native geometry for mqt_min_parallel.
