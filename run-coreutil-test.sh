if [ 2 -gt $# ]; then
    echo "Usage: $0 <util> <run_out_path>"
    exit 1
fi

UTIL=$1
RUN_OUT_PATH=$2
KLEE_OUT_DIR="${KLEE_OUT_DIR:-./klee-out}"

if [ ! -d "$KLEE_OUT_DIR" ]; then
    mkdir $KLEE_OUT_DIR
fi

DOCKER_IMAGE_TAG=klee-coreutils
docker build -t $DOCKER_IMAGE_TAG .

INTERNAL_OUT_DIR=/home/klee/klee-out/
COMMAND="python3 ./run-klee.py $UTIL"

docker run --rm \
    -it \
    -e "KLEE_OUT_DIR=$INTERNAL_OUT_DIR$RUN_OUT_PATH" \
    -e "KLEE_MAX_TIME_MIN=1" \
    -v "$KLEE_OUT_DIR:$INTERNAL_OUT_DIR" \
    $DOCKER_IMAGE_TAG \
    $COMMAND
