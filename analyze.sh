#!/bin/bash

# ========================================
# arg parsing
# ========================================

POSITIONAL_ARGS=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --llvm-dir)
      LLVM_DIR="$2"
      shift # past argument
      shift # past value
      ;;
    --cov-dir)
      COV_DIR="$2"
      shift # past argument
      shift # past value
      ;;
    --klee-max-time)
      KLEE_MAX_TIME_MIN="$2"
      shift # past argument
      shift # past value
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift # past argument
      shift # past value
      ;;
    -*|--*)
      echo "Unknown option $1"
      exit 1
      ;;
    *)
      POSITIONAL_ARGS+=("$1") # save positional arg
      shift # past argument
      ;;
  esac
done

set -- "${POSITIONAL_ARGS[@]}" # restore positional parameters

if [ 1 -gt $# ]; then
  echo "Usage: $0 <util>"
  echo "Args:"
  echo "--llvm-dir             The directory where the llvm .bc files are stored"
  echo "--cov-dir              The directory where the binaries instrumented with gcov are stored"
  echo "--klee-max-time        The timeout after which KLEE stops its analysis"
  echo "--out-dir              The output directory"
  exit 1
fi

UTIL=$1
echo "Testing util \"${UTIL}\""

# ========================================
# KLEE analysis
# ========================================

LLVM_DIR=${LLVM_DIR-./llvm}
COV_DIR=${COV_DIR-./cov}
KLEE_MAX_TIME_MIN=${KLEE_MAX_TIME_MIN-60}
OUT_DIR=${OUT_DIR-./out}

echo "Assuming input directory for llvm files ${LLVM_DIR}"
echo "Assuming input directory for gcov instrumented files ${COV_DIR}"
echo "Setting output directory: ${OUT_DIR}"
echo "Setting KLEE's timeout to ${KLEE_MAX_TIME_MIN}"

mkdir -p $OUT_DIR

# according to the documentation from the original experiment
case $UTIL in
    dd)
        UTIL_ARGS="--sym-args 0 3 10 --sym-files 1 8 --sym-stdin 8 --sym-stdout" ;;
    dircolors)
        UTIL_ARGS="--sym-args 0 3 10 --sym-files 2 12 --sym-stdin 12 --sym-stdout" ;;
    echo)
        UTIL_ARGS="--sym-args 0 4 300 --sym-files 2 30 --sym-stdin 30 --sym-stdout" ;;
    expr)
        UTIL_ARGS="--sym-args 0 1 10 --sym-args 0 3 2 --sym-stdout" ;;
    mknod)
        UTIL_ARGS="--sym-args 0 1 10 --sym-args 0 3 2 --sym-files 1 8 --sym-stdin 8 --sym-stdout" ;;
    od)
        UTIL_ARGS="--sym-args 0 3 10 --sym-files 2 12 --sym-stdin 12 --sym-stdout" ;;
    pathchk)
        UTIL_ARGS="--sym-args 0 1 2 --sym-args 0 1 300 --sym-files 1 8 --sym-stdin 8 --sym-stdout" ;;
    printf)
        UTIL_ARGS="--sym-args 0 3 10 --sym-files 2 12 --sym-stdin 12 --sym-stdout" ;;
    *)
        UTIL_ARGS="--sym-args 0 1 10 --sym-args 0 2 2 --sym-files 1 8 --sym-stdin 8 --sym-stdout" ;;
esac

# taken from the documentation with a few differences:
# --max-time is usually fixed on `60min`
# --output-dir is usually not set
KLEE_COMMAND="\
  klee --simplify-sym-indices --write-cvcs --write-cov --output-module \
  --max-memory=1000 --disable-inlining --optimize --use-forked-solver \
  --use-cex-cache --libc=uclibc --posix-runtime \
  --external-calls=all --only-output-states-covering-new \
  --env-file=test.env --run-in-dir=/tmp/sandbox \
  --max-sym-array-size=4096 --max-solver-time=30s --max-time=${KLEE_MAX_TIME_MIN}min \
  --watchdog --max-memory-inhibit=false --max-static-fork-pct=1 \
  --max-static-solve-pct=1 --max-static-cpfork-pct=1 --switch-type=internal \
  --search=random-path --search=nurs:covnew \
  --use-batching-search --batch-instructions=10000 \
  --output-dir=${OUT_DIR}/klee \
  ${LLVM_DIR}/${UTIL}.bc \
  ${UTIL_ARGS}"

echo -e "\nRunning KLEE as follows:\n${KLEE_COMMAND}\n"

eval "$KLEE_COMMAND" > $OUT_DIR/klee-stdout.log 2> $OUT_DIR/klee-stderr.log
KLEE_EXIT_CODE=$?

if [ $KLEE_EXIT_CODE -ne 0 ]; then
  echo "WARNING: KLEE failed, check logs in ${OUT_DIR}/klee-stderr.log"
  echo -e "Here are the last few lines of the logs:\n\n"
  tail -n 10 $OUT_DIR/klee-stderr.log
fi

# ========================================
# Exporting information about crashes
# ========================================

echo "Exporting args for crashing test cases using ktest-tool"
for f in $(ls "${OUT_DIR}/klee" | grep -e "\.err$"); do
  TEST_NR=$(echo $f | cut --d="." --f=1 )
  ktest-tool "${OUT_DIR}/klee/${TEST_NR}.ktest" > "${OUT_DIR}/klee/${TEST_NR}.err.ktest.txt"
done

# ========================================
# Exporting global stats
# ========================================

echo "Exporting stats about the test run"
klee-stats "${OUT_DIR}/klee" --print-all --table-format=csv > "${OUT_DIR}/klee-stats.csv"

# ========================================
# Getting coverage
# ========================================

echo "Collecting coverage data"
find "${OUT_DIR}/klee" -type f -name "*.ktest" | while read f; do
  # the timeout is necessary for programs that wait for something, like `tail -f` or `yes`
  # the env variables make sure that the output is actually written
  # for some reason, it is required for the actual util to produce an output
  # likely related to the fact that the directory structure on the build and test systems differ
  GCOV_PREFIX=$(realpath "${OUT_DIR}/cov") \
  GCOV_PREFIX_STRIP=2 \
    timeout "10s" \
      klee-replay "${COV_DIR}/${UTIL}" "${f}" \
        >> "${OUT_DIR}/klee-replay-stdout.log" \
        2>> "${OUT_DIR}/klee-replay-stderr.log"
done

echo "Done"