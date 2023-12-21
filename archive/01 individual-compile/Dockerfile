# Idea: Compile individual coreutils directly within the klee container

FROM klee/klee

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

# copying run scripts
COPY compile-using-clang.sh ./

RUN ./compile-using-clang.sh ls