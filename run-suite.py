import argparse
import os
from concurrent.futures import ThreadPoolExecutor
import threading
import subprocess
import sys
import datetime
from enum import Enum

RED = "\033[31m"  # Red text
GREEN = "\033[32m"  # Green text
YELLOW = "\033[33m"  # Yellow text
RESET = "\033[0m"  # Reset to default terminal color

# coreutils tested in the initial KLEE paper
all_coreutils = [
    "[",
    "base64",
    "basename",
    "cat",
    "chcon",
    "chgrp",
    "chmod",
    "chown",
    "chroot",
    "cksum",
    "comm",
    "cp",
    "csplit",
    "cut",
    "date",
    "dd",
    "df",
    "dircolors",
    "dirname",
    "du",
    "echo",
    "env",
    "expand",
    "expr",
    "factor",
    "false",
    "fmt",
    "fold",
    "head",
    "hostid",
    "hostname",
    "id",
    "ginstall",
    "join",
    "kill",
    "link",
    "ln",
    "logname",
    "ls",
    "md5sum",
    "mkdir",
    "mkfifo",
    "mknod",
    "mktemp",
    "mv",
    "nice",
    "nl",
    "nohup",
    "od",
    "paste",
    "pathchk",
    "pinky",
    "pr",
    "printenv",
    "printf",
    "ptx",
    "pwd",
    "readlink",
    "rm",
    "rmdir",
    "runcon",
    "seq",
    "setuidgid",
    "shred",
    "shuf",
    "sleep",
    "sort",
    "split",
    "stat",
    "stty",
    "sum",
    "sync",
    "tac",
    "tail",
    "tee",
    "touch",
    "tr",
    "tsort",
    "tty",
    "uname",
    "unexpand",
    "uniq",
    "unlink",
    "uptime",
    "users",
    "wc",
    "whoami",
    "who",
    "yes",
]


class State(Enum):
    WATING = 0
    STARTED = 1
    FINISHED_ANALYSIS = 2
    FINISHED_COVERAGE = 3
    ERROR = 4


print_lock = threading.Lock()
counter_lock = threading.Lock()

states: dict[str, State] = {e: State.WATING for e in all_coreutils}


def update_counter(util: str, state: State) -> str:
    with counter_lock:
        global states
        global all_coreutils
        states[util] = state
        state_counts = [
            list(states.values()).count(e) for e in State._member_map_.values()
        ]
        state_counts = [f"{e:>{len(str(len(all_coreutils)))}}" for e in state_counts]
        state_counts[-1] = f"{RED}{state_counts[-1]}{RESET}"
        state_counts = ", ".join(state_counts)
        state_counts = f"({state_counts})"
        return state_counts


def thread_safe_print(*args, **kwargs):
    with print_lock:
        print(datetime.datetime.now().isoformat(), *args, **kwargs)


def print_with_counter(util: str, newState: State, message: str):
    if newState == State.ERROR:
        thread_safe_print(
            f"{update_counter(util, newState)} — {RED}{message}{RESET}",
            file=sys.stderr,
        )
    else:
        thread_safe_print(f"{update_counter(util, newState)} — {message}")


