import subprocess
import sys
import os


valid_utils = ["base64", "basename", "cat", "chcon", "chgrp", "chmod", "chown", "chroot", "cksum", "comm", "cp", "csplit", "cut", "date", "dd", "df", "dircolors", "dirname", "du", "echo", "env", "expand", "expr", "factor", "false", "fmt", "fold", "head", "hostid", "hostname", "id", "ginstall", "join", "kill", "link", "ln", "logname", "ls", "md5sum", "mkdir", "mkfifo", "mknod", "mktemp", "mv", "nice", "nl", "nohup", "od", "paste", "pathchk", "pinky", "pr", "printenv", "printf", "ptx", "pwd", "readlink", "rm", "rmdir", "runcon", "seq", "setuidgid", "shred", "shuf", "sleep", "sort", "split", "stat", "stty", "sum", "sync", "tac", "tail", "tee", "touch", "tr", "tsort", "tty", "uname", "unexpand", "uniq", "unlink", "uptime", "users", "wc", "whoami", "who", "yes"]

def get_sym_args(util):
    if util == "dd":
        return "--sym-args 0 3 10 --sym-files 1 8 --sym-stdin 8 --sym-stdout"
    elif util == "dircolors":
        return "--sym-args 0 3 10 --sym-files 2 12 --sym-stdin 12 --sym-stdout"
    elif util == "echo":
        return "--sym-args 0 4 300 --sym-files 2 30 --sym-stdin 30 --sym-stdout"
    elif util == "expr":
        return "--sym-args 0 1 10 --sym-args 0 3 2 --sym-stdout"
    elif util == "mknod":
        return "--sym-args 0 1 10 --sym-args 0 3 2 --sym-files 1 8 --sym-stdin 8 --sym-stdout"
    elif util == "od":
        return "--sym-args 0 3 10 --sym-files 2 12 --sym-stdin 12 --sym-stdout"
    elif util == "pathchk":
        return "--sym-args 0 1 2 --sym-args 0 1 300 --sym-files 1 8 --sym-stdin 8 --sym-stdout"
    elif util == "printf":
        return "--sym-args 0 3 10 --sym-files 2 12 --sym-stdin 12 --sym-stdout"
    else:
        return "--sym-args 0 1 10 --sym-args 0 2 2 --sym-files 1 8 --sym-stdin 8 --sym-stdout"

def get_util_CLAs(util):
    # if util == "sort":
    #     return "--parallel=1"
    # else:
        return ""
    
def construct_command(util, path_to_utils):
    cmd = f"klee --simplify-sym-indices --write-cvcs --write-cov --output-module \
            --max-memory=1000 --disable-inlining --optimize --use-forked-solver \
            --use-cex-cache --libc=uclibc --posix-runtime \
            --external-calls=all --only-output-states-covering-new \
            --env-file=test.env --run-in-dir=/tmp/sandbox \
            --max-sym-array-size=4096 --max-solver-time=30s --max-time=60min \
            --watchdog --max-memory-inhibit=false --max-static-fork-pct=1 \
            --max-static-solve-pct=1 --max-static-cpfork-pct=1 --switch-type=internal \
            --search=random-path --search=nurs:covnew \
            --use-batching-search --batch-instructions=10000 \
            {path_to_utils}{util}.bc {get_util_CLAs(util)} {get_sym_args(util)}"
    
    return [e for e in cmd.split(" ") if len(e) > 0]

if __name__ == "__main__":
    
    if len(sys.argv) < 2 or (len(sys.argv) == 2 and not "CORETUILS_BC_PATH" in os.environ):
        print(f"Usage: python3 {sys.argv[0]} <path_to_utils> <util>")
        print(f"Usage if env variable CORETUILS_BC_PATH is set: python3 {sys.argv[0]} <util>")
        exit(1)

    if len(sys.argv) >= 3:
        path_to_utils = sys.argv[1]
        util = sys.argv[2]
    else:
        path_to_utils = os.environ["CORETUILS_BC_PATH"]
        util = sys.argv[1]

    if util not in valid_utils:
        print(f"passed invalid util: {util}")
        exit(2)

    cmd = construct_command(util, path_to_utils)
    print(f"running klee with the following arguments:\n{cmd}")
    subprocess.run(cmd)