# src

This directory contains the files for our proposed algorithms and their performance analysis.

## cpp

The directories `allocator`, `scheduler`, and `util` contain the header files implementing our proposed algorithms.
The C++ files are used for numerical experiments.
The main results will be saved in `out/table` as a CSV file.

## ipynb

This directory contains notebooks and code for analyzing the saved results.
Particularly, `paper_figures.ipynb` and `path_length_histogram.ipynb` reproduce the plots used in the paper.

## TeleportRouterSub

This directory contains the files required to apply the EDPC algorithm by Beverland et al. (2022) to our benchmark.
After precompiling the project `TeleportRouter.jl`, which is imported as a submodule, you can use `process_circuit.py` to apply their algorithm to our benchmark.
The results will be saved as `out/table/EDPC_results.csv`.

## \*.json & log_\*.py

The JSON files summarize the numerical experiment settings used in the paper.
These files are used by `log_metrics.py` and `log_all.py`, which execute the C++ files `log_metrics.cpp` and `log_all.cpp` in parallel, respectively.
Here is the list of options for `python log_metrics.py` and `python log_all.py`:
- `--process` or `-p`: The number of parallel processes. Defaults to `16`.
- `--config` or `-c`: Path to the JSON config file. Default values: `paper_figures.json` for `log_metric.py` and `path_length_histogram.json` for `log_all.py`.
- `--output` or `-o`: Path to the output CSV file (only in `log_metrics.py`). Default value: `../out/table/results.csv`.

# Reproducing Our Main Results

Here, we describe the procedure to reproduce the results in our paper.
As the results of the numerical experiments are already saved in this project,
you can directly skip to Step 4 if desired.

1\. Move to the directory `src/cpp` and compile `log_metrics.cpp` and `log_all.cpp` using the following:
```bash
g++ -O3 -march=native -mtune=native log_metrics.cpp -o log_metrics.out
g++ -O3 -march=native -mtune=native log_all.cpp -o log_all.out
```

2\. Move to the parent directory `src` and run the following to obtain the results in CSV format and compressed data files in `out/result/`.
```bash
python log_metrics.py
python log_all.py
```
See the section above, `*.json & log_*.py`, for optional arguments.
The former is necessary for running `paper_figures.ipynb`, and the latter is required for running `path_length_histogram.ipynb`.

3\. Move to the `TeleportRouter.jl` directory and set it up as a Julia project:
```bash
julia --project=@. -e 'using Pkg; Pkg.up(); Pkg.instantiate(); Pkg.precompile()'
```
Then, move to the directory `src/TeleportRouterSub` and execute the following to run the Julia code implementing the EDPC algorithm:
```bash
python process_circuit.py
```
This result is saved as `out/table/EDPC_results.csv`, which is required for running `paper_figures.ipynb`.

4\. After obtaining the results, you can run the cells in `paper_figures.ipynb `and `path_length_histogram.ipynb` to reproduce the figures in the paper.
