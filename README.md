# Experiments With Running KLEE on Coreutils

## State
- Running first analyzes, with same versions as in KLEE paper

## TODOs
- Newer versions of coreutils
- Longer runs
- Coverage?

## Issues
### Coverage
The issue here is that KLEE describes measuring coverage using gcov. This leads to the original problem: You need to be able to build your system, which is tricky with older coreutils versions. You cannot do it on current ubuntu versions (see [this problem](/archive/02%20local-make/)). You can do it on older ubuntu versions (like ubuntu 14.04 for coreutils 6.10). However: while the binaries can be run in newer ubuntu containers, coverage is only recorded if an appropriate version of gcov is installed on the system. To record coverage, `klee-replay` has to be used, since it may involve complex setup. This however cannot be run in old ubuntu versions. One solution to this would be to run docker-in-docker: From within klee, start a docker container with an old ubuntu version, build the instrumented binary there, execute it, copy the results back to the klee container. But this doesn't work either: The setup (including files etc.) would also need to be put in the container and I doubt `klee-replay` would do this. And on top of that, the copying things back and forth is rather involved, since many tests need to be run on the same binary where the state needs to persist in between runs.

Basically, I have no solution for now. Which is unfortunate, because coverage might be an indicator of how today's hardware abstracted through docker compares to the hardware used for the KLEE paper.