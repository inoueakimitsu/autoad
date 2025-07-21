"""Unit tests for logging_utils module."""
import os
import sys
import tempfile
import shutil
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.autoad.logging_utils import (
    LoggingManager, TeeOutput, LoggingError, DirectoryCreationError,
    LogFileError, get_log_directory, set_logging_manager, get_logging_manager,
    LOG_DIR_ENV_VAR
)


class TestTeeOutput:
    """Test cases for TeeOutput class."""
    
    def test_write_to_multiple_targets(self):
        """Test writing to multiple targets simultaneously."""
        # Create mock targets
        target1 = MagicMock()
        target2 = MagicMock()
        target1.write.return_value = len("Hello, world!")
        target2.write.return_value = len("Hello, world!")
        
        # Create TeeOutput instance
        tee = TeeOutput(target1, target2)
        
        # Write some data
        data = "Hello, world!"
        result = tee.write(data)
        
        # Verify both targets were written to
        target1.write.assert_called_once_with(data)
        target2.write.assert_called_once_with(data)
        target1.flush.assert_called_once()
        target2.flush.assert_called_once()
        
        # Check return value (should be from the first target that succeeded)
        assert result == len(data)
    
    def test_flush_all_targets(self):
        """Test flushing all targets."""
        target1 = MagicMock()
        target2 = MagicMock()
        
        tee = TeeOutput(target1, target2)
        tee.flush()
        
        target1.flush.assert_called_once()
        target2.flush.assert_called_once()
    
    def test_write_error_handling(self):
        """Test that write continues even if one target fails."""
        target1 = MagicMock()
        target2 = MagicMock()
        target1.write.side_effect = IOError("Write failed")
        
        tee = TeeOutput(target1, target2)
        
        # Write should not raise exception
        tee.write("test data")
        
        # Second target should still be written to
        target2.write.assert_called_once_with("test data")
    
    def test_isatty(self):
        """Test isatty method."""
        target1 = MagicMock()
        target2 = MagicMock()
        target1.isatty.return_value = False
        target2.isatty.return_value = True
        
        tee = TeeOutput(target1, target2)
        assert tee.isatty() is True
        
        # Test when no targets are TTY
        target2.isatty.return_value = False
        assert tee.isatty() is False
    
    def test_fileno(self):
        """Test fileno method."""
        target1 = MagicMock()
        target2 = MagicMock()
        target1.fileno.return_value = 1
        
        tee = TeeOutput(target1, target2)
        assert tee.fileno() == 1
        
        # Test when no target has fileno
        del target1.fileno
        del target2.fileno
        
        with pytest.raises(AttributeError):
            tee.fileno()


