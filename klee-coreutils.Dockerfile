ARG BASE_IMAGE=ubuntu:14.04
FROM $BASE_IMAGE AS build

# installing dependencies
RUN apt-get update \
    && apt-get install -y \
    wget \
    build-essential \
    clang \
    llvm \
    python3-pip

ARG WLLVM_VERSION=1.1.5
# Newer versions do not work with python 3.4
# (which is the most recent version available through apt)
RUN pip3 install --upgrade -v "wllvm==${WLLVM_VERSION}" 

# args (might occur multiple times)
ARG COREUTILS_VERSION=6.10

# downloading source code
RUN wget "http://ftp.gnu.org/gnu/coreutils/coreutils-${COREUTILS_VERSION}.tar.gz" \
    && tar -xf "coreutils-${COREUTILS_VERSION}.tar.gz" \
    && mv "coreutils-${COREUTILS_VERSION}" coreutils

# modifying source code according to the original mod
RUN sed -i \
    's/^#define INPUT_FILE_SIZE_GUESS (1024 \* 1024)$/#define INPUT_FILE_SIZE_GUESS 1024/g' \
    coreutils/src/sort.c

# compiling

# The version using -O1 etc. proposed in the tutorial does not work for this version of llvm
# and does not seem necessary either (since the most recent version of clang is based on LLVM 3.4)
ARG CFLAGS="-O0 -D__NO_STRING_INLINES -D_FORTIFY_SOURCE=0 -U__OPTIMIZE__"

WORKDIR "/coreutils/obj-llvm"
ENV LLVM_COMPILER clang
ENV CC wllvm
RUN ../configure \
    --build x86_64-pc-linux-gnu \
    LLVM_COMPILER=clang \
    CC=wllvm \
    CFLAGS="${CFLAGS}"
RUN make
RUN make -C src arch hostname

WORKDIR "/coreutils/obj-llvm/src"
RUN find . -executable -type f | xargs -I '{}' extract-bc '{}'

FROM klee/klee AS exec

# setting up klee env
RUN wget "http://www.doc.ic.ac.uk/~cristic/klee/testing-env.sh" \
    && env -i /bin/bash -c '(source testing-env.sh; env >test.env)' \
    && wget "http://www.doc.ic.ac.uk/~cristic/klee/sandbox.tgz" \
    && tar xzfv sandbox.tgz \
    && mv sandbox.tgz /tmp \
    && mv sandbox /tmp

# copying files from build stage
COPY --from=build --chown=klee /coreutils coreutils
ENV CORETUILS_BC_PATH ./coreutils/obj-llvm/src/

# copying run scripts
COPY run-klee.py ./

# you might want to run python3 ./run-klee.py <util>