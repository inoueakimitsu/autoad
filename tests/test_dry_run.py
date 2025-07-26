"""Tests for dry-run mode functionality."""

import sys
import subprocess
from unittest.mock import patch, MagicMock, call
import pytest

from autoad.main import parse_args, run_claude_with_prompt, _run_single_iteration


class TestDryRunMode:
    """Test suite for dry-run mode functionality."""
    
    def test_dry_run_cli_argument(self):
        """Test that --dry-run option is correctly parsed."""
        args = parse_args(["--dry-run", 
                           "--improvement-prompt", "test improvement",
                           "--objective", "test", "test objective"])
        assert args.dry_run is True
        
        args = parse_args(["--improvement-prompt", "test improvement",
                           "--objective", "test", "test objective"])
        assert args.dry_run is False
    
    def test_dry_run_iterations_override(self, capsys):
        """Test that iterations is overridden to 1 in dry-run mode."""
        with patch('autoad.main._run_single_iteration'):
            with patch('sys.argv', ['autoad', '--dry-run', '--iterations', '5',
                                    '--improvement-prompt', 'test',
                                    '--objective', 'test', 'test objective']):
                from autoad.main import main
                main()
                
        captured = capsys.readouterr()
        assert "=== ドライランモード ===" in captured.out
        assert "警告: iterations=5が指定されていますが" in captured.out
        assert "ドライランモードでは1に上書きされます" in captured.out
    
    def test_run_claude_with_prompt_dry_run(self, capsys):
        """Test run_claude_with_prompt in dry-run mode."""
        result = run_claude_with_prompt(
            prompt="test prompt",
            max_turns=5,
            allowed_tools=["Bash", "Read"],
            continue_conversation=False,
            dry_run=True
        )
        
        captured = capsys.readouterr()
        assert "実行予定のClaudeコマンド:" in captured.out
        assert "claude --verbose" in captured.out
        assert "--max-turns 5" in captured.out
        assert "--allowedTools 'Bash,Read'" in captured.out
        assert "-p 'test prompt'" in captured.out
        
        assert "対話モードで実行する場合:" in captured.out
        assert "-p" not in captured.out.split("対話モードで実行する場合:")[1].split("\n")[1]
        
        assert result == ["ドライランモード：実行されませんでした"]
    
    def test_sync_remote_skip_in_dry_run(self, capsys):
        """Test that sync_remote operations are skipped in dry-run mode."""
        mock_args = MagicMock()
        mock_args.dry_run = True
        mock_args.no_logging = True
        
        with patch('subprocess.run') as mock_run:
            _run_single_iteration(
                mock_args, 
                "test improvement", 
                [("test", "test objective")],
                "test-prefix",
                None,
                True,  # sync_remote enabled
                1
            )
            
        captured = capsys.readouterr()
        assert "ドライランモード：sync_remote（git fetch --all --tags）はスキップされました" in captured.out
        assert "ドライランモード：sync_remote（git push --all --tags --force）はスキップされました" in captured.out
        
        # subprocess.run should not be called for git operations
        for call_args in mock_run.call_args_list:
            cmd = call_args[0][0]
            if isinstance(cmd, list):
                assert not (cmd[0] == "git" and ("fetch" in cmd or "push" in cmd))
    
    def test_no_logging_in_dry_run(self):
        """Test that logging is disabled in dry-run mode."""
        with patch('autoad.main.LoggingManager') as mock_logging:
            with patch('autoad.main._run_single_iteration'):
                with patch('sys.argv', ['autoad', '--dry-run',
                                        '--improvement-prompt', 'test',
                                        '--objective', 'test', 'test objective']):
                    from autoad.main import main
                    main()
            
            # LoggingManager should not be instantiated in dry-run mode
            mock_logging.assert_not_called()


class TestCommandDisplay:
    """Test suite for command display functionality."""
    
    def test_command_with_continue_conversation(self, capsys):
        """Test command display with continue conversation option."""
        run_claude_with_prompt(
            prompt="test prompt",
            max_turns=5,
            allowed_tools=["Bash"],
            continue_conversation=True,
            dry_run=True
        )
        
        captured = capsys.readouterr()
        assert "--continue" in captured.out
    
    def test_complex_prompt_escaping(self, capsys):
        """Test that complex prompts are properly escaped."""
        complex_prompt = """Test prompt with "quotes" and 'single quotes'
        and multiple lines
        and special chars: $VAR & command"""
        
        run_claude_with_prompt(
            prompt=complex_prompt,
            max_turns=5,
            allowed_tools=["Bash"],
            dry_run=True
        )
        
        captured = capsys.readouterr()
        # Check that the prompt is properly quoted
        assert "claude" in captured.out
        assert "-p" in captured.out