if [ 2 -gt $# ]; then
    echo "Usage: $0 [Dockerfile-path] [tagname]"
    exit 1
fi

if [ 4 -le $# ]; then
    TARGET="--target=$4"
    echo "adding target: $TARGET"
    REMAINING_ARG=$3
else
    TARGET=""
    REMAINING_ARG=$3
fi

docker build -t $2 -f $1 $TARGET . \
    && docker stop $2 || true \
    && docker rm $2 || true \
    && docker run --name $2 -it $2 $REMAINING_ARG