class TestLoggingManager:
    """Test cases for LoggingManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_env = os.environ.get(LOG_DIR_ENV_VAR)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if self.original_env:
            os.environ[LOG_DIR_ENV_VAR] = self.original_env
        else:
            os.environ.pop(LOG_DIR_ENV_VAR, None)
    
    def test_init_with_defaults(self):
        """Test initialization with default values."""
        manager = LoggingManager()
        
        assert manager.session_id is not None
        assert manager.iteration_dir is None  # Created when entering context
        assert manager.log_dir.endswith(".autoad/logs")
        assert manager.metadata["status"] == "initialized"
    
    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        manager = LoggingManager(
            log_dir=self.temp_dir
        )
        
        assert manager.log_dir == self.temp_dir
        assert manager.session_id is not None
        assert manager.iteration_dir is None  # Created when entering context
    
    def test_resolve_log_directory_priority(self):
        """Test log directory resolution priority."""
        # Test CLI argument takes precedence (use temp dir to avoid permission issues)
        cli_path = os.path.join(self.temp_dir, "cli_path")
        env_path = os.path.join(self.temp_dir, "env_path")
        
        os.environ[LOG_DIR_ENV_VAR] = env_path
        manager = LoggingManager(log_dir=cli_path)
        assert manager.log_dir == cli_path
        
        # Test environment variable when no CLI arg
        manager = LoggingManager(log_dir=None)
        assert manager.log_dir == env_path
        
        # Test default when neither is set
        os.environ.pop(LOG_DIR_ENV_VAR)
        manager = LoggingManager(log_dir=None)
        assert manager.log_dir.endswith(".autoad/logs")
    
    def test_generate_session_id(self):
        """Test session ID generation."""
        manager = LoggingManager()
        
        # Check format YYYY-MM-DD-HH-MM-SS
        try:
            datetime.strptime(manager.session_id, "%Y-%m-%d-%H-%M-%S")
        except ValueError:
            pytest.fail("Session ID does not match expected format")
    
    def test_create_iteration_directory(self):
        """Test iteration directory creation."""
        manager = LoggingManager(
            log_dir=self.temp_dir
        )
        
        # Directory is created when entering context
        with manager:
            assert manager.iteration_dir is not None
            assert os.path.exists(manager.iteration_dir)
            
            # Check that directory name contains timestamp with microseconds
            dir_name = os.path.basename(manager.iteration_dir)
            parts = dir_name.split('-')
            assert len(parts) == 7  # YYYY-MM-DD-HH-MM-SS-microseconds
            
            # Check permissions (Unix only)
            if hasattr(os, 'stat'):
                stat_info = os.stat(manager.iteration_dir)
                assert stat_info.st_mode & 0o777 == 0o700
    
    def test_create_directory_error(self):
        """Test error handling when directory creation fails."""
        # Create a file where directory should be
        bad_path = os.path.join(self.temp_dir, "bad_dir")
        with open(bad_path, 'w') as f:
            f.write("blocking file")
        
        manager = LoggingManager(log_dir=self.temp_dir)
        manager.log_dir = bad_path  # Force bad path
        
        with pytest.raises(LogFileError):  # Changed to LogFileError as it's wrapped
            with manager:
                pass  # Directory creation should fail
    
    def test_context_manager_basic(self):
        """Test basic context manager functionality."""
        manager = LoggingManager(
            log_dir=self.temp_dir
        )
        
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        with manager:
            # Check that streams are redirected
            assert sys.stdout != original_stdout
            assert sys.stderr != original_stderr
            assert isinstance(sys.stdout, TeeOutput)
            assert isinstance(sys.stderr, TeeOutput)
            
            # Write some output
            print("Test stdout")
            print("Test stderr", file=sys.stderr)
        
        # Check that streams are restored
        assert sys.stdout == original_stdout
        assert sys.stderr == original_stderr
        
        # Check that log files exist
        stdout_log = os.path.join(manager.iteration_dir, "stdout.log")
        stderr_log = os.path.join(manager.iteration_dir, "stderr.log")
        assert os.path.exists(stdout_log)
        assert os.path.exists(stderr_log)
        
        # Check log contents
        with open(stdout_log, 'r') as f:
            assert "Test stdout" in f.read()
        
        with open(stderr_log, 'r') as f:
            assert "Test stderr" in f.read()
    
    def test_context_manager_with_exception(self):
        """Test context manager handles exceptions properly."""
        manager = LoggingManager(
            log_dir=self.temp_dir
        )
        
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        
        try:
            with manager:
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Streams should be restored
        assert sys.stdout == original_stdout
        assert sys.stderr == original_stderr
        
        # Metadata should reflect failure
        metadata_path = os.path.join(manager.iteration_dir, "metadata.json")
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        assert metadata["status"] == "failed"
        assert metadata["error"]["type"] == "ValueError"
        assert metadata["error"]["message"] == "Test error"
    
    def test_save_metadata(self):
        """Test metadata saving."""
        manager = LoggingManager(
            log_dir=self.temp_dir
        )
        
        # Add custom metadata
        manager.metadata["custom_field"] = "custom_value"
        manager.metadata["branch_name"] = "test-branch"
        
        with manager:
            pass
        
        # Check metadata file
        metadata_path = os.path.join(manager.iteration_dir, "metadata.json")
        with open(metadata_path, 'r') as f:
            saved_metadata = json.load(f)
        
        assert saved_metadata["session_id"] is not None
        assert saved_metadata["iteration_start_time"] is not None
        assert saved_metadata["custom_field"] == "custom_value"
        assert saved_metadata["branch_name"] == "test-branch"
        assert saved_metadata["status"] == "completed"
        assert "start_time" in saved_metadata
        assert "end_time" in saved_metadata
    
    def test_iteration_timestamp_generation(self):
        """Test that timestamp is generated in correct format with microseconds."""
        manager = LoggingManager(log_dir=self.temp_dir)
        
        timestamp = manager._generate_iteration_timestamp()
        
        # Check format YYYY-MM-DD-HH-MM-SS-microseconds
        parts = timestamp.split('-')
        assert len(parts) == 7
        
        # Verify it's a valid timestamp
        try:
            # Reconstruct without microseconds for datetime parsing
            dt_str = '-'.join(parts[:6])
            datetime.strptime(dt_str, "%Y-%m-%d-%H-%M-%S")
            
            # Check microseconds are 6 digits
            assert len(parts[6]) == 6
            assert parts[6].isdigit()
        except ValueError:
            pytest.fail("Timestamp does not match expected format")
    
    def test_directory_uniqueness(self):
        """Test that multiple managers create unique directories."""
        manager1 = LoggingManager(log_dir=self.temp_dir)
        manager2 = LoggingManager(log_dir=self.temp_dir)
        
        with manager1:
            with manager2:
                assert manager1.iteration_dir != manager2.iteration_dir
                assert os.path.exists(manager1.iteration_dir)
                assert os.path.exists(manager2.iteration_dir)
    
    def test_no_session_id_in_directory(self):
        """Test that directory name does not contain session ID or iter-N."""
        manager = LoggingManager(log_dir=self.temp_dir)
        
        with manager:
            dir_name = os.path.basename(manager.iteration_dir)
            assert "iter-" not in dir_name
            
            # Directory name should be timestamp with microseconds
            parts = dir_name.split('-')
            assert len(parts) == 7  # YYYY-MM-DD-HH-MM-SS-microseconds
            
            # The iteration timestamp should have microseconds while session_id doesn't
            assert len(parts[6]) == 6  # microseconds part


class TestUtilityFunctions:
    """Test cases for utility functions."""
    
    def test_get_log_directory(self):
        """Test get_log_directory function."""
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with CLI argument
            custom_path = os.path.join(temp_dir, "custom_path")
            log_dir = get_log_directory(custom_path)
            assert log_dir == custom_path
            
            # Test without CLI argument (uses default)
            log_dir = get_log_directory(None)
            assert log_dir.endswith(".autoad/logs")
    
    def test_set_and_get_logging_manager(self):
        """Test global logging manager setter and getter."""
        # Initially should be None
        assert get_logging_manager() is None
        
        # Set a manager
        manager = MagicMock()
        set_logging_manager(manager)
        assert get_logging_manager() is manager
        
        # Clear it
        set_logging_manager(None)
        assert get_logging_manager() is None


@pytest.mark.integration
class TestIntegration:
    """Integration tests for the logging system."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_multiple_iterations(self):
        """Test logging across multiple iterations."""
        iteration_dirs = []
        
        for i in range(1, 4):
            manager = LoggingManager(
                log_dir=self.temp_dir
            )
            
            with manager:
                print(f"Iteration {i} output")
                iteration_dirs.append(manager.iteration_dir)
        
        # Check all directories exist and are unique
        assert len(set(iteration_dirs)) == 3  # All unique
        
        for i, iter_dir in enumerate(iteration_dirs, 1):
            assert os.path.exists(iter_dir)
            
            # Check log content
            with open(os.path.join(iter_dir, "stdout.log"), 'r') as f:
                assert f"Iteration {i} output" in f.read()
    
    def test_concurrent_write_safety(self):
        """Test thread-safe writing to logs."""
        import threading
        
        manager = LoggingManager(
            log_dir=self.temp_dir
        )
        
        def write_output(thread_id):
            for i in range(10):
                print(f"Thread {thread_id} line {i}")
        
        with manager:
            threads = []
            for i in range(5):
                t = threading.Thread(target=write_output, args=(i,))
                threads.append(t)
                t.start()
            
            for t in threads:
                t.join()
        
        # Check that all output was captured
        with open(os.path.join(manager.iteration_dir, "stdout.log"), 'r') as f:
            content = f.read()
            
        # All threads should have written their output
        for thread_id in range(5):
            for line_num in range(10):
                assert f"Thread {thread_id} line {line_num}" in content