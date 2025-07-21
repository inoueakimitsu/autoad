"""Tests for prompt logging functionality in autoad.

This module tests the prompt logging features including JSON formatting,
output integration, and error handling.
"""
import json
import sys
from io import StringIO
from datetime import datetime
from unittest.mock import patch, MagicMock, call

import pytest

from autoad.main import format_prompt_as_jsonl, log_prompt, MAX_PROMPT_LENGTH, MAX_TURNS_IN_EACH_ITERATION


class TestPromptLogging:
    """Test suite for prompt logging functionality."""
    
    def test_format_prompt_as_jsonl_basic(self):
        """Test basic JSONL formatting of prompt."""
        prompt = "Test prompt"
        max_turns = MAX_TURNS_IN_EACH_ITERATION
        allowed_tools = ["Read", "Edit"]
        
        result = format_prompt_as_jsonl(prompt, max_turns, allowed_tools, False)
        parsed = json.loads(result.strip())
        
        assert parsed["type"] == "user_input"
        assert parsed["message"] == prompt
        assert "timestamp" in parsed
        assert "continue_conversation" not in parsed  # Should not include default values
        assert "max_turns" not in parsed  # Should not include default values
        assert parsed["allowed_tools"] == allowed_tools
    
    def test_format_prompt_as_jsonl_with_metadata(self):
        """Test JSONL formatting with all metadata fields."""
        prompt = "Test prompt with metadata"
        max_turns = 500  # Non-default value
        allowed_tools = ["Bash", "Write"]
        
        result = format_prompt_as_jsonl(prompt, max_turns, allowed_tools, True)
        parsed = json.loads(result.strip())
        
        assert parsed["type"] == "user_input"
        assert parsed["message"] == prompt
        assert parsed["continue_conversation"] is True
        assert parsed["max_turns"] == 500
        assert parsed["allowed_tools"] == allowed_tools
        
        # Verify timestamp is in ISO format
        datetime.fromisoformat(parsed["timestamp"])
    
    def test_format_prompt_as_jsonl_special_characters(self):
        """Test JSONL formatting with special characters and newlines."""
        prompt = 'Test with "quotes"\nand\nnewlines\tand\ttabs'
        max_turns = MAX_TURNS_IN_EACH_ITERATION
        allowed_tools = []
        
        result = format_prompt_as_jsonl(prompt, max_turns, allowed_tools, False)
        parsed = json.loads(result.strip())
        
        assert parsed["message"] == prompt
        assert "allowed_tools" not in parsed  # Empty list should not be included
        
        # Ensure the result is valid JSONL (single line)
        assert result.count('\n') == 1
        assert result.endswith('\n')
    
    def test_format_prompt_as_jsonl_large_prompt(self):
        """Test JSONL formatting with large prompts."""
        prompt = "x" * (MAX_PROMPT_LENGTH + 1000)
        max_turns = MAX_TURNS_IN_EACH_ITERATION
        allowed_tools = ["Read"]
        
        result = format_prompt_as_jsonl(prompt, max_turns, allowed_tools, False)
        parsed = json.loads(result.strip())
        
        assert len(parsed["message"]) == MAX_PROMPT_LENGTH
        assert parsed["message"] == "x" * MAX_PROMPT_LENGTH
    
    @patch('builtins.print')
    def test_log_prompt_basic(self, mock_print):
        """Test basic prompt logging to stdout."""
        prompt = "Test logging"
        max_turns = MAX_TURNS_IN_EACH_ITERATION
        allowed_tools = ["Edit"]
        
        log_prompt(prompt, max_turns, allowed_tools, False)
        
        mock_print.assert_called_once()
        call_args = mock_print.call_args
        output = call_args[0][0]
        
        # Verify it's valid JSON
        parsed = json.loads(output.strip())
        assert parsed["message"] == prompt
        
        # Verify print parameters
        assert call_args[1]["end"] == ""
        assert call_args[1]["flush"] is True
    
    @patch('builtins.print')
    @patch('autoad.main.format_prompt_as_jsonl')
    def test_log_prompt_error_handling(self, mock_format, mock_print):
        """Test error handling in prompt logging."""
        # Simulate JSON formatting error
        mock_format.side_effect = Exception("JSON error")
        
        # Should not raise exception
        log_prompt("test", 100, ["Read"], False)
        
        # Should print warning to stderr
        mock_print.assert_called_once()
        call_args = mock_print.call_args
        assert "Warning: Failed to log prompt" in call_args[0][0]
        assert call_args[1]["file"] == sys.stderr


class TestPromptLoggingIntegration:
    """Integration tests for prompt logging with TeeOutput."""
    
    @pytest.mark.integration
    def test_prompt_logging_with_tee_output(self):
        """Test prompt logging integration with TeeOutput."""
        from autoad.logging_utils import TeeOutput
        
        # Create string buffers for output
        console_output = StringIO()
        file_output = StringIO()
        
        # Create TeeOutput instance
        tee = TeeOutput(console_output, file_output)
        
        # Replace stdout temporarily
        original_stdout = sys.stdout
        sys.stdout = tee
        
        try:
            # Log a prompt
            log_prompt("Test with TeeOutput", 100, ["Read"], False)
            
            # Get outputs
            console_result = console_output.getvalue()
            file_result = file_output.getvalue()
            
            # Both outputs should be identical
            assert console_result == file_result
            
            # Verify JSON content
            parsed = json.loads(console_result.strip())
            assert parsed["message"] == "Test with TeeOutput"
            assert parsed["type"] == "user_input"
            
        finally:
            # Restore stdout
            sys.stdout = original_stdout
    
    @pytest.mark.integration
    def test_prompt_logging_time_ordering(self):
        """Test that prompts are logged in correct time order."""
        outputs = []
        
        with patch('builtins.print') as mock_print:
            # Log multiple prompts
            for i in range(3):
                log_prompt(f"Prompt {i}", 100, ["Read"], False)
            
            # Extract timestamps from calls
            for call in mock_print.call_args_list:
                output = call[0][0]
                parsed = json.loads(output.strip())
                outputs.append(parsed)
        
        # Verify timestamps are in ascending order
        timestamps = [datetime.fromisoformat(o["timestamp"]) for o in outputs]
        assert timestamps == sorted(timestamps)
        
        # Verify message order
        for i, output in enumerate(outputs):
            assert output["message"] == f"Prompt {i}"
    
    @pytest.mark.integration
    @patch('autoad.main.get_logging_manager')
    def test_prompt_logging_no_logging_option(self, mock_get_logging_manager):
        """Test prompt logging behavior with --no-logging option."""
        from autoad.main import run_claude_with_prompt
        
        # Simulate --no-logging option (LoggingManager is None)
        mock_get_logging_manager.return_value = None
        
        with patch('builtins.print') as mock_print:
            with patch('subprocess.Popen'):
                # This should not log the prompt
                # We'll verify by checking that log_prompt is not called
                with patch('autoad.main.log_prompt') as mock_log_prompt:
                    try:
                        run_claude_with_prompt("Test prompt", 100, ["Read"], False)
                    except:
                        # We expect this to fail due to mocked subprocess
                        pass
                    
                    # log_prompt should not be called
                    mock_log_prompt.assert_not_called()