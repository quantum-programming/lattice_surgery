# Additional benchmarks

The active comparison is this work and TopoLS, using the two original six-qubit,
24-CNOT inputs. Both outputs are exported to TQEC BlockGraph. See
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
Both tools use the same official TQEC viewer. Open these HTML files in a browser.

Python tests also run on Windows after `uv sync --frozen`, setting
`UV_PROJECT_ENVIRONMENT` to `work/venv-windows`.

## Optional input regeneration

Normal comparison reads the checked-in QASM files and does not require MQT.
Its optional generator has a separate project and lockfile in benchmarks/:

```bash
UV_PROJECT_ENVIRONMENT=work/venv-inputs-wsl uv run --project benchmarks --frozen python benchmarks/generate_benchmarks.py
```

This always regenerates both QASM inputs and figures/mqt_max_parallel.png and
figures/mqt_min_parallel.png using MQT QECC 2.0.0. The separate environment
keeps generator dependencies out of the comparison environment.

Ignored work/ contains older experiments that are not preserved by Git.
The current comparison artifacts are in work/tqec-comparison.
Stim is unused; the user manages removal of its submodule registration.
