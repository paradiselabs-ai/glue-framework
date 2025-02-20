"""
GLUE (GenAI Linking & Unification Engine)

A framework for building AI applications with:
- Models with Adhesive Tool Usage
- Teams with Natural Communication
- Magnetic Information Flow
"""

from .core.app import GlueApp, AppConfig
from .core.model import Model
from .core.team import Team
from .core.types import AdhesiveType, ResourceState
from .core.tool_binding import ToolBinding
from .core.workspace import Workspace
from .core.context import ContextAnalyzer, ContextState
from .core.logger import logger, get_logger
from .core.state import StateManager

from .tools.base import BaseTool
from .tools.web_search import WebSearchTool
from .tools.file_handler import FileHandlerTool
from .tools.code_interpreter import CodeInterpreterTool

from .providers.base import BaseProvider
from .providers.openrouter import OpenRouterProvider

from .magnetic.field import MagneticField

__version__ = "0.1.0"

__all__ = [
    # Core
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
    "StateManager",
    
    # Tools
    "BaseTool",
    "WebSearchTool",
    "FileHandlerTool",
    "CodeInterpreterTool",
    
    # Providers
    "BaseProvider",
    "OpenRouterProvider",
    
    # Magnetic
    "MagneticField"
]
