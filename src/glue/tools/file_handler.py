"""File Handler Tool Implementation"""

from typing import Any, Dict, List, Optional, Union, Tuple, Literal
import os
import json
import yaml
import csv
import re
import asyncio
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field
from prefect import task, flow
from smolagents.tools import Tool, AUTHORIZED_TYPES
from smolagents.agents import ToolCallingAgent
from .base import BaseTool, ToolConfig, ToolPermission
from ..core.types import AdhesiveType
from ..core.logger import get_logger
from ..core.tool_binding import ToolBinding

# ==================== Constants ====================
class FileFormat(str, Enum):
    """Supported file formats"""
    TEXT = "text"
    JSON = "json"
    YAML = "yaml"
    CSV = "csv"

class FileOperation(str, Enum):
    """Supported file operations"""
    READ = "read"
    WRITE = "write"
    APPEND = "append"
    DELETE = "delete"

class FileFormats:
    """File format mappings and defaults"""
    FORMATS = {
        ".txt": FileFormat.TEXT,
        ".json": FileFormat.JSON,
        ".yaml": FileFormat.YAML,
        ".yml": FileFormat.YAML,
        ".csv": FileFormat.CSV,
        ".py": FileFormat.TEXT,     # Python support as text
        ".js": FileFormat.TEXT,     # JavaScript support as text
        ".html": FileFormat.TEXT,   # HTML support as text
        ".css": FileFormat.TEXT,    # CSS support as text
        ".md": FileFormat.TEXT      # Markdown support as text
    }
    
    DEFAULT = ".md"  # Default to markdown
    OPERATIONS = {op.value for op in FileOperation}

# ==================== Pydantic Models ====================
class FileHandlerConfig(BaseModel):
    """Configuration for file handler tool"""
    workspace_dir: Optional[str] = Field(None, description="Working directory for file operations")
    base_path: Optional[str] = Field(None, description="Base path for file operations")
    allowed_formats: Optional[List[str]] = Field(None, description="List of allowed file formats")
    shared_resources: List[str] = Field(
        default=["file_content", "file_path", "file_format"],
        description="Resources that can be shared with other tools"
    )

class FileOperationInput(BaseModel):
    """Input schema for file operations"""
    action: FileOperation = Field(..., description="The action to perform")
    path: str = Field(..., description="Path to the file")
    content: Optional[str] = Field(None, description="Content for write/append operations")

class FileOperationResult(BaseModel):
    """Result schema for file operations"""
    success: bool = Field(..., description="Whether the operation succeeded")
    operation: FileOperation = Field(..., description="The operation performed")
    format: Optional[FileFormat] = Field(None, description="Format of the file")
    path: str = Field(..., description="Path to the file")
    content: Optional[Any] = Field(None, description="File content for read operations")

