"""Core components of the GLUE framework"""

# Import types and utilities first as they have no dependencies
from .types import AdhesiveType, ResourceState
from .logger import logger, get_logger
from .state import StateManager

# Import core models that others depend on
from .model import Model
from .tool_binding import ToolBinding

# Import workspace and context which depend on models
from .workspace import Workspace
from .context import ContextAnalyzer, ContextState

# Lazy imports for circular dependencies
def __getattr__(name):
    if name == "Team":
        from .team import Team
        return Team
    elif name in ("GlueApp", "AppConfig"):
        from .app import GlueApp, AppConfig
        if name == "GlueApp":
            return GlueApp
        return AppConfig
    raise AttributeError(f"module {__name__} has no attribute {name}")

__all__ = [
    "GlueApp",
    "AppConfig",
    "Model",
    "Team",
    "AdhesiveType",
    "ResourceState",
    "ToolBinding",
    "Workspace",
    "ContextAnalyzer",
    "ContextState",
    "logger",
    "get_logger",
    "StateManager"
]
