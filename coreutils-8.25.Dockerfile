# ========================================
# base
# ========================================
FROM ubuntu:16.04 as klee-coreutils-base

# installing dependencies
RUN apt-get update \
    && apt-get install -y \
    wget \
    build-essential \
    texinfo

# downloading source code
RUN wget "http://ftp.gnu.org/gnu/coreutils/coreutils-8.25.tar.xz" \
    && tar xf coreutils-8.25.tar.xz \
    && mv coreutils-8.25 coreutils

# modifying source code according to the documentation of the original experiment
# exit if nothing was changed
RUN sed -i.bak \
    's/^#define INPUT_FILE_SIZE_GUESS (128 \* 1024)$/#define INPUT_FILE_SIZE_GUESS 1024/g' \
    coreutils/src/sort.c \
    && [ "$(cmp coreutils/src/sort.c coreutils/src/sort.c.bak)" ] && rm coreutils/src/sort.c.bak || (rm coreutils/src/sort.c.bak; false)

# ========================================
# llvm
# ========================================

FROM klee-coreutils-base as klee-coreutils-llvm

RUN apt-get install -y \
    clang-3.5 \
    llvm-3.5 \
    python3-pip

RUN pip3 install --upgrade -v "pip==19" 
RUN pip3 install --upgrade -v "wllvm==1.1.5"

ENV LLVM_COMPILER clang
ENV LLVM_CC_NAME "clang-3.5"
ENV LLVM_CXX_NAME "clang-3.5"
ENV LLVM_LINK_NAME "llvm-link-3.5"
ENV CC wllvm

# compiling code to llvm bytecode (.bc)
WORKDIR /coreutils/obj-llvm
RUN FORCE_UNSAFE_CONFIGURE=1 \
    ../configure \
    --build x86_64-pc-linux-gnu \
    --disable-nls \
    CFLAGS="-g -O1 -disable-llvm-passes -D__NO_STRING_INLINES -D_FORTIFY_SOURCE=0 -U__OPTIMIZE__" 
RUN make

WORKDIR /coreutils/obj-llvm/src
RUN find . -executable -type f | xargs -I '{}' extract-bc '{}'

# ========================================
# gcov
# ========================================

FROM klee-coreutils-base as klee-coreutils-gcov

# compiling code to binaries instrumented with gcov
WORKDIR /coreutils/obj-cov
RUN FORCE_UNSAFE_CONFIGURE=1 \
    ../configure \
    --build x86_64-pc-linux-gnu \
    --disable-nls \
    CFLAGS="-O2 -g -fprofile-arcs -ftest-coverage" \
    && find .. -type f -name '*.c' -exec sed -i -E 's/\b_exit\(/exit(/g' {} + \
    && make

ENV COVERAGE_DATA_DIR /out/cov/src
ENV UTIL echo

WORKDIR /coreutils/obj-cov/src

CMD echo "Starting coverage gathering" \
    && echo "Copying coverage files" \
    && cp -r "$COVERAGE_DATA_DIR"/* "/coreutils/obj-cov/src/" \
    && echo "Running gcov" \
    && gcov "$UTIL" > "/out/cov.txt" \
    && echo "Coverage gathering done" \
    && tar czf "/out/src-gcov.tar.gz" "/coreutils/obj-cov/src"

# ========================================
# exec
# ========================================

FROM klee/klee AS klee-coreutils-exec

# setting up klee env
RUN wget "http://www.doc.ic.ac.uk/~cristic/klee/testing-env.sh" \
    && env -i /bin/bash -c '(source testing-env.sh; env >test.env)' \
    && wget "http://www.doc.ic.ac.uk/~cristic/klee/sandbox.tgz" \
    && tar xzfv sandbox.tgz \
    && mv sandbox.tgz /tmp \
    && mv sandbox /tmp

# copying files from build stage
COPY --from=klee-coreutils-llvm --chown=klee /coreutils/ ./coreutils-llvm/
COPY --from=klee-coreutils-gcov --chown=klee /coreutils/ ./coreutils-gcov/

# copying run scripts
COPY analyze.sh ./

# setting default values for analyze script
# can be overridden using -e in docker run
ENV KLEE_MAX_TIME_MIN 60
ENV UTIL echo
ENV SKIP_KLEE_ANALYSIS ""

CMD bash ./analyze.sh \
    --llvm-dir ./coreutils-llvm/obj-llvm/src \
    --cov-dir ./coreutils-gcov/obj-cov/src \
    --skip-klee-analysis "${SKIP_KLEE_ANALYSIS}" \
    --klee-max-time "${KLEE_MAX_TIME_MIN}" \
    --out-dir ./out \
    "${UTIL}" \
    && tar czf ./out/src-llvm.tar.gz ./coreutils-llvm/obj-llvm/src

# to keep files output by klee, run the container as follows:
# `docker run [docker_args] \
# -v <path/on/your/system>:/home/klee/out \
# <image-name>`