# ==================== File Handler Tool ====================
class FileHandlerTool(BaseTool):
    """Tool for handling file operations with Prefect orchestration and Pydantic validation"""
    
    # SmolAgents interface
    name = "file_handler"
    description = "Handles file operations with format support"
    skip_forward_signature_validation = True  # Using Prefect flows
    inputs = {
        "action": {
            "type": "string",
            "description": "The action to perform (read/write/append/delete)",
            "enum": list(FileFormats.OPERATIONS)
        },
        "path": {
            "type": "string",
            "description": "Path to the file"
        },
        "content": {
            "type": "string",
            "description": "Content to write (for write/append actions)",
            "nullable": True,
            "optional": True,
            "default": None
        }
    }
    output_type = "string"
    
    # GLUE interface
    tool_name = "file_handler"
    tool_description = "Handles file operations with format support"

    def __init__(
        self,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        base_path: Optional[str] = None,
        allowed_formats: Optional[List[str]] = None,
        workspace_dir: Optional[str] = None,
        binding_type: Optional[AdhesiveType] = None,
        shared_resources: Optional[List[str]] = None,
        **kwargs
    ):
        # Initialize GLUE tool config with Pydantic validation
        file_config = FileHandlerConfig(
            workspace_dir=workspace_dir,
            base_path=base_path,
            allowed_formats=allowed_formats,
            shared_resources=shared_resources or ["file_content", "file_path", "file_format"]
        )
        
        # Create tool config if not provided
        if not config:
            config = {
                "required_permissions": [
                    ToolPermission.FILE_SYSTEM,  # For workspace access
                    ToolPermission.READ,         # For reading files
                    ToolPermission.WRITE         # For writing files
                ],
                "tool_specific_config": file_config.model_dump()
            }
        
        # Initialize base tool with config
        super().__init__(name=name, config=config)
        self.adhesive_type = binding_type or AdhesiveType.VELCRO
        self.tags = {"file_handler", "io", "filesystem"}
        
        # Initialize configuration
        config = self.config.tool_specific_config
        self.base_path = os.path.abspath(
            config["workspace_dir"] or 
            config["base_path"] or 
            os.getcwd()
        )
        self.allowed_formats = (
            {fmt: FileFormats.FORMATS[fmt] 
             for fmt in config["allowed_formats"] if fmt in FileFormats.FORMATS}
            if config["allowed_formats"]
            else FileFormats.FORMATS
        )
        
        # Initialize logger and binding
        self.logger = get_logger(self.name)
        self.logger.debug(f"Initialized file handler with base_path: {self.base_path}")
        self.binding = ToolBinding(self)

    async def _validate_input(self, *args, **kwargs) -> bool:
        """Validate tool input"""
        content = args[0] if args else kwargs
        
        # Handle string input
        if isinstance(content, str):
            return bool(content.strip())
            
        # Handle dictionary input
        if isinstance(content, dict):
            # Must have either content or operation
            if not (content.get('content') or content.get('operation')):
                return False
            # If operation specified, must be valid
            if 'operation' in content and content['operation'] not in FileFormats.OPERATIONS:
                return False
            return True
            
        # Handle list input (for CSV data)
        if isinstance(content, list):
            return bool(content) and all(isinstance(item, dict) for item in content)
            
        return False

    def _validate_path(self, file_path: str) -> Path:
        """Validate and resolve file path"""
        self.logger.debug(f"Validating path: {file_path}")
        
        # Skip URLs - they should be handled by web_search
        # Common URL patterns
        url_patterns = [
            'http://', 'https://',  # Standard protocols
            'www.', '.com', '.org', '.edu', '.gov', '.net',  # Common domains
            '.asp', '.php', '.html?', '?'  # Common web extensions and query strings
        ]
        if any(pattern in file_path.lower() for pattern in url_patterns):
            raise ValueError("Cannot handle URLs directly. Use web_search tool instead.")
        
        # Clean up path (remove quotes, extra spaces, leading slashes)
        file_path = file_path.strip(' "\'/')
        self.logger.debug(f"Cleaned path: {file_path}")
        
        # If path starts with base_path directory name, remove it
        base_dir = os.path.basename(self.base_path)
        if file_path.startswith(f"{base_dir}/"):
            file_path = file_path[len(base_dir)+1:]
            self.logger.debug(f"Removed base dir: {file_path}")
        
        # Add default extension if no extension present
        if not os.path.splitext(file_path)[1]:
            file_path = f"{file_path}{FileFormats.DEFAULT}"
            self.logger.debug(f"Added default extension: {file_path}")
        
        # Convert to absolute path if relative
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.base_path, file_path)
            self.logger.debug(f"Converted to absolute path: {file_path}")
        
        # Resolve to absolute path, following symlinks
        abs_path = os.path.abspath(os.path.realpath(file_path))
        base_path = os.path.abspath(os.path.realpath(self.base_path))
        self.logger.debug(f"Resolved absolute path: {abs_path}")
        self.logger.debug(f"Base path: {base_path}")
        
        # Check if path attempts to traverse outside base directory
        if '..' in file_path:
            raise ValueError(f"Access denied: {file_path} attempts to traverse outside base directory")
            
        # Check if path is within base directory
        if not abs_path.startswith(base_path):
            # If path is absolute and starts with /tmp or /var/folders, allow it (for tests)
            if file_path.startswith(('/tmp/', '/var/folders/')):
                abs_path = os.path.abspath(os.path.realpath(file_path))
                self.logger.debug(f"Allowing temp directory path: {abs_path}")
            else:
                # Try treating the path as relative to base_path
                alt_path = os.path.join(base_path, os.path.basename(file_path))
                abs_path = os.path.abspath(os.path.realpath(alt_path))
                self.logger.debug(f"Tried alternate path: {abs_path}")
                if not abs_path.startswith(base_path):
                    raise ValueError(f"Access denied: {file_path} is outside base directory")

        return Path(abs_path)

    def _get_format_handler(self, file_path: Path) -> str:
        """Get appropriate format handler for file"""
        suffix = file_path.suffix.lower()
        self.logger.debug(f"Getting format handler for suffix: {suffix}")
        if suffix not in self.allowed_formats:
            raise ValueError(
                f"Unsupported format: {suffix}. "
                f"Supported: {list(self.allowed_formats.keys())}"
            )
        return self.allowed_formats[suffix]

    def _extract_topic(self, content: str) -> Optional[str]:
        """Extract topic from content for filename"""
        # Look for title
        title_match = re.search(r'^Title:\s*(.+?)(?:\n|$)', content, re.MULTILINE | re.IGNORECASE)
        if title_match:
            topic = title_match.group(1).strip()
            self.logger.debug(f"Found title: {topic}")
            return topic
        
        # Look for topic after keywords
        topic_match = re.search(r'(?:research|summary)\s+(?:on|about)?\s*(.+?)(?:\s+and|\s*[.?!]|$)', content)
        if topic_match:
            topic = topic_match.group(1).strip()
            self.logger.debug(f"Found topic: {topic}")
            return topic
        
        # Look for first heading after Research Results
        heading_match = re.search(r'^# Research Results: (.+?)\n.*?### \d+\.\s*(.+?)\n', content, re.DOTALL)
        if heading_match:
            query = heading_match.group(1).strip()
            first_result = heading_match.group(2).strip()
            # Use query if it's specific, otherwise use first result title
            topic = query if len(query.split()) > 2 else first_result
            self.logger.debug(f"Found heading topic: {topic}")
            return topic
        
        return None

    def _infer_operation(self, content: Union[str, Dict[str, Any], List[Dict[str, Any]]]) -> Tuple[str, str, Optional[str]]:
        """Infer operation type and file path from natural language input"""
        self.logger.debug(f"Inferring operation from content: {content}")
        
        # Handle dictionary input
        if isinstance(content, dict):
            file_path = content.get('file_path', content.get('path', 'document'))
            operation = content.get('operation', 'write')
            content_str = content.get('content', '')
            
            # Validate operation
            if operation not in FileFormats.OPERATIONS:
                raise ValueError(f"Invalid operation: {operation}")
            
            return operation, file_path, content_str
        
        # Handle list input (for CSV data)
        if isinstance(content, list):
            return "write", "data.csv", content
        
        # Handle string input
        content_str = str(content)
        # Check if content looks like a document (has title and content)
        has_title = bool(re.search(r'^Title:', content_str, re.MULTILINE | re.IGNORECASE))
        has_content = len(content_str.split('\n')) > 2  # More than just title and blank line
        
        # Extract file path and format hints
        file_path = None
        format_hint = None
        
        # Look for format hints like "as markdown" or "in json"
        format_match = re.search(r'(?:as|in|to)\s+(\w+)', content_str.lower())
        if format_match:
            format_name = format_match.group(1)
            # Map common format names to extensions
            format_map = {
                'markdown': '.md',
                'md': '.md',
                'json': '.json',
                'yaml': '.yaml',
                'yml': '.yml',
                'csv': '.csv',
                'text': '.txt',
                'txt': '.txt',
                'python': '.py',
                'py': '.py',
                'javascript': '.js',
                'js': '.js',
                'html': '.html',
                'css': '.css'
            }
            format_hint = format_map.get(format_name)
            self.logger.debug(f"Found format hint: {format_hint}")
        
        # Look for explicit file path (must contain slash or valid extension)
        for word in content_str.lower().split():
            if '/' in word or any(word.endswith(ext) for ext in FileFormats.FORMATS):
                file_path = word
                self.logger.debug(f"Found explicit file path: {file_path}")
                break
        
        # Extract topic for filename if no explicit path
        if not file_path:
            topic = self._extract_topic(content_str)
            if topic:
                # Convert to snake case
                topic = re.sub(r'[^\w\s-]', '', topic)  # Remove special chars
                topic = re.sub(r'[-\s]+', '_', topic)   # Replace spaces/hyphens with underscore
                topic = topic.strip('_').lower()        # Clean up and lowercase
                self.logger.debug(f"Converted topic to filename: {topic}")
                file_path = topic
        
        # If still no path, use default
        if not file_path:
            file_path = "document"
            self.logger.debug("Using default filename: document")
        
        # Add format extension if specified
        if format_hint:
            file_path = f"{file_path}{format_hint}"
            self.logger.debug(f"Added format extension: {file_path}")
        
        # Determine operation
        if any(word in content_str.lower() for word in ["save", "write", "create"]):
            # Explicit save/write/create operation
            return "write", file_path, content_str
        elif has_title and has_content:
            # If content looks like a document, it's a write operation
            self.logger.debug("Content looks like a document, using write operation")
            return "write", file_path, content_str
        elif any(word in content_str.lower() for word in ["append", "add to"]):
            return "append", file_path, content_str
        elif any(word in content_str.lower() for word in ["delete", "remove"]):
            return "delete", file_path, None
        elif any(word in content_str.lower() for word in ["read", "show", "get", "what"]):
            # Only read if explicitly requested
            return "read", file_path, None
        else:
            # Default to write for research summaries and other content
            return "write", file_path, content_str

    @task(name="validate_operation", retries=2)
    async def _validate_operation(
        self,
        action: str,
        path: str,
        content: Optional[str] = None
    ) -> Tuple[FileOperationInput, Path, str]:
        """Validate operation inputs with Prefect task"""
        # Validate input using Pydantic
        operation_input = FileOperationInput(
            action=FileOperation(action),
            path=path,
            content=content
        )
        self.logger.debug(f"Validating operation: {operation_input.model_dump_json()}")
        
        # Validate and resolve path
        validated_path = self._validate_path(operation_input.path)
        format_handler = self._get_format_handler(validated_path)
        
        return operation_input, validated_path, format_handler

    @task(name="execute_operation", retries=3, retry_delay_seconds=1)
    async def _execute_operation(
        self,
        operation_input: FileOperationInput,
        validated_path: Path,
        format_handler: str
    ) -> FileOperationResult:
        """Execute file operation with Prefect task"""
        # Store operation details in binding
        self.binding.store_resource("operation", operation_input.action.value)
        self.binding.store_resource("file_path", str(validated_path))
        self.binding.store_resource("format", format_handler)
        
        # Execute operation
        result = None
        if operation_input.action == FileOperation.READ:
            result = await self._read_file(validated_path, format_handler)
            self.binding.store_resource("file_content", result.content)
        elif operation_input.action == FileOperation.WRITE:
            result = await self._write_file(validated_path, operation_input.content, format_handler, mode='w')
        elif operation_input.action == FileOperation.APPEND:
            result = await self._write_file(validated_path, operation_input.content, format_handler, mode='a')
        elif operation_input.action == FileOperation.DELETE:
            result = await self._delete_file(validated_path)
            
        return result

    @flow(
        name="file_handler_flow",
        description="Execute file operations with validation and retries",
        retries=3,
        retry_delay_seconds=1,
        persist_result=True,
        version="1.0.0"
    )
    async def forward(self, action: str, path: str, content: Optional[str] = None) -> str:
        """Execute file operation as a Prefect flow"""
        try:
            # Validate operation
            operation_input, validated_path, format_handler = await self._validate_operation(
                action=action,
                path=path,
                content=content
            )
            
            # Execute operation
            result = await self._execute_operation(
                operation_input=operation_input,
                validated_path=validated_path,
                format_handler=format_handler
            )

            # Convert result to string as required by SmolAgents
            if result:
                if operation_input.action == FileOperation.READ:
                    return str(result.content)
                else:
                    return f"Successfully {operation_input.action.value}d file: {operation_input.path}"
            return "Operation completed successfully"

        except Exception as e:
            self.logger.error(f"File operation failed: {str(e)}")
            if isinstance(e, (ValueError, FileNotFoundError)):
                raise e
            raise RuntimeError(f"File operation failed: {str(e)}")

    async def _read_file(
        self,
        path: Path,
        format_handler: FileFormat
    ) -> FileOperationResult:
        """Read file content based on format"""
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(path, 'r') as f:
            if format_handler == FileFormat.TEXT:
                content = f.read()
            elif format_handler == FileFormat.JSON:
                content = json.load(f)
            elif format_handler == FileFormat.YAML:
                content = yaml.safe_load(f)
            elif format_handler == FileFormat.CSV:
                content = list(csv.DictReader(f))

        result = FileOperationResult(
            success=True,
            operation=FileOperation.READ,
            format=format_handler,
            path=str(path),
            content=content
        )

        # Store content in binding
        self.binding.store_resource("file_content", content)
        self.binding.store_resource("file_path", str(path))
        self.binding.store_resource("file_format", format_handler)

        return result

    async def _write_file(
        self,
        path: Path,
        content: Any,
        format_handler: FileFormat,
        mode: str
    ) -> FileOperationResult:
        """Write content to file based on format"""
        os.makedirs(path.parent, exist_ok=True)

        if format_handler == FileFormat.CSV and not isinstance(content, list):
            raise ValueError("CSV content must be a list of dictionaries")

        with open(path, mode) as f:
            if format_handler == FileFormat.TEXT:
                f.write(str(content))
            elif format_handler == FileFormat.JSON:
                json.dump(content, f, indent=2)
            elif format_handler == FileFormat.YAML:
                yaml.safe_dump(content, f)
            elif format_handler == FileFormat.CSV:
                writer = csv.DictWriter(f, fieldnames=content[0].keys())
                if mode == 'w':
                    writer.writeheader()
                writer.writerows(content)

        # Store the updated file content in binding
        self.binding.store_resource("file_content", content)
        self.binding.store_resource("file_path", str(path))
        self.binding.store_resource("file_format", format_handler)

        return FileOperationResult(
            success=True,
            operation=FileOperation.WRITE if mode == 'w' else FileOperation.APPEND,
            format=format_handler,
            path=str(path),
            content=content
        )

    async def _delete_file(self, path: Path) -> FileOperationResult:
        """Delete file"""
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        os.remove(path)
        return FileOperationResult(
            success=True,
            operation=FileOperation.DELETE,
            path=str(path)
        )

    async def process_shared_content(self, content: str) -> Optional[FileOperationResult]:
        """Process shared content from other tools"""
        if not isinstance(content, str):
            self.logger.warning(f"Received non-string content: {type(content)}")
            return None

        try:
            # Extract topic from content if possible
            topic = self._extract_topic(content)
            if topic:
                # Convert to snake case
                topic = re.sub(r'[^\w\s-]', '', topic)  # Remove special chars
                topic = re.sub(r'[-\s]+', '_', topic)   # Replace spaces/hyphens with underscore
                topic = topic.strip('_').lower()        # Clean up and lowercase
                
                # Clean up common words that make bad filenames
                topic = re.sub(r'\b(the|a|an|in|on|at|to|for|of|with|by|from)\b', '', topic)
                topic = re.sub(r'\s+', '_', topic.strip())
                
                # If topic is too generic, try to get first result title
                if len(topic.split('_')) < 2:
                    heading_match = re.search(r'### \d+\.\s*(.+?)\n', content)
                    if heading_match:
                        first_result = heading_match.group(1).strip()
                        topic = re.sub(r'[^\w\s-]', '', first_result)
                        topic = re.sub(r'[-\s]+', '_', topic)
                        topic = topic.strip('_').lower()
            
            # Create operation input with validated data
            operation_input = FileOperationInput(
                action=FileOperation.WRITE,
                path=f"{topic or 'document'}.md",
                content=content
            )
            
            # Validate path and get format
            validated_path = self._validate_path(operation_input.path)
            format_handler = self._get_format_handler(validated_path)
            
            # Execute write operation
            result = await self._write_file(
                validated_path,
                operation_input.content,
                format_handler,
                mode='w'
            )
            
            self.logger.debug(f"Successfully processed shared content to {result.path}")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to process shared content: {str(e)}")
            raise RuntimeError(f"Failed to process shared content: {str(e)}")

    async def cleanup(self) -> None:
        """Clean up resources when tool is done"""
        await super().cleanup()

    def __str__(self) -> str:
        """String representation"""
        return f"{self.name}: {self.description} (Binding: {self.binding.type.name})"
