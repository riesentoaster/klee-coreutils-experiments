# Running KLEE on coreutils

[KLEE](https://klee.github.io) is an open-source, symbolic execution-based, advanced fuzzing tool. The [paper introducing it in OSDI 2008](http://www.doc.ic.ac.uk/~cristic/papers/klee-osdi-08.pdf) is one of the most-cited works in the space of symbolic execution-based fuzzing. I wanted to see if I can reproduce their findings with the current version of KLEE and perform some additional experiments. This repository contains all code and results from these experiments.

> WARNING: I kept fairly expensive records of each experiment, so this repository is >30GB.

All experiments were run on a virtuallized server with the following specs: AMD EPYC 7713 64C 225W 2.0GHz Processor, 1 TiB RAM, 2x 25GiB/s Ethernet.

## Running KLEE on the Correct Coreutils Version

I'm basing my experiment setup on the [original paper](http://www.doc.ic.ac.uk/~cristic/papers/klee-osdi-08.pdf), the [FAQs in the docs](http://klee.github.io/docs/coreutils-experiments/) and the [tutorial on testing a more recent version of coreutils](http://klee.github.io/tutorials/testing-coreutils/).

The experiments in the original paper used version 6.10 of coreutils, so this is where I started. And it's also where I ran into the first issue: KLEE is a complex program including complex additional packages such as SMT solvers, so i opted to run it from the provided Docker image. However, this image, at the time of the experiments, is based on Ubuntu 22 (Jammy), and can no longer build coreutils 6.10 with GCC. This is because the build system checks performs some checks on what system it is running on and those no longer work.

### Building coreutils 6.10 on a Current Version of Ubuntu

```bash
wget http://ftp.gnu.org/gnu/coreutils/coreutils-6.10.tar.gz
tar xf coreutils-6.10.tar.gz
mkdir coreutils-6.10/obj-llvm
cd coreutils-6.10/obj-llvm
../configure --disable-nls
make
```

#### Error

These are the last few lines of the output from `make`. The full output of the `configure` and `make` commands can be found [here](docs/build-coreutils-6.10-on-klee-image.txt), `freadahead.h` [here](docs/freadahead.h), and `freadahead.c` [here](docs/freadahead.c). 

```text
depbase=`echo freadahead.o | sed 's|[^/]*$|.deps/&|;s|\.o$||'`;\
gcc  -I. -I../../lib      -g -O2 -MT freadahead.o -MD -MP -MF $depbase.Tpo -c -o freadahead.o ../../lib/freadahead.c &&\
mv -f $depbase.Tpo $depbase.Po
../../lib/freadahead.c: In function 'freadahead':
../../lib/freadahead.c:64:3: error: #error "Please port gnulib freadahead.c to your platform! Look at the definition of fflush, fread on your system, then report this to bug-gnulib."
   64 |  #error "Please port gnulib freadahead.c to your platform! Look at the definition of fflush, fread on your system, then report this to bug-gnulib."
      |   ^~~~~
make[2]: *** [Makefile:1245: freadahead.o] Error 1
make[2]: Leaving directory '/home/klee/coreutils-6.10/obj-llvm/lib'
make[1]: *** [Makefile:905: all] Error 2
make[1]: Leaving directory '/home/klee/coreutils-6.10/obj-llvm/lib'
make: *** [Makefile:769: all-recursive] Error 1
```

### Using an Old Version of Ubuntu

Because coreutils use a complex build system, I opted to not try to update it to where it would work on a more recent version of Ubuntu and instead chose to just use an old version of Ubuntu to build the binaries and then copy them to the KLEE container. I also started keeping everything I did in Dockerfiles to both document the steps I took and enable me to reproduce each step. Plus Docker's caching made development and debugging significantly faster.

```Dockerfile
FROM ubuntu:14.04
RUN apt-get update \
    && apt-get install -y \
    wget \
    build-essential

RUN wget "http://ftp.gnu.org/gnu/coreutils/coreutils-6.10.tar.gz" \
    && tar xf "coreutils-6.10.tar.gz"

WORKDIR /coreutils-6.10/obj-cov
RUN ../configure --disable-nls \
    && make \
    && make -C src arch hostname
```

This worked! Now I have a way to build coreutils binaries.

## LLVM

KLEE uses LLVM bytecode as input files for its analysis. Compiling an ordinary `.c` file to LLVM can easily be done using `clang`. However, again, coreutils use a complex build system which means to just use `clang`, I'd have to deeply understand and modify it, which would take a lot of time.

Just using `clang` as the C compiler (with the `CC=clang` argument in the configure step) unfortunately does not work, because these files will obviously not be executable and the build system depends on that.

Luckily, there exists [Whole Program LLVM (wllvm)](https://github.com/travitch/whole-program-llvm), a tool specifically designed to work with complex build systems. From wllvm's README:

> WLLVM provides python-based compiler wrappers that work in two steps. The wrappers first invoke the compiler as normal. Then, for each object file, they call a bitcode compiler to produce LLVM bitcode. The wrappers also store the location of the generated bitcode file in a dedicated section of the object file. When object files are linked together, the contents of the dedicated sections are concatenated (so we don't lose the locations of any of the constituent bitcode files). After the build completes, one can use a WLLVM utility to read the contents of the dedicated section and link all of the bitcode into a single whole-program bitcode file. This utility works for both executable and native libraries.

Let's build coreutils using wllvm.
- I had to use an old version of wllvm, because newer versions require a version of python which is not available on Ubuntu 14.04.
- Two other arguments are passed in the `configure` step in preparation of running KLEE. The first is `--build x86_64-pc-linux-gnu`, because KLEE complains if the target tripplets don't match.
- The `CFLAGS` turn off optimization (because KLEE needs this) and enables some other flags according to the [KLEE docs](http://klee.github.io/tutorials/testing-coreutils/#step-3-build-coreutils-with-llvm).

```Dockerfile
FROM ubuntu:14.04 as build-llvm

RUN apt-get update \
    && apt-get install -y \
    wget \
    build-essential \
    clang \
    llvm \
    python3-pip

RUN wget "http://ftp.gnu.org/gnu/coreutils/coreutils-6.10.tar.gz" \
    && tar xf "coreutils-6.10.tar.gz"

RUN pip3 install --upgrade -v "wllvm==1.1.5" 

ENV LLVM_COMPILER clang
ENV CC wllvm
WORKDIR /coreutils-6.10/obj-llvm
RUN ../configure \
    --disable-nls \
    --build x86_64-pc-linux-gnu \
    LLVM_COMPILER=clang \
    CC=wllvm \
    CFLAGS="-O0 -D__NO_STRING_INLINES -D_FORTIFY_SOURCE=0 -U__OPTIMIZE__" \
    && make \
    && make -C src arch hostname

WORKDIR /coreutils-6.10/obj-llvm/src
RUN find . -executable -type f | xargs -I '{}' extract-bc '{}'
```

This leaves us with both executable and bytecode files:

```text
root@c892bf24028e:/coreutils-6.10/obj-llvm/src# ls -l
[...]
-rwxr-xr-x 1 root root 103112 Jan 11 12:06 chroot
-rw-r--r-- 1 root root 123308 Jan 11 12:07 chroot.bc
-rw-r--r-- 1 root root   9672 Jan 11 12:06 chroot.o
-rwxr-xr-x 1 root root 106255 Jan 11 12:06 cksum
-rw-r--r-- 1 root root 130596 Jan 11 12:07 cksum.bc
-rw-r--r-- 1 root root  21408 Jan 11 12:06 cksum.o
-rwxr-xr-x 1 root root 114630 Jan 11 12:06 comm
-rw-r--r-- 1 root root 143300 Jan 11 12:07 comm.bc
-rw-r--r-- 1 root root  22344 Jan 11 12:06 comm.o
[...]
```

### Running KLEE

These `.bc` LLVM files can now be copied to KLEE's docker image and KLEE can be run on them. Before starting the fuzzing process, KLEE needs to run in a specific environment. This is set up according to the [docs](http://klee.github.io/docs/coreutils-experiments/). The command is taken from the [FAQ](http://klee.github.io/docs/coreutils-experiments/), with only the path changed.

```Dockerfile
FROM klee/klee

RUN wget "http://www.doc.ic.ac.uk/~cristic/klee/testing-env.sh" \
    && env -i /bin/bash -c '(source testing-env.sh; env >test.env)' \
    && wget "http://www.doc.ic.ac.uk/~cristic/klee/sandbox.tgz" \
    && tar xzfv sandbox.tgz \
    && mv sandbox.tgz /tmp \
    && mv sandbox /tmp

# copying files from build stage
COPY --from=build-llvm --chown=klee /coreutils-6.10/ ./coreutils-llvm/

CMD klee --simplify-sym-indices --write-cvcs --write-cov --output-module \
--max-memory=1000 --disable-inlining --optimize --use-forked-solver \
--use-cex-cache --libc=uclibc --posix-runtime \
--external-calls=all --only-output-states-covering-new \
--env-file=test.env --run-in-dir=/tmp/sandbox \
--max-sym-array-size=4096 --max-solver-time=30s --max-time=60min \
--watchdog --max-memory-inhibit=false --max-static-fork-pct=1 \
--max-static-solve-pct=1 --max-static-cpfork-pct=1 --switch-type=internal \
--search=random-path --search=nurs:covnew \
--use-batching-search --batch-instructions=10000 \
./coreutils/obj-llvm/paste.bc --sym-args 0 1 10 --sym-args 0 2 2 --sym-files 1 8 --sym-stdin 8 --sym-stdout
```

Alright, we've got KLEE running on the correct coreutils version!
