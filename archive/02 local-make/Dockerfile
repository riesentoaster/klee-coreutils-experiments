# Idea: Use toolchain available in klee/klee to build the whole thing

FROM klee/klee

RUN sudo apt-get update \
    && sudo apt-get install -y libselinux-dev

# setting up klee env
RUN wget "http://www.doc.ic.ac.uk/~cristic/klee/testing-env.sh" \
    && env -i /bin/bash -c '(source testing-env.sh; env >test.env)' \
    && wget "http://www.doc.ic.ac.uk/~cristic/klee/sandbox.tgz" \
    && tar xzfv sandbox.tgz \
    && mv sandbox.tgz /tmp \
    && mv sandbox /tmp

# args (might occur multiple times)
ARG COREUTILS_VERSION=6.10

# initializing variables
ENV COREUTILS_STRING "coreutils-$COREUTILS_VERSION"
ENV COREUTILS_BIN_DIR "/$COREUTILS_STRING-bin"

# downloading source code
RUN wget "http://ftp.gnu.org/gnu/coreutils/$COREUTILS_STRING.tar.gz" \
    && tar -xf "$COREUTILS_STRING.tar.gz"

WORKDIR ${COREUTILS_STRING}
# configuring
RUN sh "./configure" --prefix="$COREUTILS_BIN_DIR"
RUN make
RUN make install
