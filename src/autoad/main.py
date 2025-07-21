"""Automated algorithm design tool using AI-assisted code optimization.

This module implements an evolutionary algorithm approach to code optimization,
using Git branches to explore different optimization strategies and Claude CLI
for code improvements. It supports multi-objective optimization with automated
evaluation and branch selection based on genetic algorithm principles.
"""
import argparse
import os
import subprocess
import shlex
import sys
from typing import List, Tuple, Optional

# Sets the maximum number of turns for each Claude CLI iteration.
# One turn represents one response from Claude.
# Claude automatically ends the conversation after 1000 turns.
MAX_TURNS_IN_EACH_ITERATION = 1000

# Sets the timeout for subprocess execution in seconds
SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
SUBPROCESS_TIMEOUT_HOURS = 2
SUBPROCESS_TIMEOUT = SECONDS_PER_MINUTE * MINUTES_PER_HOUR * SUBPROCESS_TIMEOUT_HOURS

# Sets the number of significant digits for the evaluation metric values.
# The evaluation metric values are rounded to this number of significant digits.
# The evaluation metric values are displayed in the tag name.
NUMBER_OF_SIGNIFICANT_DIGITS_FOR_EVALUATION_METRIC_VALUES = 3

BASE_ALLOWED_TOOLS = [
    # File operations
    "Read",
    "Edit",
    # File system operations
    "Bash(ls:*)",
    "Bash(cat:*)", 
    "Bash(tail:*)",
    "Bash(head:*)",
    "Bash(mv:*)",
    "Bash(cp:*)",
    "Bash(rm:*)",
    "Bash(mkdir:*)",
    "Bash(rmdir:*)",
    "Bash(touch:*)",
    "Bash(find:*)",
    "Bash(grep:*)",
    "Bash(rg:*)",
    # Git operations
    "Bash(git status:*)",
    "Bash(git diff:*)",
    "Bash(git log:*)",
    "Bash(git commit:*)",
    "Bash(git --no-pager commit:*)",
    "Bash(git tag:*)",
    "Bash(git --no-pager tag:*)",
    "Bash(git add:*)",
    "Bash(git pull:*)",
    "Bash(git checkout:*)",
    "Bash(git branch:*)",
    "Bash(git rev-parse:*)",
    "Bash(git rev-list:*)",
    "Bash(git branch -m:*)",
    # Package management
    "Bash(pip install:*)",
    "Bash(pip uninstall:*)",
    "Bash(pip freeze:*)",
    "Bash(pip show:*)",
    "Bash(pip search:*)",
    "Bash(pip download:*)",
    "Bash(pip wheel:*)",
    "Bash(pip check:*)",
    "Bash(npm run test:*)",
    "Bash(npm run lint:*)",
    "Bash(npm run build:*)",
    "Bash(npm install:*)",
    "Bash(npm uninstall:*)",
    "Bash(npm shrinkwrap:*)",
    "Bash(npm show:*)",
    "Bash(npm list:*)",
    "Bash(npm search:*)",
    "Bash(uv sync:*)",
    "Bash(uv run:*)",
    "Bash(uv pip:*)",
    "Bash(uv add:*)",
    "Bash(uv remove:*)",
    # Code quality tools
    "Bash(ruff:*)",
    # Code execution and testing
    "Bash(python:*)",
    "Bash(python3:*)",
    "Bash(uvx:*)",
    "Bash(bash:*)",
    "Bash(node:*)",
    "Bash(npx:*)",
    "Bash(npm:*)",
    # Long-running processes
    "Bash(nohup:*)",
    # Special tools (called directly)
    "mcp__o3",
]

