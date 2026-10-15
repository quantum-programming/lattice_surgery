# Additional benchmarks

The active comparison is this work and TopoLS on eight-qubit, 32-CNOT
max-parallel and min-parallel circuit families. The manuscript table aggregates
five paired circuit-generation seeds, while the figures use seed 45. Both tools
use a 7x7 spatial allocation for these inputs.
This work's CNOT-only grid has no MSF sites.
Both outputs are exported to TQEC BlockGraph. See
[COMPARISON.md](COMPARISON.md) for scope, sources, accounting, and results.

## Reproduction

Use Linux/WSL, Python 3.13, uv, and g++ with C++17 support. The pinned TopoLS and
TQEC submodules must already be initialized by the user. The environments live
in the visible `.venv/` directories of this project and `benchmarks/`. Run from
this directory:

```bash
# Apply this only when the submodule is clean; run_comparison.py verifies it.
git -C external/TopoLS apply --check ../../patches/topols-branching-endpoint.patch
git -C external/TopoLS apply ../../patches/topols-branching-endpoint.patch
uv sync --frozen
mkdir -p work
g++ -std=c++17 -O2 -D_GLIBCXX_ASSERTIONS scripts/ours_cnot.cpp -o work/ours_cnot
uv run --frozen python scripts/run_comparison.py
uv run --project benchmarks --frozen python benchmarks/generate_benchmarks.py --sweep-seeds 41 42 43 44 45 46 47 48
uv run --frozen python scripts/run_seed_sweep.py
uv run --frozen python scripts/analyze_seed_sweep.py
uv run --frozen python -m unittest discover -s tests -v
```

Each run recreates only work/tqec-comparison, replacing its previous contents.
Other work/ directories are retained. It updates comparison.json
after both cases succeed. Schedules and TopoLS intermediate compilation outputs
remain in that run's work directory. tqec_interop.py saves verified textual
BGRAPHs directly to results/. These files are updated per case.
To render the four manuscript images from saved graphs, run:

```powershell
python scripts/render_figures.py
```

This uses TopoLS's upstream Matplotlib cube-and-pipe renderer for both methods
and writes PNGs directly to figures/. A small adapter supplies graph metadata.
Renderer geometry, colours and camera use upstream defaults. No browser or
network connection is required. The manuscript uses these PNGs and the two
Q-circuit diagrams.

Python tests also run on Windows after `uv sync --frozen`; uv uses `.venv/`
in this directory on both platforms.

## Optional input regeneration

To convert another CNOT-only OpenQASM 2 file to the native scheduler input,
run `python scripts/qasm2in.py input.qasm output.in` in the comparison environment.
This converter accepts arbitrary circuit sizes, preserves instruction order and
uses global qubit indices across registers. It rejects other operations and unused
qubits, which the native input format cannot represent. The comparison runner
uses the same conversion function but retains its eight-qubit, 32-CNOT input check.

Normal comparison reads the checked-in QASM files and does not require MQT.
Its optional generator has a separate project and lockfile in benchmarks/:

```bash
uv sync --project benchmarks --frozen
uv run --project benchmarks --frozen python benchmarks/generate_benchmarks.py
```

Without `--sweep-seeds`, this regenerates both QASM inputs and
figures/mqt_max_parallel.tex and figures/mqt_min_parallel.tex using MQT QECC
2.0.0. Qiskit generates Q-circuit LaTeX bodies, which the manuscript reads
directly with input. No circuit PNG or PDF images are generated. The separate
environment keeps generator dependencies out of the comparison environment.

The seed sweep varies only the MQT input-generation seed. Compiler search seeds
remain fixed. It records every attempted case in seed_sweep.json and calculates
paired statistics only from seeds for which both tools pass export, validation,
and circuit-equivalence checks. Intermediate files are kept in
work/seed-sweep/, and the aggregate LaTeX table is written to
figures/seed_sweep_comparison.tex. The seed-45 circuits remain the examples used
for the circuit and geometry figures.

Ignored work/ contains older experiments that are not preserved by Git.
The current comparison artifacts are in work/tqec-comparison.
Stim is unused; the user manages removal of its submodule registration.

## Reproducing the comparison tables

Run `python scripts/analyze_structure.py` on the saved results, using the comparison environment.
It loads results/*.bgraph through TQEC, validates each graph and obtains the
official spacetime_volume and bounding_box_size. It checks these values against
comparison.json and writes figures/block_graph_comparison.tex.
Preserve results/*.bgraph together with comparison.json from the same run.
Run `python scripts/analyze_seed_sweep.py` to reproduce the aggregate manuscript
table from seed_sweep.json. The single-instance table remains a diagnostic for
the four illustrated seed-45 graphs; the manuscript uses the aggregate table.
No existing work/ data is required. Full compilation requires the executable
built from scripts/ours_cnot.cpp and dependencies installed from the lockfiles.
The standalone draft topols_comparison.tex uses that generated table and the
same preamble as the supplied manuscript, with qcircuit added. Compile it from this directory.
Its citation keys are provisional until the references are added via Zotero.

The manuscript draft includes both input circuits and all four BlockGraph PNGs rendered with TopoLS.
Its compiled PDF belongs at topols_comparison.pdf beside the .tex, not in figures/.
Compile with `pdflatex -output-directory=work/latex-check topols_comparison.tex`
(twice for cross-references), then copy work/latex-check/topols_comparison.pdf
into this directory. LaTeX PNG previews are not generated.

## Editor and type checking

Open additional_benchmarks.code-workspace in VS Code to keep the comparison and
input-generation projects in the same window with separate Python environments.
The comparison uses `.venv/`; benchmark-inputs uses its own `benchmarks/.venv/`.
If VS Code remembers a previously selected interpreter, select the corresponding
interpreter for each folder.
Pylance reads the local tool.pyright configuration; the mypy extension uses each
project's tool.mypy configuration. The configurations cover our Python sources,
not external submodule code or generated work files. Only missing type metadata
for the untyped Qiskit/TopoLS packages is ignored by mypy.

Run mypy from each project directory (additional_benchmarks, then benchmarks)
with --config-file pyproject.toml. Pyright can check the maintained source files
from additional_benchmarks with --project pyproject.toml. These tools are development
checks, not runtime dependencies of the comparison.
