# Additional benchmarks

The active comparison is this work and TopoLS, using the two original six-qubit,
24-CNOT inputs. This work uses a 7x7 CNOT-only grid without MSF sites;
TopoLS keeps its standard 9x5 footprint. Both outputs are exported to TQEC BlockGraph. See
[COMPARISON.md](COMPARISON.md) for scope, sources, accounting, and results.

## Reproduction

Use Linux/WSL, Python 3.13, uv, and g++ with C++17 support. The pinned TopoLS and
TQEC submodules must already be initialized by the user. Run from this directory:

```bash
export UV_PROJECT_ENVIRONMENT=work/venv-wsl
uv sync --frozen
mkdir -p work
g++ -std=c++17 -O2 -D_GLIBCXX_ASSERTIONS scripts/ours_cnot.cpp -o work/ours_cnot
uv run --frozen python scripts/run_comparison.py
uv run --frozen python -m unittest discover -s tests -v
```

Each run recreates only work/tqec-comparison, replacing its previous contents.
Other work/ directories are retained. It updates comparison.json
after both cases succeed. Schedules and TopoLS intermediate compilation outputs
remain in that run's work directory. tqec_interop.py saves verified textual
BGRAPHs directly to results/ and official HTML views directly to figures/ as
ours-mqt_{max,min}_parallel.html and topols-mqt_{max,min}_parallel.html.
These files are updated per case, so a failed run may leave a partial update.
To capture the same official cube-and-pipe display for LaTeX, run on Windows:

```powershell
python scripts/render_html_figures.py
```

This uses existing Chrome/Edge and writes the four matching PNG files to figures/.
It hides only viewer controls and preserves TQEC's model, colors and default camera.
The browser needs network access to load the official viewer's three.js imports.
No browser package installation or custom geometric renderer is needed.
The manuscript uses these PNG captures and the two Q-circuit diagrams.

Python tests also run on Windows after `uv sync --frozen`, setting
`UV_PROJECT_ENVIRONMENT` to `work/venv-windows`.

## Optional input regeneration

To convert another CNOT-only OpenQASM 2 file to the native scheduler input,
run `python scripts/qasm2in.py input.qasm output.in` in the comparison environment.
This converter accepts arbitrary circuit sizes, preserves instruction order and
uses global qubit indices across registers. It rejects other operations and unused
qubits, which the native input format cannot represent. The comparison runner
uses the same conversion function but retains its six-qubit, 24-CNOT input check.

Normal comparison reads the checked-in QASM files and does not require MQT.
Its optional generator has a separate project and lockfile in benchmarks/:

```bash
UV_PROJECT_ENVIRONMENT=work/venv-inputs-wsl uv run --project benchmarks --frozen python benchmarks/generate_benchmarks.py
```

This always regenerates both QASM inputs and figures/mqt_max_parallel.tex and
figures/mqt_min_parallel.tex using MQT QECC 2.0.0. Qiskit generates Q-circuit
LaTeX bodies, which the manuscript reads directly with input. No circuit PNG
or PDF images are generated. The separate environment keeps generator
dependencies out of the comparison environment.

Ignored work/ contains older experiments that are not preserved by Git.
The current comparison artifacts are in work/tqec-comparison.
Stim is unused; the user manages removal of its submodule registration.

## Reproducing the comparison table

Run `python scripts/analyze_structure.py` on the saved results, using the comparison environment.
It loads results/*.bgraph through TQEC, validates each graph and obtains the
official spacetime_volume and bounding_box_size. It checks these values against
comparison.json and writes figures/block_graph_comparison.tex.
Preserve results/*.bgraph together with comparison.json from the same run.
No existing work/ data is required. Full compilation requires the executable
built from scripts/ours_cnot.cpp and dependencies installed from the lockfiles.
The standalone draft topols_comparison.tex uses that generated table and the
same preamble as the supplied manuscript, with qcircuit added. Compile it from this directory.
Its citation keys are provisional until the references are added via Zotero.

The manuscript draft includes both input circuits and all four TQEC HTML-derived PNG figures.
Its compiled PDF belongs at topols_comparison.pdf beside the .tex, not in figures/.
Compile with `pdflatex -output-directory=work/latex-check topols_comparison.tex`
(twice for cross-references), then copy work/latex-check/topols_comparison.pdf
into this directory. LaTeX PNG previews are not generated.

## Editor and type checking

Open additional_benchmarks.code-workspace in VS Code to keep the comparison and
input-generation projects in the same window with separate Python environments.
The comparison uses work/venv-windows; benchmark-inputs uses its own
work/venv-inputs-windows (under benchmarks/). If VS Code remembers a previously
selected interpreter, select the corresponding interpreter for each folder.
Pylance reads the local tool.pyright configuration; the mypy extension uses each
project's tool.mypy configuration. The configurations cover our Python sources,
not external submodule code or generated work files. Only missing type metadata
for the untyped Qiskit/TopoLS packages is ignored by mypy.

Run mypy from each project directory (additional_benchmarks, then benchmarks)
with --config-file pyproject.toml. Pyright can check all seven source files from
additional_benchmarks with --project pyproject.toml. These tools are development
checks, not runtime dependencies of the comparison.
