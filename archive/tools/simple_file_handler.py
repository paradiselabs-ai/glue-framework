"""Simplified File Handler Tool Implementation"""

import os
import json
import yaml
import csv
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union
from .simple_base import SimpleBaseTool, ToolConfig, ToolPermission
from ..core.logger import get_logger

class SimpleFileHandlerTool(SimpleBaseTool):
    """
    Simplified tool for handling file operations.
    
    Features:
    - Read/write/append operations
    - Multiple format support
    - Simple state management (IDLE/ACTIVE)
    - Path validation
    """
    
    SUPPORTED_FORMATS = {
        ".txt": "text",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".csv": "csv",
        ".py": "text",
        ".js": "text",
        ".html": "text",
        ".css": "text",
        ".md": "text"
    }
    
    DEFAULT_FORMAT = ".md"  # Default to markdown
    
    def __init__(
        self,
        name: str = "file_handler",
        description: str = "Handles file operations with format support",
        workspace_dir: Optional[str] = None,
        sticky: bool = False
    ):
        super().__init__(
            name=name,
            description=description,
            config=ToolConfig(
                required_permissions=[
                    ToolPermission.FILE_SYSTEM,
                    ToolPermission.READ,
                    ToolPermission.WRITE
                ],
                cache_results=False
            ),
            sticky=sticky
        )
        
        # Use workspace_dir if provided, otherwise use cwd
        self.base_path = os.path.abspath(workspace_dir or os.getcwd())
        self.logger = get_logger()

    def _validate_path(self, file_path: str) -> Path:
        """Validate and resolve file path"""
        self.logger.debug(f"Validating path: {file_path}")
        
        # Skip URLs - they should be handled by web_search
        if any(pattern in file_path.lower() for pattern in [
            'http://', 'https://', 'www.', '.com', '.org', '.edu'
        ]):
            raise ValueError("Cannot handle URLs directly. Use web_search tool instead.")
        
        # Clean up path
        file_path = file_path.strip(' "\'/')
        
        # Add default extension if no extension present
        if not os.path.splitext(file_path)[1]:
            file_path = f"{file_path}{self.DEFAULT_FORMAT}"
        
        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.base_path, file_path)
        
        # Resolve to absolute path
        abs_path = os.path.abspath(os.path.realpath(file_path))
        base_path = os.path.abspath(os.path.realpath(self.base_path))
        
        # Check if path is within base directory
        if not abs_path.startswith(base_path):
            raise ValueError(f"Access denied: {file_path} is outside base directory")

        return Path(abs_path)

    def _get_format_handler(self, file_path: Path) -> str:
        """Get appropriate format handler for file"""
        suffix = file_path.suffix.lower()
        if suffix not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {suffix}. "
                f"Supported: {list(self.SUPPORTED_FORMATS.keys())}"
            )
        return self.SUPPORTED_FORMATS[suffix]

    def _extract_topic(self, content: str) -> Optional[str]:
        """Extract topic from content for filename"""
        # Look for title
        title_match = re.search(r'^Title:\s*(.+?)(?:\n|$)', content, re.MULTILINE | re.IGNORECASE)
        if title_match:
            return title_match.group(1).strip()
        
        # Look for first heading after Research Results
        heading_match = re.search(r'^# Research Results: (.+?)\n.*?### \d+\.\s*(.+?)\n', content, re.DOTALL)
        if heading_match:
            query = heading_match.group(1).strip()
            first_result = heading_match.group(2).strip()
            # Use query if it's specific, otherwise use first result title
            return query if len(query.split()) > 2 else first_result
        
        return None

    async def _execute(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute file operation"""
        # Handle positional arguments
        content = args[0] if args else kwargs
        
        # Infer operation and path
        operation = "write"  # Default to write
        file_path = None
        operation_content = None
        
        if isinstance(content, dict):
            file_path = content.get('file_path', content.get('path', 'document'))
            operation = content.get('operation', 'write')
            operation_content = content.get('content', '')
        elif isinstance(content, str):
            operation_content = content
            # Extract topic for filename
            topic = self._extract_topic(content)
            if topic:
                # Convert to snake case
                topic = re.sub(r'[^\w\s-]', '', topic)
                topic = re.sub(r'[-\s]+', '_', topic)
                topic = topic.strip('_').lower()
                file_path = topic
            else:
                file_path = "document"
        
        # Validate path
        path = self._validate_path(file_path)
        format_handler = self._get_format_handler(path)
        
        try:
            result = None
            if operation == "read":
                if not path.exists():
                    raise FileNotFoundError(f"File not found: {path}")
                    
                with open(path, 'r') as f:
                    if format_handler == "text":
                        content = f.read()
                    elif format_handler == "json":
                        content = json.load(f)
                    elif format_handler == "yaml":
                        content = yaml.safe_load(f)
                    elif format_handler == "csv":
                        content = list(csv.DictReader(f))
                        
                result = {
                    "success": True,
                    "operation": "read",
                    "format": format_handler,
                    "content": content,
                    "path": str(path)
                }
            else:  # write/append
                os.makedirs(path.parent, exist_ok=True)
                mode = 'a' if operation == "append" else 'w'
                
                with open(path, mode) as f:
                    if format_handler == "text":
                        f.write(str(operation_content))
                    elif format_handler == "json":
                        json.dump(operation_content, f, indent=2)
                    elif format_handler == "yaml":
                        yaml.safe_dump(operation_content, f)
                    elif format_handler == "csv":
                        if not isinstance(operation_content, list):
                            raise ValueError("CSV content must be a list of dictionaries")
                        writer = csv.DictWriter(f, fieldnames=operation_content[0].keys())
                        if mode == 'w':
                            writer.writeheader()
                        writer.writerows(operation_content)
                
                result = {
                    "success": True,
                    "operation": operation,
                    "format": format_handler,
                    "path": str(path)
                }

            return result

        except Exception as e:
            self.logger.error(f"File operation failed: {str(e)}")
            raise RuntimeError(f"File operation failed: {str(e)}")

    def __str__(self) -> str:
        """String representation"""
        return f"{self.name}: {self.description}"
