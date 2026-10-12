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
g++ -std=c++17 -O2 -D_GLIBCXX_ASSERTIONS scripts/utils/ours_cnot.cpp -o work/ours_cnot
uv run --frozen python scripts/run_comparison.py
uv run --frozen python -m unittest discover -s tests -v
```

The runner refuses an existing output directory. To repeat a run, pass a fresh
path with `--output-dir work/tqec-comparison-repeat`. It updates comparison.json
and figures/structure_comparison.png after both cases succeed. Textual BGRAPH,
TQEC HTML views, schedules, and TopoLS compilation outputs remain in that run's
work directory. The structure PNG shows native geometry; the HTML views use the
same TQEC viewer for both tools.

Python tests also run on Windows after `uv sync --frozen`, setting
`UV_PROJECT_ENVIRONMENT` to `work/venv-windows`.

## Optional input regeneration

Normal comparison reads the checked-in QASM files and does not require MQT.
Its optional generator has a separate project and lockfile in benchmarks/:

```bash
UV_PROJECT_ENVIRONMENT=work/venv-inputs-wsl uv run --project benchmarks --frozen python benchmarks/generate_benchmarks.py --check
```

This checks exact reproduction by MQT QECC 2.0.0 without overwriting inputs.
Omitting --check regenerates the inputs and circuit figures. The separate
environment keeps generator dependencies out of the comparison environment.

SAT-only prototype files are preserved under ignored work/archive-sat and are
outside the active workflow. Stim is not needed by this workflow; its existing
submodule registration is left for the user to manage. external_results.json
and figures/native_external_results.png retain historical native-tool results.
