"""Utilities for suppressing stderr at the OS file-descriptor level.

Used to silence noisy third-party imports (e.g. Basic Pitch) that write
warnings directly to stderr even when Python-level logging is quiet.

Note: documentation in this file was written with assistance from AI tools.
"""

from contextlib import contextmanager
import sys
import os

def suppress_import_stderr():
    """Redirects stderr to /dev/null at the OS fd level.

    Returns:
        int: The saved stderr file descriptor, needed to restore later.
    """
    devnull = os.open(os.devnull, os.O_WRONLY)
    original_stderr_fd = sys.stderr.fileno()
    saved_stderr_fd = os.dup(original_stderr_fd)
    os.dup2(devnull, original_stderr_fd)
    os.close(devnull)
    return saved_stderr_fd

def restore_import_stderr(saved_fd):
    """Restores stderr from a previously saved file descriptor.

    Args:
        saved_fd (int): The fd returned by suppress_import_stderr.
    """
    os.dup2(saved_fd, sys.stderr.fileno())
    os.close(saved_fd)

@contextmanager
def no_stderr():
    """Context manager that suppresses all stderr output for its duration."""
    saved = suppress_import_stderr()
    try:
        yield
    finally:
        restore_import_stderr(saved)
