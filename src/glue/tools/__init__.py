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
    'file_handler': FileHandlerTool,  # Added the exact tool name
    'write_file': FileHandlerTool,
    'file': FileHandlerTool,
    'save': FileHandlerTool,
    'write': FileHandlerTool,
    'output': FileHandlerTool,
    'store': FileHandlerTool,
    'export': FileHandlerTool,
    'files': FileHandlerTool,      # Added plural form
    'read_file': FileHandlerTool,  # Added read operation
    'read': FileHandlerTool,       # Added read keyword
    'load': FileHandlerTool,       # Added load keyword
    'import': FileHandlerTool,     # Added import keyword
    
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
