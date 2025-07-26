# autoad

A simple automated algorithm design (AAD) tool.

## Overview

This tool optimizes code by iteratively maximizing multiple measurable objectives. The core concepts are:

- **Prompt-driven Optimization**: Accepts improvement instructions and evaluation criteria as prompts to guide the optimization process
- **Coding Agent Delegation**: Delegates code improvement tasks to a coding agent within the optimization loop
- **Git-based Progress Tracking**: Stores evaluation scores in Git tags to inform future optimization decisions
- **Evolutionary Approach**: Simulates genetic and evolutionary algorithms by growing, merging, and selecting branches based on their performance scores

The optimization process starts when you provide improvement goals and evaluation metrics. The system then creates new branches where a coding agent implements suggested improvements. Each variant is evaluated using your specified metrics, with scores stored in Git tags. Based on these scores, the system selects high-performing branches for further improvement or merging, continuously evolving your codebase towards better solutions.

## Usage

The tool requires:

- `--improvement-prompt`: Describes what you want to improve
- `--objective NAME "PROMPT"`: Defines evaluation criteria (can be used multiple times)

Optional parameters:

- `--optional-prompt`: Supplementary instructions for the optimization process
- `--sync-remote`: Automatically sync with remote repository (fetches at start, pushes at end)
- `--log-dir PATH`: Directory to save execution logs (default: ~/.autoad/logs)
- `--no-logging`: Disable logging to files
- `--iterations N`: Number of optimization iterations (default: 10)
- `--branch-prefix PREFIX`: Prefix for optimization branches (default: 'optimize')

```bash
uvx autoad \
  --improvement-prompt "Improve accuracy of milwrap/countbase.py by increasing the higher value of the two iter 9 MIL instance unit accuracy metrics obtained from running 'uv run pytest -s .'" \
  --objective accuracy-auto-init "Run 'uv run pytest -s .' and use the first iter 9 MIL instance unit accuracy value as the score" \
  --objective accuracy-external-init "Run 'uv run pytest -s .' and use the second iter 9 MIL instance unit accuracy value as the score" \
  --iterations 300 \
  --branch-prefix optim-mil \
  --optional-prompt "Please report progress in Japanese."
```

The tool follows these steps to evolve your codebase:

1. **User Actions**
   - Define optimization goals by providing:
     - Improvement prompt describing desired changes
     - Evaluation prompts specifying metrics

2. **System Actions - Code Generation**
   - Generates improved code versions by:
     - Creating new branches
     - Delegating improvements to coding agent
     - Implementing suggested changes

3. **System Actions - Evaluation**
   - Evaluates each variant by:
     - Running specified evaluation metrics
     - Calculating objective scores
     - Recording results in Git tags

4. **System Actions - Evolution**
   - Evolves solution space through:
     - Selecting high-performing branches
     - Merging promising variants
     - Continuing optimization process

### Example Application

