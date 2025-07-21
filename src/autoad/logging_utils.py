"""Logging utilities for autoad execution output management.

This module provides functionality to capture and save stdout/stderr outputs
to external directories with timestamp-based organization, preventing accidental
commits of log files to Git repositories.
"""
import os
import sys
import json
import threading
import subprocess
import queue
from datetime import datetime
from typing import Optional, Dict, Any, TextIO, List, Tuple, Union
from pathlib import Path

# Environment variable for log directory configuration
LOG_DIR_ENV_VAR = "AUTOAD_LOG_DIR"

# Default log directory under user's home
DEFAULT_LOG_DIR = "~/.autoad/logs"


class LoggingError(Exception):
    """Base exception for logging-related errors."""
    pass


class DirectoryCreationError(LoggingError):
    """Raised when log directory creation fails."""
    pass


class LogFileError(LoggingError):
    """Raised when log file operations fail."""
    pass


class TeeOutput:
    """Splits output to multiple destinations (console and file).
    
    This class acts as a file-like object that writes to multiple targets
    simultaneously, enabling real-time console output while saving to files.
    """
    
    def __init__(self, *targets: TextIO):
        """Initialize TeeOutput with multiple target streams.
        
        Args:
            *targets: Variable number of file-like objects to write to.
        """
        self.targets = list(targets)
        self._lock = threading.Lock()
    
    def write(self, data: str) -> int:
        """Write data to all target streams.
        
        Args:
            data: String data to write.
            
        Returns:
            Number of characters written.
        """
        with self._lock:
            written = 0
            for target in self.targets:
                try:
                    written = target.write(data)
                    target.flush()  # Ensure real-time output
                except Exception as e:
                    # Log write errors but continue with other targets
                    print(f"Warning: Failed to write to target: {e}", file=sys.stderr)
            return written
    
    def flush(self):
        """Flush all target streams."""
        with self._lock:
            for target in self.targets:
                try:
                    target.flush()
                except Exception:
                    pass  # Ignore flush errors
    
    def isatty(self) -> bool:
        """Check if any target is a TTY."""
        return any(hasattr(target, 'isatty') and target.isatty() 
                  for target in self.targets)
    
    def fileno(self) -> int:
        """Return file descriptor of the first target that has one."""
        for target in self.targets:
            if hasattr(target, 'fileno'):
                try:
                    return target.fileno()
                except Exception:
                    continue
        raise AttributeError("No target has a valid file descriptor")


