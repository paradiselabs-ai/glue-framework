# src/glue/tools/__init__.py

"""GLUE Tool Implementations"""

from .base import BaseTool
from .web_search import WebSearchTool
from .file_handler import FileHandlerTool
from .code_interpreter import CodeInterpreterTool

__all__ = [
    'BaseTool',
    'WebSearchTool',
    'FileHandlerTool',
    'CodeInterpreterTool'
]

# Tool type mapping with intuitive keywords
TOOL_TYPES = {
    # Web Search Tool keywords
    'web_search': WebSearchTool,
    'search': WebSearchTool,
    'web': WebSearchTool,
    'browser': WebSearchTool,
    'google': WebSearchTool,
    'research': WebSearchTool,
    
    # File Handler Tool keywords
    'file_handler': FileHandlerTool,
    'write_file': FileHandlerTool,
    'file': FileHandlerTool,
    'save': FileHandlerTool,
    'write': FileHandlerTool,
    'output': FileHandlerTool,
    'store': FileHandlerTool,
    'export': FileHandlerTool,
    'files': FileHandlerTool,
    'read_file': FileHandlerTool,
    'read': FileHandlerTool,
    'load': FileHandlerTool,
    'import': FileHandlerTool,
    
    # Code Interpreter Tool keywords
    'code_interpreter': CodeInterpreterTool,
    'code': CodeInterpreterTool,
    'interpreter': CodeInterpreterTool,
    'execute': CodeInterpreterTool,
    'run': CodeInterpreterTool,
    'code_generator': CodeInterpreterTool,
    'generator': CodeInterpreterTool,
    'code_executor': CodeInterpreterTool,
    'executor': CodeInterpreterTool,
    'script': CodeInterpreterTool,
    'program': CodeInterpreterTool,
    'compile': CodeInterpreterTool,
    'build': CodeInterpreterTool
}
