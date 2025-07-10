"""
Common logging utility for VOLTS functional testing suite.
Provides consistent logging across all modules.
"""

import logging
import os
import sys
from pathlib import Path

def setup_logger(name: str, log_level: int = 1) -> logging.Logger:
    """
    Set up a logger with consistent formatting and level based on LOG_LEVEL.
    
    Args:
        name: Logger name (typically __name__)
        log_level: Log level (0=ERROR, 1=WARNING, 2=INFO, 3=DEBUG)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Clear any existing handlers
    logger.handlers.clear()
    
    # Map log levels
    level_map = {
        0: logging.ERROR,
        1: logging.WARNING,
        2: logging.INFO,
        3: logging.DEBUG
    }
    
    # Set log level
    logger.setLevel(level_map.get(log_level, logging.INFO))
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level_map.get(log_level, logging.INFO))
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger

def get_log_level() -> int:
    """
    Get log level from environment variable with proper validation.
    
    Returns:
        Log level (0-3), defaults to 1 if invalid
    """
    try:
        log_level = int(os.environ.get("LOG_LEVEL", "1"))
        if log_level not in [0, 1, 2, 3]:
            return 1
        return log_level
    except (ValueError, TypeError):
        return 1

class ErrorReporter:
    """
    Centralized error reporting for consistent error handling.
    """
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.errors = []
    
    def add_error(self, error: str, exception: Exception = None):
        """Add error to the error list and log it."""
        if exception:
            error_msg = f"{error}: {str(exception)}"
            self.logger.error(error_msg, exc_info=True)
        else:
            error_msg = error
            self.logger.error(error_msg)
        
        self.errors.append(error_msg)
    
    def add_warning(self, warning: str):
        """Add warning and log it."""
        self.logger.warning(warning)
    
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0
    
    def get_errors(self) -> list:
        """Get all errors."""
        return self.errors.copy()
    
    def get_error_summary(self) -> str:
        """Get a summary of all errors."""
        if not self.errors:
            return ""
        return " | ".join(self.errors)
    
    def clear_errors(self):
        """Clear all errors."""
        self.errors.clear()