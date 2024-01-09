import argparse
import os
from concurrent.futures import ThreadPoolExecutor
import threading
import subprocess
import sys
import datetime
from enum import Enum


all_coreutils = ["base64", "basename", "cat", "chcon", "chgrp", "chmod", "chown", "chroot", "cksum", "comm", "cp", "csplit", "cut", "date", "dd", "df", "dircolors", "dirname", "du", "echo", "env", "expand", "expr", "factor", "false", "fmt", "fold", "head", "hostid", "hostname", "id", "ginstall", "join", "kill", "link", "ln", "logname", "ls", "md5sum", "mkdir", "mkfifo", "mknod", "mktemp", "mv", "nice", "nl", "nohup", "od", "paste", "pathchk", "pinky", "pr", "printenv", "printf", "ptx", "pwd", "readlink", "rm", "rmdir", "runcon", "seq", "setuidgid", "shred", "shuf", "sleep", "sort", "split", "stat", "stty", "sum", "sync", "tac", "tail", "tee", "touch", "tr", "tsort", "tty", "uname", "unexpand", "uniq", "unlink", "uptime", "users", "wc", "whoami", "who", "yes"]
class State(Enum):
    STARTED = 1
    FINISHED_ANALYSIS = 2
    FINISHED_COVERAGE = 3

print_lock = threading.Lock()
counter_lock = threading.Lock()

states: dict[str, State] = {e: State.STARTED for e in all_coreutils}

def update_counter(util: str, state: State) -> str:
    with counter_lock:
        global states
        states[util] = state
        return f"({list(states.values()).count(State.STARTED)}, {list(states.values()).count(State.FINISHED_ANALYSIS)}, {list(states.values()).count(State.FINISHED_COVERAGE)})"

def thread_safe_print(*args, **kwargs):
    with print_lock:
        print(datetime.datetime.now().isoformat(), *args, **kwargs)

# Function to run klee-coreutils for a given util
def run_klee_coreutils(image_name, util, env_vars):
    # Create a specific environment for the current util
    env = {"UTIL": util}
    env.update(env_vars)
    
    # Create a subfolder for the current util within the output directory
    util_output_dir = os.path.join(output_dir, util)
    os.makedirs(util_output_dir, exist_ok=True)

    # Obtain the absolute path for the output directory
    abs_util_output_dir = os.path.abspath(util_output_dir)

    # Define output filenames for stdout and stderr
    stdout_file = os.path.join(util_output_dir, "orchestration-stdout.txt")
    stderr_file = os.path.join(util_output_dir, "orchestration-stderr.txt")
    
    # Command to run klee-coreutils docker image and direct output to the util-specific folder
    exec_command = ["docker", "run", "--rm", "-it"]
    
    # Append environment variables to the command
    for key, value in env.items():
        exec_command += ["-e", f"{key}={value}"]
    
    # Append image name and output directory volume mapping to the command
    exec_command += ["-v", f"{abs_util_output_dir}:/home/klee/out", image_name]
    
    # Command to gather coverage information
    cov_command = ["docker", "run", "--rm", "-it", "-e", f"UTIL={util}", "-v", f"{abs_util_output_dir}:/out", f"{image_name}-cov"]

    # Execute the command using subprocess.run
    with open(stdout_file, "w") as stdout_f, open(stderr_file, "w") as stderr_f:
        thread_safe_print(f"starting run for util \"{util}\". State: {update_counter(util, State.STARTED)}")
        process = subprocess.run(exec_command, stdout=stdout_f, stderr=stderr_f, text=True)
        if process.returncode != 0:
            thread_safe_print(f"=== ERROR: Failed to execute {util} with exit code {process.returncode}", file=sys.stderr)
    
        thread_safe_print(f"starting coverage gathering for util \"{util}\". State: {update_counter(util, State.FINISHED_ANALYSIS)}")
        process = subprocess.run(cov_command, stdout=stdout_f, stderr=stderr_f, text=True)
        if process.returncode != 0:
            thread_safe_print(f"=== ERROR: Failed to gather coverage for {util} with exit code {process.returncode}", file=sys.stderr)
        thread_safe_print(f"done with util \"{util}\". State: {update_counter(util, State.FINISHED_COVERAGE)}")
    

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run klee-coreutils for each coreutil from the original KLEE paper.')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('--max-threads', type=int, help='Maximum number of threads', default=1)
    parser.add_argument('--image-name', help='Name of the image built', default="klee-coreutils")
    parser.add_argument('--util', action='append', help='Utils to test')
    parser.add_argument('--env', '-e', action='append', nargs=2, metavar=('key', 'value'), help='Environment variables')
    parser.add_argument('--force', '-f', action='store_true', help='Force execution, even if target directory already exists')

    args = parser.parse_args()
    thread_safe_print(f"Analyzing with the following args: {args}")

    output_dir = args.output_dir
    image_name = args.image_name

    # Check if the output directory exists and is empty
    if (not args.force) and (os.path.exists(output_dir) and os.path.isdir(output_dir) and os.listdir(output_dir)):
        response = input("Output directory is not empty, this might not work. Continue anyway? (y/n) ").lower().strip()
        if response not in ['y', 'yes']:
            thread_safe_print("Exiting")
            exit(1)

    # Make sure the docker image is up to date
    thread_safe_print("Building docker image")
    process = subprocess.run(["docker", "build", "--progress=plain", "--target", "klee-coreutils-exec", "-t", f"{image_name}", "."], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if process.returncode != 0:
        thread_safe_print(f"=== ERROR: Failed to build docker image exec with exit code {process.returncode}", file=sys.stderr)
    process = subprocess.run(["docker", "build", "--progress=plain", "--target", "klee-coreutils-gcov", "-t", f"{image_name}-cov", "."], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if process.returncode != 0:
        thread_safe_print(f"=== ERROR: Failed to build docker image cov with exit code {process.returncode}", file=sys.stderr)

    # Complete list of coreutils from the KLEE paper
    
    coreutils = all_coreutils
    if args.util is not None:
        coreutils = [e for e in args.util if e in all_coreutils]
        thread_safe_print(f"Only running the following coreutils: {coreutils}")

    # Prepare environment variables
    env_vars = {}
    if args.env:
        for key, value in args.env:
            env_vars[key] = value

    futures = []
    # Run klee-coreutils for each coreutil with specific environment variables using ThreadPoolExecutor
    max_threads = args.max_threads
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        for util in coreutils:
            futures.append(executor.submit(run_klee_coreutils, image_name, util, env_vars))
    
    for future in futures:
        future.result()  # Wait for each task to complete

    thread_safe_print("All tasks completed.")
