# src/glue/core/logger.py

"""GLUE Logging System"""

import os
import sys
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

class GlueLogger:
    """GLUE Logger with support for development and production modes"""
    
    def __init__(
        self,
        name: str,
        log_dir: Optional[str] = None,
        development: bool = False
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG if development else logging.INFO)
        self.development = development
        
        # Remove any existing handlers
        self.logger.handlers = []
        
        # Console handler - shows debug info in development
        console_handler = logging.StreamHandler(sys.stdout)
        if development:
            # In development, show all levels with timestamp
            console_handler.setLevel(logging.DEBUG)
            console_format = logging.Formatter(
                '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
                datefmt='%H:%M:%S'
            )
        else:
            # In production, show only info and above
            console_handler.setLevel(logging.INFO)
            console_format = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_format)
        self.logger.addHandler(console_handler)
        
        # File handler - always shows full debug info
        if log_dir:
            log_dir = Path(log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Create daily log file
            today = datetime.now().strftime('%Y-%m-%d')
            log_file = log_dir / f"{name}_{today}.log"
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_format)
            self.logger.addHandler(file_handler)
    
    def debug(self, msg: str, *args, **kwargs):
        """Log debug message (only shown in development)"""
        if self.development:
            self.logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        """Log info message (shown in both modes)"""
        self.logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        """Log warning message"""
        self.logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        """Log error message"""
        self.logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        """Log critical error message"""
        self.logger.critical(msg, *args, **kwargs)

# Global logger instance
_logger: Optional[GlueLogger] = None

def init_logger(
    name: str = "glue",
    log_dir: Optional[str] = None,
    development: bool = False
) -> GlueLogger:
    """Initialize global logger"""
    global _logger
    _logger = GlueLogger(name, log_dir, development)
    return _logger

def get_logger() -> GlueLogger:
    """Get global logger instance"""
    if _logger is None:
        return init_logger()
    return _logger