As a practical example, this tool was applied to improve the algorithm performance in a multiple instance learning framework ([inoueakimitsu/milwrap](https://github.com/inoueakimitsu/milwrap)).

![Optimization Progress](demo.png)

The optimization process ran for 2 days, focusing on enhancing the algorithm's performance on test data. The accuracy improved from 0.914 to 0.956 (with a theoretical maximum of 0.970). The graph shows the evaluation results of various algorithm variants generated during the optimization process.

### Custom Iterations and Branch Prefix

You can specify the maximum number of iterations and customize the branch prefix using the following parameters:

- `--iterations N`: Set the maximum number of optimization iterations (default: 100)
- `--branch-prefix PREFIX`: Set custom prefix for optimization branches (default: "optim")

### Remote Synchronization

The `--sync-remote` option enables automatic synchronization with a remote Git repository:

- **Before optimization**: Fetches all branches and tags from the remote repository to ensure you're working with the latest state
- **After optimization**: Force pushes all branches and tags to the remote repository to share your optimization results

This is particularly useful for:
- **Distributed optimization**: Run optimization on multiple machines and combine results
- **Collaborative workflows**: Share optimization progress with team members
- **Backup and persistence**: Ensure optimization results are saved to remote repository

Example:
```bash
uvx autoad \
  --improvement-prompt "Optimize performance" \
  --objective speed "Measure execution time" \
  --sync-remote
```

**Note**: The `--force` flag is used when pushing, which will overwrite remote branches. Ensure you have appropriate permissions and understand the implications before using this option.

### Dry-Run Mode

The `--dry-run` option allows you to preview what commands would be executed without actually running them:

- **Command preview**: Displays the exact Claude CLI commands that would be executed
- **Interactive mode hints**: Shows how to run the same commands interactively (without `-p` option)
- **Safe validation**: Verify your prompts and tool permissions before actual execution
- **No side effects**: Skips all Git operations and Claude CLI execution
- **Automatic iteration limit**: Forces iterations to 1 (with warning if different value specified)

This is particularly useful for:
- **Prompt validation**: Check that your improvement and objective prompts are correctly formatted
- **Permission testing**: Verify Claude has necessary tool permissions before long-running optimization
- **Command debugging**: See exact commands that will be executed
- **Learning**: Understand how autoad constructs Claude CLI commands

Example:
```bash
uvx autoad \
  --improvement-prompt "Optimize algorithm performance" \
  --objective accuracy "Run tests and extract accuracy score" \
  --dry-run
```

### Logging and Output Management

Autoad automatically logs all execution output to help with debugging and analysis:

- **Default location**: `~/.autoad/logs/`
- **Directory structure**: `YYYY-MM-DD-HH-MM-SS-microseconds/` for each iteration (timestamp with microsecond precision)
- **Log files**: 
  - `stdout.log`: Standard output from the iteration
  - `stderr.log`: Error output from the iteration
  - `metadata.json`: Execution metadata (session_id, iteration_start_time, branch name, timestamps, etc.)

#### Logging Options

```bash
# Specify custom log directory
uvx autoad --log-dir /path/to/logs ...

# Set via environment variable
export AUTOAD_LOG_DIR=/path/to/logs
uvx autoad ...

# Disable logging entirely
uvx autoad --no-logging ...
```

#### Log Directory Structure Example

```
~/.autoad/logs/
├── 2025-07-21-13-45-00-123456/     # Iteration 1 (with microseconds)
│   ├── stdout.log
│   ├── stderr.log
│   └── metadata.json
├── 2025-07-21-13-45-01-789012/     # Iteration 2
│   ├── stdout.log
│   ├── stderr.log
│   └── metadata.json
└── 2025-07-21-13-45-02-345678/     # Iteration 3
    ├── stdout.log
    ├── stderr.log
    └── metadata.json
```

**Note**: Each iteration now creates its own directory based on the iteration start timestamp with microsecond precision. This ensures unique directories even when iterations run in parallel, eliminating the need for session IDs and iteration numbers in the directory names.

The logging system:
- Preserves real-time console output while saving to files
- Captures subprocess output (Git, Claude CLI, etc.)
- Prevents accidental commits of log files to Git
- Includes error handling with fallback directories
- Protects against path traversal attacks

## Requirements

- Python 3.10+
- macOS, Linux or WSL
- Claude Code installed and configured. Due to intensive usage of the coding agent, we strongly recommend subscribing to the Claude MAX plan for optimal performance and to avoid rate limiting.
- Git repository (for tracking optimization history)

## Running Development Version

To run a development version of autoad from a local repository without using `uvx`, you can clone the repository and use `uv run` with the `--project` option:

```bash
# Clone the autoad repository
git clone https://github.com/inoueakimitsu/autoad

# Run autoad from a different project directory
uv run --project ../autoad python -m autoad.main --help
```

In this example:
- `../autoad` is the path to your cloned autoad repository
- The command runs autoad using the development code from that repository