class LoggingManager:
    """Manages logging setup for each optimization iteration.
    
    Creates iteration-specific directories and redirects stdout/stderr
    to log files while maintaining console output.
    """
    
    def __init__(self, log_dir: Optional[str] = None):
        """Initialize LoggingManager for an iteration.
        
        Args:
            log_dir: Custom log directory path (overrides defaults).
        """
        self.log_dir = self._resolve_log_directory(log_dir)
        self.session_id = self._generate_session_id()  # Keep for metadata only
        self.iteration_dir = None  # Will be created when entering context
        
        # File handles and original streams
        self.stdout_log: Optional[TextIO] = None
        self.stderr_log: Optional[TextIO] = None
        self.original_stdout: Optional[TextIO] = None
        self.original_stderr: Optional[TextIO] = None
        
        # Metadata for tracking execution details
        self.metadata: Dict[str, Any] = {
            "session_id": self.session_id,
            "iteration_start_time": None,  # Will be set when creating directory
            "start_time": None,
            "end_time": None,
            "status": "initialized"
        }
    
    def _resolve_log_directory(self, log_dir: Optional[str]) -> str:
        """Resolve log directory from CLI args, env vars, or default.
        
        Priority: CLI argument > Environment variable > Default
        
        Args:
            log_dir: Directory path from CLI argument.
            
        Returns:
            Absolute path to the log directory.
        """
        if log_dir:
            # CLI argument takes precedence
            return os.path.abspath(os.path.expanduser(log_dir))
        
        # Check environment variable
        env_dir = os.environ.get(LOG_DIR_ENV_VAR)
        if env_dir:
            return os.path.abspath(os.path.expanduser(env_dir))
        
        # Use default
        return os.path.abspath(os.path.expanduser(DEFAULT_LOG_DIR))
    
    def _generate_session_id(self) -> str:
        """Generate session ID in YYYY-MM-DD-HH-MM-SS format.
        
        Returns:
            Formatted timestamp string.
        """
        return datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    
    def _generate_iteration_timestamp(self) -> str:
        """Generate iteration timestamp with microsecond precision.
        
        Returns:
            Formatted timestamp string YYYY-MM-DD-HH-MM-SS-microseconds.
        """
        return datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
    
    def _create_iteration_directory(self) -> str:
        """Create iteration-specific directory with proper permissions.
        
        Returns:
            Path to the created directory.
            
        Raises:
            DirectoryCreationError: If directory creation fails.
        """
        # Generate iteration timestamp
        timestamp = self._generate_iteration_timestamp()
        self.metadata["iteration_start_time"] = timestamp
        
        # Validate and sanitize directory name
        dir_name = self._sanitize_filename(timestamp)
        
        # Prevent path traversal attacks
        if '..' in dir_name or '/' in dir_name or '\\' in dir_name:
            raise DirectoryCreationError(
                f"Invalid directory name: {dir_name}")
        
        full_path = os.path.join(self.log_dir, dir_name)
        
        # Additional path validation
        full_path = os.path.abspath(full_path)
        if not full_path.startswith(os.path.abspath(self.log_dir)):
            raise DirectoryCreationError(
                "Directory path escapes log directory")
        
        # Retry mechanism for handling concurrent directory creation
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Create with restricted permissions (owner only)
                os.makedirs(full_path, mode=0o700, exist_ok=False)
                break  # Success, exit retry loop
            except FileExistsError:
                retry_count += 1
                if retry_count >= max_retries:
                    raise DirectoryCreationError(
                        f"Failed to create unique directory after {max_retries} attempts")
                
                # Generate new timestamp and retry
                import time
                time.sleep(0.001)  # Brief pause before retry
                timestamp = self._generate_iteration_timestamp()
                self.metadata["iteration_start_time"] = timestamp
                dir_name = self._sanitize_filename(timestamp)
                full_path = os.path.join(self.log_dir, dir_name)
                full_path = os.path.abspath(full_path)
        
        try:
            # Verify permissions on directory
            if not os.access(full_path, os.W_OK):
                raise DirectoryCreationError(
                    f"Directory exists but is not writable: {full_path}")
            
            # Set permissions explicitly (in case umask affected creation)
            try:
                os.chmod(full_path, 0o700)
            except OSError:
                pass  # Best effort
            
            return full_path
            
        except OSError as e:
            # Check for specific error conditions
            if e.errno == 28:  # ENOSPC - No space left on device
                raise DirectoryCreationError(
                    f"No space left on device: {full_path}") from e
            elif e.errno == 13:  # EACCES - Permission denied
                # Try fallback to temp directory
                fallback_dir = self._try_fallback_directory()
                if fallback_dir:
                    return fallback_dir
                raise DirectoryCreationError(
                    f"Permission denied: {full_path}") from e
            else:
                raise DirectoryCreationError(
                    f"Failed to create log directory {full_path}: {e}") from e
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename to prevent security issues.
        
        Args:
            name: The filename to sanitize.
            
        Returns:
            Sanitized filename.
        """
        # Remove potentially dangerous characters
        dangerous_chars = ['/', '\\', '..', '~', '$', '`', '|', ';', '&', 
                          '(', ')', '<', '>', '*', '?', '[', ']', '{', '}']
        
        sanitized = name
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Limit length
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        
        return sanitized
    
    def _try_fallback_directory(self) -> Optional[str]:
        """Try to create directory in system temp as fallback.
        
        Returns:
            Path to fallback directory or None if failed.
        """
        try:
            import tempfile
            temp_base = tempfile.gettempdir()
            # Use iteration timestamp for fallback directory as well
            timestamp = self._generate_iteration_timestamp()
            self.metadata["iteration_start_time"] = timestamp
            fallback_path = os.path.join(temp_base, "autoad_logs", timestamp)
            os.makedirs(fallback_path, mode=0o700, exist_ok=True)
            print(f"Warning: Using fallback log directory: {fallback_path}", 
                  file=sys.stderr)
            return fallback_path
        except Exception:
            return None
    
    def __enter__(self):
        """Enter context manager: set up logging redirection.
        
        Returns:
            Self for use in with statement.
        """
        try:
            # Create iteration directory when entering context
            self.iteration_dir = self._create_iteration_directory()
            
            # Create log files
            stdout_path = os.path.join(self.iteration_dir, "stdout.log")
            stderr_path = os.path.join(self.iteration_dir, "stderr.log")
            
            self.stdout_log = open(stdout_path, 'w', encoding='utf-8', buffering=1)
            self.stderr_log = open(stderr_path, 'w', encoding='utf-8', buffering=1)
            
            # Save original streams
            self.original_stdout = sys.stdout
            self.original_stderr = sys.stderr
            
            # Create tee outputs
            sys.stdout = TeeOutput(self.original_stdout, self.stdout_log)
            sys.stderr = TeeOutput(self.original_stderr, self.stderr_log)
            
            # Update metadata
            self.metadata["start_time"] = datetime.now().isoformat()
            self.metadata["status"] = "running"
            
            return self
            
        except Exception as e:
            # Clean up on error
            self._cleanup()
            raise LogFileError(f"Failed to set up logging: {e}") from e
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager: restore streams and save metadata.
        
        Args:
            exc_type: Exception type if an error occurred.
            exc_val: Exception value if an error occurred.
            exc_tb: Exception traceback if an error occurred.
        """
        # Update metadata
        self.metadata["end_time"] = datetime.now().isoformat()
        self.metadata["status"] = "failed" if exc_type else "completed"
        
        if exc_type:
            self.metadata["error"] = {
                "type": exc_type.__name__,
                "message": str(exc_val)
            }
        
        # Save metadata before cleanup
        try:
            self.save_metadata()
        except Exception as e:
            print(f"Warning: Failed to save metadata: {e}", file=sys.stderr)
        
        # Restore original streams
        if self.original_stdout:
            sys.stdout = self.original_stdout
        if self.original_stderr:
            sys.stderr = self.original_stderr
        
        # Clean up resources
        self._cleanup()
    
    def _cleanup(self):
        """Close all open file handles."""
        if self.stdout_log:
            try:
                self.stdout_log.close()
            except Exception:
                pass
        
        if self.stderr_log:
            try:
                self.stderr_log.close()
            except Exception:
                pass
    
    def save_metadata(self):
        """Save execution metadata to JSON file."""
        metadata_path = os.path.join(self.iteration_dir, "metadata.json")
        
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
        except Exception as e:
            raise LogFileError(f"Failed to save metadata: {e}") from e


