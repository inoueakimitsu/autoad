"""Integration tests for dry-run mode."""

import subprocess
import sys
import os
import pytest


@pytest.mark.integration
class TestDryRunIntegration:
    """Integration tests for dry-run mode end-to-end functionality."""
    
    def test_full_dry_run_execution(self, tmp_path, monkeypatch):
        """Test complete dry-run execution from CLI."""
        # Change to temporary directory
        monkeypatch.chdir(tmp_path)
        
        # Initialize git repo
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True)
        
        # Create a dummy file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello():\n    print('Hello')\n")
        subprocess.run(["git", "add", "test.py"], check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)
        
        # Run autoad in dry-run mode
        result = subprocess.run([
            sys.executable, "-m", "autoad.main",
            "--dry-run",
            "--improvement-prompt", "Improve the hello function",
            "--objective", "performance", "Make it run faster"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        
        # Check output contains expected messages
        output = result.stdout
        assert "=== ドライランモード ===" in output
        assert "実行予定のClaudeコマンド:" in output
        assert "claude --verbose" in output
        assert "--max-turns" in output
        assert "対話モードで実行する場合:" in output
        
        # Verify no actual changes were made
        status = subprocess.run(["git", "status", "--porcelain"], 
                                capture_output=True, text=True, check=True)
        assert status.stdout == ""  # No changes
        
        # Verify no tags were created
        tags = subprocess.run(["git", "tag"], 
                              capture_output=True, text=True, check=True)
        assert tags.stdout == ""  # No tags
    
    def test_dry_run_with_sync_remote(self, tmp_path, monkeypatch):
        """Test dry-run with sync-remote option."""
        monkeypatch.chdir(tmp_path)
        
        # Initialize git repo
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True)
        
        # Run with sync-remote
        result = subprocess.run([
            sys.executable, "-m", "autoad.main",
            "--dry-run",
            "--sync-remote",
            "--improvement-prompt", "Test",
            "--objective", "test", "Test objective"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        assert "ドライランモード：sync_remote（git fetch --all --tags）はスキップされました" in result.stdout
        assert "ドライランモード：sync_remote（git push --all --tags --force）はスキップされました" in result.stdout
    
    def test_dry_run_multiple_objectives(self, tmp_path, monkeypatch):
        """Test dry-run with multiple objectives."""
        monkeypatch.chdir(tmp_path)
        
        # Initialize git repo
        subprocess.run(["git", "init"], check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True)
        
        # Run with multiple objectives
        result = subprocess.run([
            sys.executable, "-m", "autoad.main",
            "--dry-run",
            "--improvement-prompt", "Optimize code",
            "--objective", "speed", "Make it faster",
            "--objective", "memory", "Reduce memory usage"
        ], capture_output=True, text=True)
        
        assert result.returncode == 0
        
        # Should see multiple Claude command displays
        command_count = result.stdout.count("実行予定のClaudeコマンド:")
        assert command_count >= 4  # Initial + commit + 2 objectives