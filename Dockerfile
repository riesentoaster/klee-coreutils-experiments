# ========================================
# base
# ========================================

ARG BASE_IMAGE=ubuntu:14.04
FROM ${BASE_IMAGE} as klee-coreutils-compile

# installing dependencies
RUN apt-get update \
    && apt-get install -y \
    wget \
    build-essential \
    clang \
    llvm \
    python3-pip

# args (might occur multiple times)
ARG COREUTILS_VERSION=6.10

# downloading source code
RUN wget "http://ftp.gnu.org/gnu/coreutils/coreutils-${COREUTILS_VERSION}.tar.gz" \
    && tar -xf "coreutils-${COREUTILS_VERSION}.tar.gz" \
    && mv "coreutils-${COREUTILS_VERSION}" coreutils

# modifying source code according to the documentation of the original experiment
RUN sed -i \
    's/^#define INPUT_FILE_SIZE_GUESS (1024 \* 1024)$/#define INPUT_FILE_SIZE_GUESS 1024/g' \
    coreutils/src/sort.c

ARG WLLVM_VERSION=1.1.5
# Newer versions do not work with python 3.4 (which is the most recent version
# available through apt for ubuntu 14.04)
RUN pip3 install --upgrade -v "wllvm==${WLLVM_VERSION}" 

# The version using -O1 etc. proposed in the tutorial does not work for this version of llvm
# and does not seem necessary either (since the most recent version of clang is based on LLVM 3.4)
ARG CFLAGS_WLLVM="-O0 -D__NO_STRING_INLINES -D_FORTIFY_SOURCE=0 -U__OPTIMIZE__"
ENV LLVM_COMPILER clang
ENV CC wllvm

# compiling code to llvm bytecode (.bc)
WORKDIR /coreutils/obj-llvm
RUN ../configure \
    --build x86_64-pc-linux-gnu \
    --disable-nls \
    LLVM_COMPILER=clang \
    CC=wllvm \
    CFLAGS="${CFLAGS_WLLVM}"
RUN make
RUN make -C src arch hostname
WORKDIR /coreutils/obj-llvm/src
RUN find . -executable -type f | xargs -I '{}' extract-bc '{}'

# compiling code instrumented with gcov
WORKDIR /coreutils/obj-cov
RUN ../configure \
    --build x86_64-pc-linux-gnu \
    --disable-nls \
    LLVM_COMPILER=clang \
    CC=wllvm \
    CFLAGS="${CFLAGS_WLLVM} --coverage"
RUN make
RUN make -C src arch hostname

# ========================================
# exec
# ========================================

FROM klee/klee AS exec

# setting up klee env
RUN wget "http://www.doc.ic.ac.uk/~cristic/klee/testing-env.sh" \
    && env -i /bin/bash -c '(source testing-env.sh; env >test.env)' \
    && wget "http://www.doc.ic.ac.uk/~cristic/klee/sandbox.tgz" \
    && tar xzfv sandbox.tgz \
    && mv sandbox.tgz /tmp \
    && mv sandbox /tmp

# copying files from build stage
COPY --from=klee-coreutils-compile --chown=klee /coreutils/ ./coreutils-llvm/

# copying run scripts
COPY analyze.sh ./

# setting default values for analyze script
# can be overridden using -e in docker run
ENV KLEE_MAX_TIME_MIN 60
ENV UTIL echo

CMD bash ./analyze.sh \
    --llvm-dir ./coreutils-llvm/obj-llvm/src \
    --cov-dir ./coreutils-llvm/obj-cov/src \
    --klee-max-time ${KLEE_MAX_TIME_MIN} \
    --out-dir ./out \
    ${UTIL} \
    && cp -r ./coreutils-llvm/obj-llvm/src ./out/src-llvm/ \
    && cp -r ./coreutils-llvm/obj-cov/src ./out/src-cov/ 

# to keep files output by klee, run the container as follows:
# `docker run [docker_args] \
# -v <path/on/your/system>:/home/klee/out \
# <image-name>`