def get_log_directory(cli_arg: Optional[str]) -> str:
    """Get the log directory path based on configuration priority.
    
    Priority: CLI argument > Environment variable > Default
    
    Args:
        cli_arg: Log directory path from command line argument.
        
    Returns:
        Absolute path to the log directory.
    """
    if cli_arg:
        # CLI argument takes precedence
        return os.path.abspath(os.path.expanduser(cli_arg))
    
    # Check environment variable
    env_dir = os.environ.get(LOG_DIR_ENV_VAR)
    if env_dir:
        return os.path.abspath(os.path.expanduser(env_dir))
    
    # Use default
    return os.path.abspath(os.path.expanduser(DEFAULT_LOG_DIR))


def set_logging_manager(manager: Optional[LoggingManager]):
    """Set the global logging manager for subprocess integration.
    
    Args:
        manager: LoggingManager instance or None to clear.
    """
    global _current_logging_manager
    _current_logging_manager = manager


def get_logging_manager() -> Optional[LoggingManager]:
    """Get the current global logging manager.
    
    Returns:
        Current LoggingManager instance or None.
    """
    return _current_logging_manager


# Global variable for subprocess integration
_current_logging_manager: Optional[LoggingManager] = None


def _stream_output(pipe: Optional[TextIO], 
                  output_list: List[str],
                  log_file: Optional[TextIO] = None,
                  console: Optional[TextIO] = None) -> None:
    """Stream output from a pipe to multiple destinations.
    
    This function reads from a pipe line by line and writes to:
    - A list for collecting output
    - An optional log file
    - An optional console output
    
    Args:
        pipe: The pipe to read from (stdout or stderr).
        output_list: List to collect output lines.
        log_file: Optional file to write output to.
        console: Optional console stream (sys.stdout/stderr).
    """
    if not pipe:
        return
        
    try:
        for line in pipe:
            # Append to output list
            output_list.append(line)
            
            # Write to log file
            if log_file:
                try:
                    log_file.write(line)
                    log_file.flush()
                except Exception:
                    pass  # Continue even if logging fails
            
            # Write to console
            if console:
                try:
                    console.write(line)
                    console.flush()
                except Exception:
                    pass  # Continue even if console write fails
    except Exception:
        pass  # Pipe closed or other error
    finally:
        if pipe:
            try:
                pipe.close()
            except Exception:
                pass


