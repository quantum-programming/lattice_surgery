# src

This directory contains files of our proposed algorithms and its performance analysis.

## cpp

Directories `allocator`, `scheduler`, and `util` contain the header files implementing our proposed algorithms.
Cpp files are used for numerical experiments.
The main results will be saved at `out/table` as a csv file.

## ipynb

It contains notebooks and codes for analyzing the saved results.
Particularly, `paper_figures.ipynb` reproduces the plots used in the paper.

## TeleportRouterSub

It contains files to apply the EDPC algorithm by Beverland et al. (2022) to our benchmark.
After precompiling the project `TeleportRouter.jl`, which is imported as a submodule, we can use `process_circuit.py` to apply their algorithm to our benchmark.
The results will be saved as `out/table/EDPC_results.csv`.

## config.json & log_metrics.py

The JSON file `config.json` summarizes the numerical experiment settings used in the paper.
This file is an input to `log_metrics.py`, which executes the cpp file `log_metrics.cpp` in parallel.
Here are the list of the options to the `python log_metrics.py`:
- `--process` or `-p`: The number of parallel processes. Defaults to `4`.
- `--config` or `-c`: Path to the JSON config file. Default value: `config.json`.
- `--output` or `-o`: Path to the output csv file. Default value: `../out/table/results.csv`.

# Reproducing Our Main Results

Here, we describe a procedure to reproduce our results in the paper.

1\. Move to the directory `src/cpp` and compile `log_metrics.cpp` by the following:
```bash
g++ -O3 -march=native -mtune=native log_metrics.cpp -o log_metrics.out
```

2\. Move to the parent directory `src` and run the following to obtain the results in a csv format.
```bash
python log_metrics.py
```
See the section above, `config.json & log_metrics.py`, for optional arguments.

You can also obtain additional results by
```bash
python log_all.py
```

3\. Move to the subdirectory `TeleportRouterSub` and execute the following to run the julia code implementing the EDPC algorithm. It may be required to set up the `TeleportRouter.jl` directory as a julia project.
```bash
python process_circuit.py
```

4\. After obtaining the results, you can run the cells of `paper_figures.ipynb` to reproduce the figures in the papers.
