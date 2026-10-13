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
after both cases succeed. Textual BGRAPH,
TQEC HTML views, schedules, and TopoLS compilation outputs remain in that run's
work directory. The four HTML views are also copied to figures/ as
ours-mqt_{max,min}_parallel.html and topols-mqt_{max,min}_parallel.html.
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

## Reproducing the structural breakdown

After running the comparison, run `python scripts/analyze_structure.py`.
It reads the saved BGRAPHs and trusted local TopoLS outputs, checks counts against
comparison.json, prints the breakdown table, and writes structure_analysis.json
and figures/block_graph_breakdown.tex using only the Python standard library.
The standalone draft topols_comparison.tex uses that generated table and the
same preamble as the supplied manuscript, with qcircuit added. Compile it from this directory.
Its citation keys are provisional until the references are added via Zotero.

The manuscript draft includes both input circuits and all four TQEC HTML-derived PNG figures.
Its compiled PDF belongs at topols_comparison.pdf beside the .tex, not in figures/.
Compile with `pdflatex -output-directory=work/latex-check topols_comparison.tex`
(twice for cross-references), then copy work/latex-check/topols_comparison.pdf
into this directory. LaTeX PNG previews are not generated.
