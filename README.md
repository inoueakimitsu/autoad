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

## Requirements

- Python 3.10+
- macOS, Linux or WSL
- Claude Code installed and configured. Due to intensive usage of the coding agent, we strongly recommend subscribing to the Claude MAX plan for optimal performance and to avoid rate limiting.
- Git repository (for tracking optimization history)
