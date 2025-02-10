"""Enhanced logging setup for GLUE framework"""

import logging
import sys
from typing import Optional
from loguru import logger

class InterceptHandler(logging.Handler):
    """Intercepts standard logging and redirects to loguru"""
    
    def emit(self, record):
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def setup_logging(level: str = "INFO", 
                 format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
                 log_file: Optional[str] = None):
    """Configure logging with loguru"""
    
    # Remove default handler
    logger.remove()
    
    # Add console handler with custom format
    logger.add(
        sys.stderr,
        format=format,
        level=level,
        colorize=True
    )
    
    # Add file handler if specified
    if log_file:
        logger.add(
            log_file,
            rotation="10 MB",
            retention="1 week",
            compression="zip",
            format=format,
            level=level
        )
    
    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0)

def get_logger(name: str) -> logger:
    """Get a logger instance for the given name"""
    return logger.bind(name=name)

# Initialize default logging
setup_logging()
