DOCKER_IMAGE_TAG=klee-coreutils
docker build -t "${DOCKER_IMAGE_TAG}-base" --target klee-coreutils-base . \
    && docker build -t "${DOCKER_IMAGE_TAG}-gcov" --target klee-coreutils-gcov . \
    && docker build -t "${DOCKER_IMAGE_TAG}-llvm" --target klee-coreutils-llvm . \
    && docker build -t "${DOCKER_IMAGE_TAG}" --target exec .