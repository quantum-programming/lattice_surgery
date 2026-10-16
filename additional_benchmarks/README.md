# Additional benchmarks

This directory reproduces the comparison with TopoLS on two eight-qubit,
32-CNOT circuit families over generation seeds 41--48. Five seeds have complete
paired results. Seed 45 supplies the manuscript circuit and geometry figures.

## Reproduction

Use Linux/WSL, Python 3.13, uv, and a C++17 compiler. Initialize the TopoLS and
TQEC submodules, apply the recorded temporary TopoLS fix, and run:

```bash
git -C external/TopoLS apply ../../patches/topols-branching-endpoint.patch
uv sync --frozen
uv sync --project benchmarks --frozen
uv run --frozen python scripts/run_circuit_seeds.py
uv run --frozen python -m unittest discover -s tests -v
```

The command generates all inputs, compiles both methods, verifies and
saves their TQEC BlockGraphs, writes `circuit_seeds.json`, regenerates the aggregate
LaTeX table, and renders the four seed-45 geometry figures.

Versioned experiment data are organized as follows:

- `benchmarks/`: all generated QASM inputs.
- `results/`: every successful BGRAPH output.
- `circuit_seeds.json`: configuration, input hashes, failures, metrics, and summaries.
- `figures/`: the aggregate table and seed-45 manuscript figures.

The comparison and generator environments remain visible at `.venv/` and
`benchmarks/.venv/`. See [COMPARISON.md](COMPARISON.md) for methodology,
accounting definitions, and the recorded results.
