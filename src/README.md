# src

This directory contains files of our proposed algorithms and its performance analysis.

## cpp

Directories `allocator`, `scheduler`, and `util` contain the header files implementing our proposed algorithms.
Cpp files are used for numerical experiments.
The main results will be saved at `out/table` as a csv file.

## ipynb

It contains notebooks and codes for analyzing the saved results.
Particularly, `paper_figures.ipynb` and `path_length_histogram.ipynb` reproduce the plots used in the paper.

## TeleportRouterSub

It contains files to apply the EDPC algorithm by Beverland et al. (2022) to our benchmark.
After precompiling the project `TeleportRouter.jl`, which is imported as a submodule, we can use `process_circuit.py` to apply their algorithm to our benchmark.
The results will be saved as `out/table/EDPC_results.csv`.

## \*.json & log_\*.py

The JSON files summarizes the numerical experiment settings used in the paper.
These files are used by `log_metrics.py` and `log_all.py`, which execute the cpp files `log_metrics.cpp` and `log_all.cpp` in parallel, respectively.
Here are the list of the options to the `python log_metrics.py` and `python log_all.py`:
- `--process` or `-p`: The number of parallel processes. Defaults to `16`.
- `--config` or `-c`: Path to the JSON config file. Default values: `paper_figures.json` for `log_metric.py` and `path_length_histogram.json` for `log_all.py`.
- `--output` or `-o`: Path to the output csv file (only in `log_metrics.py`). Default value: `../out/table/results.csv`.

# Reproducing Our Main Results

Here, we describe a procedure to reproduce our results in the paper.
As the result of numerical experiments are already saved in this project,
you can directly move to Step 5, if desired.

1\. Move to the directory `src/cpp` and compile `log_metrics.cpp` and `log_all.cpp` by the following:
```bash
g++ -O3 -march=native -mtune=native log_metrics.cpp -o log_metrics.out
g++ -O3 -march=native -mtune=native log_all.cpp -o log_all.out
```

2\. Move to the parent directory `src` and run the following to obtain the results as a csv format and compressed data files in `out/result/`.
```bash
python log_metrics.py
python log_all.py
```
See the section above, `*.json & log_*.py`, for optional arguments.
The former is necessary for running `paper_figures.ipynb`, and the latter is required for running `path_length_histogram.ipynb`.

3\. Move to the `TeleportRouter.jl` directory and set it up as a julia project.
```bash
julia --project=@. -e 'using Pkg; Pkg.up(); Pkg.instantiate(); Pkg.precompile()'
```
Then, move to the directory `src/TeleportRouterSub` and execute the following to run the julia code implementing the EDPC algorithm.
```bash
python process_circuit.py
```
This result is saved as `out/table/EDPC_results.csv`, which is required for running `paper_figures.ipynb`.

5\. After obtaining the results, you can run the cells of `paper_figures.ipynb` and `path_length_histogram.ipynb` to reproduce the figures in the papers.
