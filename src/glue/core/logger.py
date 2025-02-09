"""GLUE Framework Logging System"""

import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from loguru import logger
from pydantic import BaseModel

class LogConfig(BaseModel):
    """Configuration for logging"""
    log_path: Path = Path("logs")
    rotation: str = "10 MB"
    retention: str = "1 week"
    format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

class FlowLogContext(BaseModel):
    """Context for flow-related logs"""
    flow_id: str
    source_team: str
    target_team: str
    flow_type: str
    timestamp: datetime = datetime.now()
    metadata: Optional[Dict[str, Any]] = None

class TeamLogContext(BaseModel):
    """Context for team-related logs"""
    team_name: str
    action: str
    timestamp: datetime = datetime.now()
    metadata: Optional[Dict[str, Any]] = None

def setup_logging(config: Optional[LogConfig] = None) -> None:
    """Set up logging with the given configuration"""
    if config is None:
        config = LogConfig()
    
    # Create logs directory if it doesn't exist
    config.log_path.mkdir(parents=True, exist_ok=True)
    
    # Remove default logger
    logger.remove()
    
    # Add console handler with custom format
    logger.add(
        sys.stderr,
        format=config.format,
        level="INFO",
        backtrace=True,
        diagnose=True
    )
    
    # Add file handler for all logs
    logger.add(
        config.log_path / "glue.log",
        rotation=config.rotation,
        retention=config.retention,
        format=config.format,
        level="DEBUG",
        backtrace=True,
        diagnose=True
    )
    
    # Add file handler for errors only
    logger.add(
        config.log_path / "error.log",
        rotation=config.rotation,
        retention=config.retention,
        format=config.format,
        level="ERROR",
        backtrace=True,
        diagnose=True,
        filter=lambda record: record["level"].name == "ERROR"
    )

def log_flow_event(
    event_type: str,
    context: FlowLogContext,
    level: str = "INFO",
    **kwargs
) -> None:
    """Log a flow-related event with context"""
    logger.log(
        level,
        "\n{separator}\n{event_type}\n{separator}",
        separator="="*50,
        event_type=event_type,
        **{
            "flow_context": context.dict(),
            **kwargs
        }
    )

def log_team_event(
    event_type: str,
    context: TeamLogContext,
    level: str = "INFO",
    **kwargs
) -> None:
    """Log a team-related event with context"""
    logger.log(
        level,
        "\n{separator}\n{event_type}\n{separator}",
        separator="="*50,
        event_type=event_type,
        **{
            "team_context": context.dict(),
            **kwargs
        }
    )

def log_error(
    error_type: str,
    message: str,
    source: str,
    details: Optional[Dict[str, Any]] = None,
    **kwargs
) -> None:
    """Log an error with context"""
    logger.error(
        "\n{separator}\n{error_type}: {message}\n{separator}",
        separator="="*50,
        error_type=error_type,
        message=message,
        **{
            "error_context": {
                "source": source,
                "details": details,
                "timestamp": datetime.now().isoformat()
            },
            **kwargs
        }
    )

# Initialize logging with default configuration
setup_logging()