def init_parser():
    parser = argparse.ArgumentParser(description="Run KLEE on coreutils.")
    parser.add_argument(
        "output_dir",
        help="Output directory",
    )
    parser.add_argument(
        "--max-threads",
        type=int,
        help="Maximum number of threads",
        default=1,
    )
    parser.add_argument(
        "--image-name",
        help='Name of the image built, defaults to "klee-coreutils(-[name of the passed dockerfile])',
    )
    parser.add_argument(
        "--dockerfile",
        help="Path of the dockerfile to use",
        default="Dockerfile",
    )
    parser.add_argument(
        "--util",
        action="append",
        help="Utils to test",
    )
    parser.add_argument(
        "--env",
        "-e",
        action="append",
        nargs=2,
        metavar=("key", "value"),
        help="Environment variables",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force execution, even if target directory already exists",
    )
    return parser


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
    cov_command = [
        "docker",
        "run",
        "--rm",
        "-it",
        "-e",
        f"UTIL={util}",
        "-v",
        f"{abs_util_output_dir}:/out",
        f"{image_name}-cov",
    ]

    # Execute the command using subprocess.run
    with open(stdout_file, "w") as stdout_f, open(stderr_file, "w") as stderr_f:
        print_with_counter(util, f'Starting run for util "{util}".')
        process = subprocess.run(
            exec_command, stdout=stdout_f, stderr=stderr_f, text=True
        )
        if process.returncode != 0:
            print_with_counter(
                util,
                State.ERROR,
                f"=== ERROR: Failed to execute {util} with exit code {process.returncode}",
            )
            return

        print_with_counter(
            util, State.FINISHED_ANALYSIS, f'Starting coverage gathering for "{util}".'
        )

        process = subprocess.run(
            cov_command, stdout=stdout_f, stderr=stderr_f, text=True
        )
        if process.returncode != 0:
            print_with_counter(
                util,
                State.ERROR,
                f"=== ERROR: Failed to gather coverage for {util} with exit code {process.returncode}",
            )
            return

        print_with_counter(util, State.FINISHED_COVERAGE, f'Done with "{util}".')


if __name__ == "__main__":
    # Parse command-line arguments
    args = init_parser().parse_args()
    thread_safe_print(f"Analyzing with the following args: {args}")

    output_dir = args.output_dir
    image_name = args.image_name
    dockerfile: str = args.dockerfile
    if image_name is None:
        image_name = "klee-coreutils"
        if len(dockerfile) > len("Dockerfile"):
            image_name = f"{image_name}-{dockerfile.replace('.Dockerfile', '')}"

    # Check if the output directory exists and is empty
    if (not args.force) and (
        os.path.exists(output_dir)
        and os.path.isdir(output_dir)
        and os.listdir(output_dir)
    ):
        response = (
            input(
                f"{YELLOW}Output directory is not empty, this might not work. Continue anyway? (y/n){RESET} "
            )
            .lower()
            .strip()
        )
        if response not in ["y", "yes"]:
            thread_safe_print("Exiting")
            exit(1)

    # Make sure the docker image is up to date
    thread_safe_print(
        f"Building docker image from dockerfile {dockerfile} to image {image_name}[-cov]"
    )
    process = subprocess.run(
        [
            "docker",
            "build",
            "--progress=plain",
            "--target",
            "klee-coreutils-exec",
            "-t",
            f"{image_name}",
            "-f",
            dockerfile,
            ".",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if process.returncode != 0:
        thread_safe_print(
            f"{RED}=== ERROR: Failed to build docker image exec with exit code {process.returncode}{RESET}",
            file=sys.stderr,
        )
        exit(1)
    process = subprocess.run(
        [
            "docker",
            "build",
            "--progress=plain",
            "--target",
            "klee-coreutils-gcov",
            "-t",
            f"{image_name}-cov",
            "-f",
            dockerfile,
            ".",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if process.returncode != 0:
        thread_safe_print(
            f"=== ERROR: Failed to build docker image cov with exit code {process.returncode}",
            file=sys.stderr,
        )
        exit(1)

    coreutils = all_coreutils
    if args.util is not None:
        coreutils = [e for e in args.util if e in all_coreutils]
        states = {e: State.WATING for e in coreutils}
        thread_safe_print(
            f"{YELLOW}Only running the following coreutils: {coreutils}{RESET}"
        )

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
            futures.append(
                executor.submit(run_klee_coreutils, image_name, util, env_vars)
            )

    for future in futures:
        future.result()  # Wait for each task to complete

    num_succ = list(states.values()).count(State.FINISHED_COVERAGE)
    num_error = list(states.values()).count(State.ERROR)
    thread_safe_print(f"All tasks completed. Successes/Errors: {num_succ}/{num_error}.")
