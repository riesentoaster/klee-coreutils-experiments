# Running KLEE on coreutils

[KLEE](https://klee.github.io) is an open-source, symbolic execution-based, advanced fuzzing tool. The [paper introducing it in OSDI 2008](http://www.doc.ic.ac.uk/~cristic/papers/klee-osdi-08.pdf) is one of the most-cited works in the space of symbolic execution-based fuzzing. I wanted to see if I can reproduce their findings with the current version of KLEE and perform some additional experiments. This repository contains all code and results from these experiments.

> WARNING: I kept fairly expensive records of each experiment, so this repository is >30GB.

## Repository Contents
This repository contains the following:
- Code to run the experiments
  - `[*.]Dockerfile`: The setup for three different versions of coreutils.
  - [`analyze.sh`](./analyze.sh): Script performing the actual analysis.
  - [`run-suite.py`](./run-suite.py): Script orchestrating a run across all 89 coreutils.
- Results and result analysis
  - [out](./out): The raw outputs from all 19 suite runs performed during this project
  - [`analyze.ipynb`](./analyze.ipynb): Scripts to analyze the raw outputs
  - [plots](./plots): A series of plots on the results
- The [report](./report/report.pdf) of the project

## Report
The report of this project can be found [here](./report/report.pdf).