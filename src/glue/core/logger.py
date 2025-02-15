"""Enhanced logging setup for GLUE framework"""

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

def setup_logging(
    level: str = "INFO",
    format: str = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    log_file: Optional[str] = None,
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

    # Configure file logging if log_file is provided
    if log_file:
        logger.add(
            log_file,
            rotation="10 MB",
            retention="1 week",
            compression="zip",
            format=format,
            level=level
        )

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