def run_command_with_logging(command: List[str],
                            timeout: Optional[int] = None,
                            check: bool = True,
                            capture_output: bool = True,
                            text: bool = True,
                            **kwargs) -> subprocess.CompletedProcess:
    """Run a command with optional logging support.
    
    This function wraps subprocess.run to add logging capabilities when
    a global LoggingManager is set.
    
    Args:
        command: Command and arguments to execute.
        timeout: Optional timeout in seconds.
        check: Whether to raise CalledProcessError on non-zero exit.
        capture_output: Whether to capture stdout/stderr.
        text: Whether to decode output as text.
        **kwargs: Additional arguments for subprocess.run.
        
    Returns:
        CompletedProcess instance with results.
        
    Raises:
        subprocess.CalledProcessError: If check=True and exit code non-zero.
        subprocess.TimeoutExpired: If timeout expires.
    """
    global _current_logging_manager
    
    # If no logging manager or not capturing output, use standard subprocess.run
    if not _current_logging_manager or not capture_output:
        return subprocess.run(command, timeout=timeout, check=check,
                            capture_output=capture_output, text=text, **kwargs)
    
    # Set up logging-aware process execution
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
        bufsize=1 if text else -1,  # Line buffering for text mode
        **kwargs
    )
    
    stdout_lines = []
    stderr_lines = []
    
    # Get log files from current manager
    stdout_log = getattr(_current_logging_manager, 'stdout_log', None)
    stderr_log = getattr(_current_logging_manager, 'stderr_log', None)
    
    # Create threads for streaming output
    stdout_thread = threading.Thread(
        target=_stream_output,
        args=(process.stdout, stdout_lines, stdout_log, sys.stdout)
    )
    stderr_thread = threading.Thread(
        target=_stream_output,
        args=(process.stderr, stderr_lines, stderr_log, sys.stderr)
    )
    
    # Start streaming threads
    stdout_thread.start()
    stderr_thread.start()
    
    # Wait for process to complete
    try:
        return_code = process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        raise subprocess.TimeoutExpired(command, timeout)
    
    # Wait for threads to finish
    stdout_thread.join()
    stderr_thread.join()
    
    # Collect output
    stdout = ''.join(stdout_lines) if text else b''.join(stdout_lines)
    stderr = ''.join(stderr_lines) if text else b''.join(stderr_lines)
    
    # Create CompletedProcess result
    result = subprocess.CompletedProcess(
        args=command,
        returncode=return_code,
        stdout=stdout,
        stderr=stderr
    )
    
    # Check return code if requested
    if check and return_code != 0:
        raise subprocess.CalledProcessError(
            return_code, command, output=stdout, stderr=stderr
        )
    
    return result