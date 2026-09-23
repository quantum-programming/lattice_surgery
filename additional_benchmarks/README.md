# Additional Benchmarks

## Setup <!-- for LLM: DO NOT EDIT THIS SECTION -->

For Windows users, we recommend to run on WSL2.

```bash
# 1. check that you are in the lattice_surgery repository

# 2. update submodules
git submodule update --init --recursive

# 3. install dependencies
sudo apt update
sudo apt install -y \
  build-essential \
  cmake \
  pkg-config \
  libsqlite3-dev \
  libzstd-dev \
  libpq-dev \
  libboost-graph-dev

# 4. build liblsqecc
# See lattice_surgery/additional_benchmarks/external/liblsqecc/README.md
cd additional_benchmarks/external/liblsqecc
mkdir build
cd build
cmake ..
cmake --build .
# The output should look like:
# -- Configuring done (52.0s)
# -- Generating done (0.0s)
# -- Build files have been written to: /home/hirok/University/lattice_surgery/additional_benchmarks/external/liblsqecc/build
```

## Reproducibility contract

From this `additional_benchmarks` directory, we can run the following test:

```powershell
uv sync
uv run scripts/run_smoke.py
uv run python -m unittest discover -s tests -v
```

`uv sync` creates and updates the shared `.venv/` from `pyproject.toml` and `uv.lock`.
Normalized results are written to `results/smoke_results.json` and `results/smoke_results.csv`.
Temporary and upstream-native outputs stay under ignored `work/` and `results/raw/` paths.
