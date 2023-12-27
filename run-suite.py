import argparse
import os
from concurrent.futures import ThreadPoolExecutor
import threading
import subprocess
import sys

print_lock = threading.Lock()

def thread_safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)

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
    command = ["docker", "run", "--rm", "-it"]
    
    # Append environment variables to the command
    for key, value in env.items():
        command += ["-e", f"{key}={value}"]
    
    # Append image name and output directory volume mapping to the command
    command += ["-v", f"{abs_util_output_dir}:/home/klee/out", image_name]
    
    # Execute the command using subprocess.run
    thread_safe_print(f"--- running command: {' '.join(command)}")
    with open(stdout_file, "w") as stdout_f, open(stderr_file, "w") as stderr_f:
        process = subprocess.run(command, stdout=stdout_f, stderr=stderr_f, text=True)
    
    # Check return code
    if process.returncode != 0:
        thread_safe_print(f"Failed to execute {util} with exit code {process.returncode}", file=sys.stderr)

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run klee-coreutils for each coreutil from the original KLEE paper.')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('--max-threads', type=int, help='Maximum number of threads', default=1)
    parser.add_argument('--image-name', help='Name of the image built', default="klee-coreutils")
    parser.add_argument('--env', '-e', action='append', nargs=2, metavar=('key', 'value'), help='Environment variables')

    args = parser.parse_args()
    output_dir = args.output_dir
    image_name = args.image_name

    # Check if the output directory exists and is empty
    if os.path.exists(output_dir) and os.path.isdir(output_dir) and os.listdir(output_dir):
        thread_safe_print("Output directory is not empty, this will not work", file=sys.stderr)
        exit(1)

    # Make sure the docker image is up to date
    subprocess.run(["docker", "build", "-t", image_name, "--target", "exec", "--progress=plain", "."])

    # Complete list of coreutils from the KLEE paper
    coreutils = ["base64", "basename", "cat", "chcon", "chgrp", "chmod", "chown", "chroot", "cksum", "comm", "cp", "csplit", "cut", "date", "dd", "df", "dircolors", "dirname", "du", "echo", "env", "expand", "expr", "factor", "false", "fmt", "fold", "head", "hostid", "hostname", "id", "ginstall", "join", "kill", "link", "ln", "logname", "ls", "md5sum", "mkdir", "mkfifo", "mknod", "mktemp", "mv", "nice", "nl", "nohup", "od", "paste", "pathchk", "pinky", "pr", "printenv", "printf", "ptx", "pwd", "readlink", "rm", "rmdir", "runcon", "seq", "setuidgid", "shred", "shuf", "sleep", "sort", "split", "stat", "stty", "sum", "sync", "tac", "tail", "tee", "touch", "tr", "tsort", "tty", "uname", "unexpand", "uniq", "unlink", "uptime", "users", "wc", "whoami", "who", "yes"]

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
