"""Tests for git worktree parallel processing functionality."""
import os
import tempfile
import subprocess
import pytest
from pathlib import Path

from autoad.main import create_worktree, cleanup_worktree


@pytest.fixture
def git_repo():
    """Create a temporary git repository for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Initialize git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmpdir, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=tmpdir, check=True, capture_output=True
        )
        # Disable commit signing for tests
        subprocess.run(
            ["git", "config", "commit.gpgsign", "false"],
            cwd=tmpdir, check=True, capture_output=True
        )

        # Create initial commit
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("test content")
        subprocess.run(["git", "add", "."], cwd=tmpdir, check=True, capture_output=True)
        result = subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=tmpdir, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Git commit stderr: {result.stderr}")
            print(f"Git commit stdout: {result.stdout}")
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)

        # Change to repo directory for tests
        original_cwd = os.getcwd()
        os.chdir(tmpdir)

        try:
            yield tmpdir
        finally:
            os.chdir(original_cwd)


def test_create_worktree(git_repo):
    """Test creating a git worktree."""
    with tempfile.TemporaryDirectory() as worktree_base:
        worktree_path = create_worktree(worktree_base, worker_id=0)

        # Verify worktree was created
        assert os.path.exists(worktree_path)
        assert os.path.isdir(worktree_path)

        # Verify it's a valid git worktree
        result = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        assert worktree_path in result.stdout

        # Clean up
        cleanup_worktree(worktree_path)


def test_cleanup_worktree(git_repo):
    """Test cleaning up a git worktree."""
    with tempfile.TemporaryDirectory() as worktree_base:
        worktree_path = create_worktree(worktree_base, worker_id=0)

        # Verify worktree exists
        assert os.path.exists(worktree_path)

        # Clean up worktree
        cleanup_worktree(worktree_path)

        # Verify worktree was removed from git
        result = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        assert worktree_path not in result.stdout


def test_multiple_worktrees(git_repo):
    """Test creating and managing multiple worktrees."""
    with tempfile.TemporaryDirectory() as worktree_base:
        num_workers = 3
        worktrees = []

        # Create multiple worktrees
        for worker_id in range(num_workers):
            worktree_path = create_worktree(worktree_base, worker_id)
            worktrees.append(worktree_path)
            assert os.path.exists(worktree_path)

        # Verify all worktrees exist
        result = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        for worktree_path in worktrees:
            assert worktree_path in result.stdout

        # Clean up all worktrees
        for worktree_path in worktrees:
            cleanup_worktree(worktree_path)

        # Verify all worktrees were removed
        result = subprocess.run(
            ["git", "worktree", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        for worktree_path in worktrees:
            assert worktree_path not in result.stdout


def test_worktree_isolation(git_repo):
    """Test that worktrees are isolated from each other."""
    with tempfile.TemporaryDirectory() as worktree_base:
        worktree1 = create_worktree(worktree_base, worker_id=0)
        worktree2 = create_worktree(worktree_base, worker_id=1)

        # Create a file in worktree1
        test_file1 = Path(worktree1) / "worker1.txt"
        test_file1.write_text("worker 1 content")

        # Create a different file in worktree2
        test_file2 = Path(worktree2) / "worker2.txt"
        test_file2.write_text("worker 2 content")

        # Verify files are isolated
        assert test_file1.exists()
        assert test_file2.exists()
        assert not (Path(worktree1) / "worker2.txt").exists()
        assert not (Path(worktree2) / "worker1.txt").exists()

        # Clean up
        cleanup_worktree(worktree1)
        cleanup_worktree(worktree2)