def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(
        description="autoad",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Multi-objective optimization
  python main.py \\
    --improvement-prompt "Optimize the code for better performance" \\
    --objective precision "Calculate test precision percentage" \\
    --objective cost "Calculate execution cost in dollars" \\
    --objective memory "Measure memory usage in MB"
        """,
    )

    parser.add_argument(
        "--improvement-prompt",
        required=True,
        help="Prompt for requesting code improvements",
    )

    parser.add_argument(
        "--objective",
        nargs=2,
        metavar=("NAME", "PROMPT"),
        action="append",
        required=True,
        help="Define optimization objective: NAME 'evaluation prompt' (can be used multiple times)",
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Maximum number of improvement iterations (default: 10)",
    )

    parser.add_argument(
        "--branch-prefix",
        default=os.environ.get("autoad_BRANCH_PREFIX", "optimize"),
        help="Prefix for optimization branches (default: 'optimize', "
        "can be set via autoad_BRANCH_PREFIX env var)",
    )

    parser.add_argument(
        "--optional-prompt",
        help="Optional supplementary prompt to incorporate into the optimization process",
    )

    parser.add_argument(
        "--sync-remote",
        action="store_true",
        help="Sync remote branches with local branches",
    )

    return parser.parse_args()

def run_claude_with_prompt(
    prompt: str,
    max_turns: int,
    allowed_tools: List[str],
    continue_conversation: bool = False,
) -> List[str]:
    """Run a conversation with Claude.

    Args:
        prompt: The prompt to send to Claude.
        max_turns: Maximum number of response turns from Claude.
        allowed_tools: List of tools Claude is allowed to use.
        continue_conversation: If True, adds the --continue option.

    Returns:
        List of response lines from Claude.

    Raises:
        subprocess.CalledProcessError: When command exits with non-zero code.
        subprocess.TimeoutExpired: When command times out.
        RuntimeError: When process stdin/stdout streams are None.
    """
    command_options = [
        "claude",
        "--verbose",
    ]

    if continue_conversation:
        command_options.append("--continue")

    command_options.extend([
        f"--max-turns {max_turns}",
        "--output-format stream-json",
        f"--allowedTools '{','.join(allowed_tools)}'",
        "-p"
    ])

    command = [
        "bash",
        "-l",
        "-c",
        " ".join(command_options)
    ]
    collected_output = []
    with subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True,
        shell=False,
    ) as process:
        # Verify process streams are not None
        if process.stdin is None:
            raise RuntimeError("Process stdin stream is None")
        if process.stdout is None:
            raise RuntimeError("Process stdout stream is None")
        if process.stderr is None:
            raise RuntimeError("Process stderr stream is None")

        # Write prompt to stdin
        process.stdin.write(shlex.quote(prompt))
        process.stdin.close()  # Complete input

        try:
            # Stream stdout
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                print(line, end="", flush=True)
                collected_output.append(line)

            # Stream stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                print(stderr_output, file=sys.stderr, flush=True)

            # Wait for process to complete
            return_code = process.wait()
            if return_code != 0:
                raise subprocess.CalledProcessError(
                    return_code,
                    command,
                    stderr=stderr_output
                )

            return collected_output

        except subprocess.TimeoutExpired as e:
            process.kill()
            raise subprocess.TimeoutExpired(
                command,
                SUBPROCESS_TIMEOUT,
            ) from e

def main() -> None:
    """Entry point for the autoad optimization tool.
    
    Orchestrates the multi-objective optimization process using evolutionary
    algorithms and Claude CLI for code improvements.
    """
    args = parse_args()
    improvement_prompt: str = args.improvement_prompt
    objectives: List[Tuple[str, str]] = list(args.objective)
    branch_prefix: str = args.branch_prefix
    optional_prompt: Optional[str] = args.optional_prompt
    iterations: int = args.iterations or 10
    sync_remote: bool = args.sync_remote

    for _ in range(1, iterations + 1):
        if sync_remote:
            subprocess.run(["git", "fetch", "--all", "--tags"], check=True)

        prompt = (
            "# Overview of the Optimization Activity\n"
            "Background: we are carrying out an optimization initiative and "
            "are testing multiple approaches in parallel.\n"
            "Each approach is managed as a Git branch under the following rules:\n"
            "- One branch corresponds to one optimization approach.\n"
            "- Improvements are performed by creating a new branch based on an existing branch.\n"
            "  (Ordinarily, branch proliferation would be discouraged, but for this "
            "initiative we deliberately permit it, as Git branches serve as the data "
            "structure for exploring alternative approaches.)\n"
            "\n"
            "# Instructions\n"
            "Proceed through the following tasks in order:\n"
            "1. Decide which branch will serve as the starting point for the next improvement.\n"
            "2. Decide the overall approach you will take for that improvement.\n"
            "3. Carry out the improvement activity in accordance with that approach.\n"
            "\n"
            "# Optimization Objective\n"
            f"{improvement_prompt}\n"
            "\n"
            "# Evaluation Procedure\n"
        )

        for objective_name, objective_prompt in objectives:
            prompt += f"- {objective_name}: {objective_prompt}\n"

        prompt += (
            "\n"
            "# Branch-Selection Policy\n"
            "By emulating evolutionary and genetic algorithms, choose the optimal "
            "branch to use as the basis for improvements from the following four "
            "perspectives:\n"
            "1. Deepening Improvements (exploitation)\n"
            "   - Further improve a branch whose evaluation score is already relatively "
            "high, or a branch whose score is low but shows growth potential.\n"
            "\n"
            "2. Exploration (exploration)\n"
            "   - Search for better solutions by trying out new ideas.\n"
            "\n"
            "3. Combining Ideas (crossover)\n"
            "   - Combine the best features of different branches.\n"
            "   - Produce new improvement methods by combining existing techniques.\n"
            "\n"
            "4. Ablation (ablation)\n"
            "   - Roll back some of the changes added in existing branches, observe "
            "their impact, and use that knowledge to devise solutions.\n"
            "   - Accumulate knowledge that identifies the causes of improvements or regressions.\n"
            "\n"
            "# How to Use Evaluation Information\n"
            "Refer to the following information when evaluating each branch:\n"
            f"- Evaluation metrics recorded in Git tags "
            f"(see them with `git tag -l '{branch_prefix}-eval-*' --sort=-version:refname`)\n"
            "- Tags associated with each commit (`git tag --contains <commit-hash>`)\n"
            "- Change descriptions in commit messages\n"
            "\n"
            "# Detailed Work Procedure\n"
            "1. Check out the optimal branch selected by the policy above.\n"
            f"   Only branches whose names start with the prefix "
            f"`{branch_prefix}/` may be checked out.\n"
            f"   If no branch with the `{branch_prefix}/` prefix exists, "
            f"use the current branch as the starting point.\n"
            "2. Create a new derivative branch based on that branch.\n"
            "3. If necessary, incorporate ideas from other branches using the commands below:\n"
            "   - `git merge` or `git cherry-pick` when you actually want to pull in code\n"
            "   - `git merge --no-ff -s ours <branch-to-merge>` when you only adopt the idea\n"
            "4. After planning, start the improvement work:\n"
            "   - Consider conducting a literature survey.\n"
            "   - Most importantly, run experiments such as debugging and analyzing "
            "intermediate results, observe the outcomes, and devise your solution accordingly.\n"
            "   - Do not commit yet; I will tell you when to commit.\n"
            "\n"
            "# Naming Convention for the New Branch\n"
            f"- Prefix  : Must start with `{branch_prefix}/`.\n"
            "- Name   : Concatenate 2–4 English words that describe the improvement, "
            "separated by hyphens (-).\n"
            f"- Examples : `{branch_prefix}/remove-temporal-reward`, "
            f"`{branch_prefix}/prefetch-fisher-info-matrix`\n"
            "- Note   : Do not include meta-information such as dates, scores, or assignee names.\n"
            "\n"
            "# Notes\n"
            "- Proceed with an *ultrathink* mindset.\n"
        )

        if optional_prompt:
            prompt += (
                "\n"
                "# Additional Instructions\n"
                f"{optional_prompt}\n"
            )

        run_claude_with_prompt(
            prompt=prompt,
            max_turns=MAX_TURNS_IN_EACH_ITERATION,
            allowed_tools=BASE_ALLOWED_TOOLS,
            continue_conversation=False,  # False only for first iteration
        )

        commit_prompt = (
            "# Creating the Commit Message\n"
            "Review the output of `git diff` and summarize the changes in the commit message.\n"
            "\n"
            "When writing the commit message, observe the following rules:\n"
            "- Uninformative expressions such as \"Fix bug\" or \"Update code\" are prohibited.\n"
            "- Do not include unnecessary long logs or stack traces.\n"
            "- Because it is not yet known whether this commit leads to an improvement, "
            "avoid value-laden wording.\n"
            "\n"
            "After adding the necessary files, run\n"
            '`git commit -m "$FULL_MESSAGE"`\n'
            "to create the commit once the message is ready.\n"
            "If you referred to or copied information from another branch, "
            "include at least the fact that it was merged in the commit message.\n"
            "If you adopted only the idea and discarded the code itself, you may also use\n"
            "`git merge --no-ff -s ours <branch-to-merge>` to record that.\n"
            "Note: The timing for adding Git tags will be given later, so do not tag yet.\n"
            "Continue until the commit is complete.\n"
        )

        if optional_prompt:
            prompt += (
                "\n"
                "# Additional Instructions\n"
                f"{optional_prompt}\n"
            )

        run_claude_with_prompt(
            prompt=commit_prompt,
            max_turns=MAX_TURNS_IN_EACH_ITERATION,
            allowed_tools=BASE_ALLOWED_TOOLS,
            continue_conversation=True,
        )

        for objective_index, (objective_name, objective_prompt) in enumerate(objectives):
            objective_prompt = (
                f"# Evaluation Task {objective_index + 1}\n"
                "Carry out the evaluation task as instructed below.\n"
                f"{objective_prompt}\n"
                f"The value obtained will be the evaluation metric for \"{objective_name}\".\n"
                "Note: The timing for adding Git tags will be given later, so do not tag yet.\n"
            )

            objective_prompt += (
                "If processing takes time, execute it in the background using `nohup`.\n"
                " After execution, obtain the process ID and periodically run the `ps` command.\n"
                " Each time, if the command is still running, execute the `sleep 60` command to wait for 1 minute.\n"
                " Repeat this wait up to a maximum of 120 times. \n"            
                "For example, refer to the following code when executing.: \n"
"""
    #!/bin/bash
    nohup your_command_here > process_output.log 2>&1 &
    pid=$!
    echo "Process started with PID: $pid"
    tail -f process_output.log &
    tail_pid=$!
    for i in {1..120}; do
        if ps -p "$pid" > /dev/null 2>&1; then
            echo "Attempt $i: Process still running"
            sleep 60
        else
            echo "Process completed after $i attempts"
            break
        fi
    done
    kill "$tail_pid"
    echo "Monitoring finished. Output log: process_output.log"
"""
            )

            run_claude_with_prompt(
                prompt=objective_prompt,
                max_turns=MAX_TURNS_IN_EACH_ITERATION,
                allowed_tools=BASE_ALLOWED_TOOLS,
                continue_conversation=True,
            )

        tag_prompt = (
            "# Creating the Git Tag\n"
            "Create a Git tag in accordance with the following instructions.\n"
            "The tag name must follow this format:\n"
            f"{branch_prefix}-eval-YYYYMMDD-HHMMSS-"
            "metricName1_metricValue1-metricName2_metricValue2-...\n"
            "After deciding on the tag name, run\n"
            "`git --no-pager tag -a <tag-name>`\n"
            "to create the tag. Create it for the current HEAD commit.\n"
            f"The number of significant digits for metric values is "
            f"{NUMBER_OF_SIGNIFICANT_DIGITS_FOR_EVALUATION_METRIC_VALUES}. "
            f"Scientific notation is acceptable.\n"
        )

        run_claude_with_prompt(
            prompt=tag_prompt,
            max_turns=MAX_TURNS_IN_EACH_ITERATION,
            allowed_tools=BASE_ALLOWED_TOOLS,
            continue_conversation=True,
        )

        if sync_remote:
            subprocess.run(["git", "push", "--all", "--tags", "--force"], check=True)

if __name__ == "__main__":
    main()
