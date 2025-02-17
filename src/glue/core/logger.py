"""Enhanced logging with Loguru for GLUE framework"""

import sys
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from loguru import logger
from pydantic import BaseModel, Field

class LogContext(BaseModel):
    """Base context for structured logging"""
    timestamp: datetime = Field(default_factory=datetime.now)
    component: str
    action: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FlowLogContext(LogContext):
    """Context for flow-related logs"""
    flow_id: str
    source_team: str
    target_team: str
    flow_type: str
    adhesive_type: Optional[str] = None

class TeamLogContext(LogContext):
    """Context for team-related logs"""
    team_name: str
    model_name: Optional[str] = None
    tool_name: Optional[str] = None

class ToolLogContext(LogContext):
    """Context for tool-related logs"""
    tool_name: str
    adhesive_type: str
    team_name: Optional[str] = None
    model_name: Optional[str] = None

def setup_logging(
    level: str = "INFO",
    format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    ),
    log_file: Optional[str] = None,
    development: bool = False
):
    """
    Backward compatibility wrapper for setup_enhanced_logging.
    Redirects to enhanced logging setup with appropriate defaults.
    """
    if development:
        level = "DEBUG"
    
    setup_enhanced_logging(
        level=level,
        format=format,
        log_dir="logs" if log_file else None
    )

def get_logger(name: str) -> logger:
    """
    Backward compatibility wrapper for get_enhanced_logger.
    Automatically determines component from name.
    """
    # Map common name prefixes to components
    component_map = {
        "flow": "flow",
        "team": "team",
        "tool": "tool",
        "model": "model",
        "magnetic": "magnetic",
        "error": "error"
    }
    
    # Determine component from name prefix
    component = "system"  # default
    for prefix, comp in component_map.items():
        if name.startswith(prefix):
            component = comp
            break
    
    return get_enhanced_logger(name, component)

def setup_enhanced_logging(
    log_dir: str = "logs",
    level: str = "INFO",
    rotation: str = "10 MB",
    retention: str = "1 week",
    format: str = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<yellow>{extra[context]}</yellow> - "
        "<level>{message}</level>"
    )
):
    """Configure enhanced logging with Loguru"""
    
    # Remove default handler
    logger.remove()
    
    # Create log directory if it doesn't exist
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    # Add console handler
    logger.add(
        sys.stderr,
        format=format,
        level=level,
        colorize=True,
        backtrace=True,
        diagnose=True
    )
    
    if log_dir:
        # Add rotating file handler for all logs
        logger.add(
            f"{log_dir}/glue_{{time}}.log",
            format=format,
            level=level,
            rotation=rotation,
            retention=retention,
            compression="zip",
            backtrace=True,
            diagnose=True
        )
        
        # Add separate handlers for different components
        components = ["flow", "team", "tool", "model", "magnetic"]
        for component in components:
            logger.add(
                f"{log_dir}/{component}_{{time}}.log",
                format=format,
                level=level,
                rotation=rotation,
                retention=retention,
                compression="zip",
                filter=lambda record: record["extra"].get("component") == component
            )

def get_enhanced_logger(name: str, component: str) -> logger:
    """Get an enhanced logger instance with component context"""
    return logger.bind(name=name, component=component)

def log_flow_event(context: FlowLogContext, message: str, level: str = "INFO") -> None:
    """Log a flow-related event with structured context"""
    logger_instance = get_enhanced_logger("flow", "flow")
    log_func = getattr(logger_instance, level.lower())
    
    context_dict = {
        "context": "flow",
        "flow_id": context.flow_id,
        "source": context.source_team,
        "target": context.target_team,
        "type": context.flow_type,
        **context.metadata
    }
    
    if context.adhesive_type:
        context_dict["adhesive"] = context.adhesive_type
    
    log_func(
        message,
        **context_dict
    )

def log_team_event(context: TeamLogContext, message: str, level: str = "INFO") -> None:
    """Log a team-related event with structured context"""
    logger_instance = get_enhanced_logger("team", "team")
    log_func = getattr(logger_instance, level.lower())
    
    context_dict = {
        "context": "team",
        "team": context.team_name,
        **context.metadata
    }
    
    if context.model_name:
        context_dict["model"] = context.model_name
    if context.tool_name:
        context_dict["tool"] = context.tool_name
    
    log_func(
        message,
        **context_dict
    )

def log_tool_event(context: ToolLogContext, message: str, level: str = "INFO") -> None:
    """Log a tool-related event with structured context"""
    logger_instance = get_enhanced_logger("tool", "tool")
    log_func = getattr(logger_instance, level.lower())
    
    context_dict = {
        "context": "tool",
        "tool": context.tool_name,
        "adhesive": context.adhesive_type,
        **context.metadata
    }
    
    if context.team_name:
        context_dict["team"] = context.team_name
    if context.model_name:
        context_dict["model"] = context.model_name
    
    log_func(
        message,
        **context_dict
    )

def log_error(
    error_type: str,
    message: str,
    component: str,
    metadata: Optional[Dict[str, Any]] = None
) -> None:
    """Log an error with structured context"""
    logger_instance = get_enhanced_logger("error", component)
    
    context_dict = {
        "context": "error",
        "error_type": error_type,
        "component": component
    }
    
    if metadata:
        context_dict.update(metadata)
    
    logger_instance.error(
        f"{error_type}: {message}",
        **context_dict
    )

# Initialize enhanced logging with default settings
setup_enhanced_logging()

# Alias for backward compatibility
init_logger = setup_logging
