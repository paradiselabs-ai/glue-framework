# src/glue/tools/file_handler.py

# ==================== Imports ====================
from typing import Any, Dict, List, Optional, Union
import os
import json
import yaml
import csv
import re
import asyncio
from pathlib import Path
from .base import ToolConfig, ToolPermission
from .magnetic import MagneticTool
from ..core.logger import get_logger

# ==================== Constants ====================
SUPPORTED_FORMATS = {
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".csv": "csv",
    ".py": "text",     # Added Python support as text
    ".js": "text",     # Added JavaScript support as text
    ".html": "text",   # Added HTML support as text
    ".css": "text",    # Added CSS support as text
    ".md": "text"      # Added Markdown support as text
}

DEFAULT_FORMAT = ".md"  # Default to markdown

# ==================== File Handler Tool ====================
class FileHandlerTool(MagneticTool):
    """Tool for handling file operations with magnetic capabilities"""
    
    def __init__(
        self,
        name: str = "file_handler",
        description: str = "Handles file operations with format support",
        base_path: Optional[str] = None,
        allowed_formats: Optional[List[str]] = None,
        magnetic: bool = True,
        sticky: bool = False,
        workspace_dir: Optional[str] = None
    ):
        super().__init__(
            name=name,
            description=description,
            magnetic=magnetic,
            sticky=sticky,
            shared_resources=["file_content", "file_path", "file_format"],
            config=ToolConfig(
                required_permissions=[
                    ToolPermission.FILE_SYSTEM,
                    ToolPermission.READ,
                    ToolPermission.WRITE,
                    ToolPermission.MAGNETIC
                ],
                cache_results=False
            )
        )
        # Use workspace_dir if provided, otherwise use base_path or cwd
        self.base_path = os.path.abspath(workspace_dir or base_path or os.getcwd())
        self.allowed_formats = (
            {fmt: SUPPORTED_FORMATS[fmt] 
             for fmt in allowed_formats if fmt in SUPPORTED_FORMATS}
            if allowed_formats
            else SUPPORTED_FORMATS
        )
        self.logger = get_logger()
        self.logger.debug(f"Initialized file handler with base_path: {self.base_path}")
        # Track pending write tasks
        self._pending_writes: List[asyncio.Task] = []

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
            file_path = f"{file_path}{DEFAULT_FORMAT}"
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
        
        # Check if path is within base directory
        if not abs_path.startswith(base_path):
            # Try treating the path as relative to base_path
            alt_path = os.path.join(base_path, os.path.basename(file_path))
            abs_path = os.path.abspath(os.path.realpath(alt_path))
            self.logger.debug(f"Tried alternate path: {abs_path}")
            if not abs_path.startswith(base_path):
                raise ValueError(
                    f"Access denied: {file_path} is outside base directory"
                )

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

    def _infer_operation(self, content: str) -> tuple[str, str, Optional[str]]:
        """Infer operation type and file path from natural language input"""
        self.logger.debug(f"Inferring operation from content: {content}")
        
        # Check if content looks like a document (has title and content)
        has_title = bool(re.search(r'^Title:', content, re.MULTILINE | re.IGNORECASE))
        has_content = len(content.split('\n')) > 2  # More than just title and blank line
        
        # Extract file path and format hints
        file_path = None
        format_hint = None
        
        # Look for format hints like "as markdown" or "in json"
        format_match = re.search(r'(?:as|in|to)\s+(\w+)', content.lower())
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
        for word in content.lower().split():
            if '/' in word or any(word.endswith(ext) for ext in SUPPORTED_FORMATS):
                file_path = word
                self.logger.debug(f"Found explicit file path: {file_path}")
                break
        
        # Extract topic for filename if no explicit path
        if not file_path:
            topic = self._extract_topic(content)
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
        if any(word in content.lower() for word in ["save", "write", "create"]):
            # Explicit save/write/create operation
            return "write", file_path, content
        elif has_title and has_content:
            # If content looks like a document, it's a write operation
            self.logger.debug("Content looks like a document, using write operation")
            return "write", file_path, content
        elif any(word in content.lower() for word in ["append", "add to"]):
            return "append", file_path, content
        elif any(word in content.lower() for word in ["delete", "remove"]):
            return "delete", file_path, None
        elif any(word in content.lower() for word in ["read", "show", "get", "what"]):
            # Only read if explicitly requested
            return "read", file_path, None
        else:
            # Default to write for research summaries and other content
            return "write", file_path, content

    async def execute(self, content: str, **kwargs) -> Dict[str, Any]:
        """Execute file operation based on natural language input"""
        self.logger.debug(f"Executing with content: {content}")
        
        # Infer operation and file path from content
        operation, file_path, operation_content = self._infer_operation(content)
        self.logger.debug(f"Inferred operation: {operation}, path: {file_path}")
        
        path = self._validate_path(file_path)
        self.logger.debug(f"Validated path: {path}")
        
        format_handler = self._get_format_handler(path)
        self.logger.debug(f"Using format handler: {format_handler}")

        try:
            result = None
            if operation == "read":
                result = await self._read_file(path, format_handler)
                # Share the file content magnetically
                if self.magnetic:
                    await self.share_resource("file_content", result["content"])
                    await self.share_resource("file_path", str(path))
                    await self.share_resource("file_format", format_handler)
            elif operation == "write":
                result = await self._write_file(
                    path, operation_content, format_handler, mode='w'
                )
            elif operation == "append":
                result = await self._write_file(
                    path, operation_content, format_handler, mode='a'
                )
            elif operation == "delete":
                result = await self._delete_file(path)

            return result

        except Exception as e:
            self.logger.error(f"File operation failed: {str(e)}")
            raise RuntimeError(f"File operation failed: {str(e)}")

    async def _read_file(
        self,
        path: Path,
        format_handler: str
    ) -> Dict[str, Any]:
        """Read file content based on format"""
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

        return {
            "success": True,
            "operation": "read",
            "format": format_handler,
            "content": content,
            "path": str(path)
        }

    async def _write_file(
        self,
        path: Path,
        content: Any,
        format_handler: str,
        mode: str
    ) -> Dict[str, Any]:
        """Write content to file based on format"""
        os.makedirs(path.parent, exist_ok=True)

        if format_handler == "csv" and not isinstance(content, list):
            raise ValueError("CSV content must be a list of dictionaries")

        with open(path, mode) as f:
            if format_handler == "text":
                f.write(str(content))
            elif format_handler == "json":
                json.dump(content, f, indent=2)
            elif format_handler == "yaml":
                yaml.safe_dump(content, f)
            elif format_handler == "csv":
                writer = csv.DictWriter(f, fieldnames=content[0].keys())
                if mode == 'w':
                    writer.writeheader()
                writer.writerows(content)

        # Share the updated file content magnetically
        if self.magnetic:
            await self.share_resource("file_content", content)
            await self.share_resource("file_path", str(path))
            await self.share_resource("file_format", format_handler)

        return {
            "success": True,
            "operation": mode == 'w' and "write" or "append",
            "format": format_handler,
            "path": str(path)
        }

    async def _delete_file(self, path: Path) -> Dict[str, Any]:
        """Delete file"""
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        os.remove(path)
        return {
            "success": True,
            "operation": "delete",
            "path": str(path)
        }

    async def _on_resource_shared(self, source: 'MagneticTool', resource_name: str, data: Any) -> None:
        """Handle shared resources from other tools"""
        # Only process resources shared by models, not other tools
        if not hasattr(source, 'role'):  # Models have 'role' attribute, tools don't
            self.logger.debug(f"Ignoring resource from non-model source: {source.name}")
            return
            
        # Process content from model
        if resource_name == "file_content":
            if isinstance(data, str):
                # Extract topic from content if possible
                topic = self._extract_topic(data)
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
                        heading_match = re.search(r'### \d+\.\s*(.+?)\n', data)
                        if heading_match:
                            first_result = heading_match.group(1).strip()
                            topic = re.sub(r'[^\w\s-]', '', first_result)
                            topic = re.sub(r'[-\s]+', '_', topic)
                            topic = topic.strip('_').lower()
                
                # Use topic or default name
                filename = f"{topic or 'document'}.md"
                path = self._validate_path(filename)
                await self._write_file(path, data, "text", mode='w')

    async def cleanup(self) -> None:
        """Clean up resources when tool is done"""
        # Wait for any pending write operations to complete
        if self._pending_writes:
            await asyncio.gather(*self._pending_writes)
        await super().cleanup()

    def __str__(self) -> str:
        formats = ", ".join(self.allowed_formats.keys())
        status = []
        if self.magnetic:
            status.append("Magnetic")
            if self.shared_resources:
                status.append(f"Shares: {', '.join(self.shared_resources)}")
            if self.sticky:
                status.append("Sticky")
        return (
            f"{self.name}: {self.description} "
            f"(Formats: {formats}"
            f"{' - ' + ', '.join(status) if status else ''})"
        )
