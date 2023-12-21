if [ $# -ge 2 ]; then
    PATH_TO_COREUTILS=$1
    CURRENT_UTIL=$2
elif [ $# -ge 1  ] && ! [[ -z "${COREUTILS_STRING}" ]]; then
    PATH_TO_COREUTILS="./$COREUTILS_STRING"
    CURRENT_UTIL=$1
else
    echo "Usage: $0 [path_to_coreutils_source] [util_name]"
    echo "or:    $0 [util_name] with the env variable COREUTILS_STRING as the name of the coreutil source folder relative to the current directory"
    exit 1
fi

echo "including $PATH_TO_COREUTILS/lib"
echo "including $PATH_TO_COREUTILS"
echo "compiling $PATH_TO_COREUTILS/src/$CURRENT_UTIL.c"

clang \
    -I "$PATH_TO_COREUTILS/lib" \
    -I "$PATH_TO_COREUTILS" \
    -emit-llvm -c -g -O0 -Xclang -disable-O0-optnone \
    "$PATH_TO_COREUTILS/src/$CURRENT_UTIL.c"
