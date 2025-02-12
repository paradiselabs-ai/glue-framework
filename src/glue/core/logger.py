"""Enhanced logging setup for GLUE framework"""

import logging
import sys
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from loguru import logger

@dataclass
class FlowLogContext:
    """Context for flow-related log events"""
    flow_id: str
    source_team: str
    target_team: str
    flow_type: str
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class TeamLogContext:
    """Context for team-related log events"""
    team_name: str
    action: str
    metadata: Optional[Dict[str, Any]] = None

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

def setup_logging(
    level: str = "INFO", 
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    log_file: Optional[str] = None,
    name: Optional[str] = None,
    log_dir: Optional[str] = None,
    development: bool = False
):
    """Configure logging with loguru"""
    
    # Remove default handler
    logger.remove()
    
    # Set level based on development mode
    if development:
        level = "DEBUG"
    
    # Add console handler with custom format
    logger.add(
        sys.stderr,
        format=format,
        level=level,
        colorize=True
    )
    
    # Configure file logging
    if log_dir:
        # Create log directory if it doesn't exist
        import os
        os.makedirs(log_dir, exist_ok=True)
        
        # Generate log file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_name = f"{name}_" if name else ""
        log_file = os.path.join(log_dir, f"{log_name}{timestamp}.log")
        
        # Add file handler
        logger.add(
            log_file,
            rotation="10 MB",
            retention="1 week",
            compression="zip",
            format=format,
            level=level
        )
    elif log_file:
        # Use specified log file
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

def log_flow_event(event: str, context: FlowLogContext) -> None:
    """Log a flow-related event with context"""
    logger.info(
        f"Flow Event: {event}\n"
        f"Flow ID: {context.flow_id}\n"
        f"Source: {context.source_team}\n"
        f"Target: {context.target_team}\n"
        f"Type: {context.flow_type}"
        + (f"\nMetadata: {context.metadata}" if context.metadata else "")
    )

def log_team_event(event: str, context: TeamLogContext) -> None:
    """Log a team-related event with context"""
    logger.info(
        f"Team Event: {event}\n"
        f"Team: {context.team_name}\n"
        f"Action: {context.action}"
        + (f"\nMetadata: {context.metadata}" if context.metadata else "")
    )

def log_error(error_type: str, message: str, source: str, metadata: Optional[Dict[str, Any]] = None) -> None:
    """Log an error with context"""
    logger.error(
        f"Error Type: {error_type}\n"
        f"Message: {message}\n"
        f"Source: {source}"
        + (f"\nMetadata: {metadata}" if metadata else "")
    )

# Initialize default logging
setup_logging()

# Alias for backward compatibility
init_logger = setup_logging
