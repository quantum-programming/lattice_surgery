# Reviewer 1 comparison experiments

This directory is an isolated harness for the compiler comparisons requested by
Reviewer 1.  Existing paper code, data, and figures outside this directory are
not modified by the harness.

## Scope

The repositories under `external/` are pinned Git submodules:

- `liblsqecc`: Lattice Surgery Compiler C++ implementation.
- `TopoLS`: circuit-to-pipe compilation through a ZX intermediate representation.
- `Surface_Code_Compiler`: Robertson--Gao--Sanders resource-allocating compiler.
- `mqt_qecc`: MQT QECC, including the `cococo` routing implementation.
- `tqec`: pipe/block-graph-to-Stim backend and validation tools.

`tqec` is a backend smoke test, not a circuit-placement competitor.  MQT QECC's
published routing flow is color-code-oriented, so its results must not be
presented as a like-for-like surface-code volume comparison.

## Reproducibility contract

`benchmarks/*.json` is the canonical circuit representation used by the local
adapters.  Generated QASM is committed beside it so that textual inputs can be
inspected.  Every result row follows `results/schema.json` and records the
submodule commit, status, runtime, and metric definitions.

The smoke test uses a four-qubit CNOT-only circuit.  This deliberately tests the
shared routing subset before introducing differences in T-state factories,
single-qubit Clifford gates, and gate decomposition.

## Running the smoke test

From this directory:

```powershell
python scripts/run_smoke.py --setup
```

`--setup` creates tool-specific virtual environments under `.venv/`.  Subsequent
runs can omit it.  Normalized results are written to
`results/smoke_results.json` and `results/smoke_results.csv`; temporary and
upstream-native outputs stay under ignored `work/` and `results/raw/` paths.

`liblsqecc` must first be built into `work/liblsqecc-build`.  On Windows its
CMake configuration requires SQLite3 development headers and libraries in
addition to the installed MSVC toolchain.

## Current smoke-test status

At the pinned commits, TopoLS, Surface Code Compiler, MQT QECC/CoCoCo, and the
TQEC backend complete their smoke cases.  `liblsqecc` is recorded as `blocked`
because SQLite3 development files are not present in the current Windows build
environment.  See `results/smoke_results.json` and `results/manifest.json`.

These values establish API and execution viability only; they are not yet a
fair performance comparison.  In particular, Surface Code Compiler traverses
unordered sets in allocation/routing, and its active space-time volume varied
between smoke processes (37 and 45).  The full experiment must therefore use
repeated runs and report a distribution rather than rely on this single value.
