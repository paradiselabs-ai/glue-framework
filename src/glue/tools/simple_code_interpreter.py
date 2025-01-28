
# src/glue/tools/simple_code_interpreter.py

"""Simplified Code Interpreter Tool"""

import os
import sys
import asyncio
import tempfile
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .simple_base import SimpleBaseTool
from ..core.state import ResourceState

@dataclass
class CodeResult:
    """Result from code execution"""
    output: str
    error: Optional[str] = None
    files: List[str] = None

    def __post_init__(self):
        if self.files is None:
            self.files = []

class SimpleCodeInterpreterTool(SimpleBaseTool):
    """
    Simplified code interpreter tool.
    
    Features:
    - Simple state management (IDLE/ACTIVE)
    - Basic code execution
    - Workspace management
    """
    
    def __init__(
        self,
        name: str = "code_interpreter",
        description: str = "Executes code in a sandboxed environment",
        workspace_dir: Optional[str] = None,
        supported_languages: Optional[List[str]] = None,
        **kwargs
    ):
        super().__init__(
            name=name,
            description=description,
            **kwargs
        )
        
        self.workspace_dir = workspace_dir or tempfile.mkdtemp()
        self.supported_languages = supported_languages or ["python"]
        
        # Ensure workspace exists
        os.makedirs(self.workspace_dir, exist_ok=True)
    
    async def _execute(self, code: str, language: str = "python", **kwargs) -> CodeResult:
        """Execute code in specified language"""
        if language not in self.supported_languages:
            return CodeResult(
                output="",
                error=f"Language {language} not supported. Supported languages: {', '.join(self.supported_languages)}"
            )
        
        # Create temp file
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix=f'.{language}',
            dir=self.workspace_dir,
            delete=False
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            # Execute code
            if language == "python":
                # Capture output
                output = []
                error = []
                
                # Create process
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    temp_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.workspace_dir
                )
                
                # Wait for completion
                stdout, stderr = await process.communicate()
                
                # Process output
                if stdout:
                    output.append(stdout.decode())
                if stderr:
                    error.append(stderr.decode())
                
                return CodeResult(
                    output="\n".join(output),
                    error="\n".join(error) if error else None,
                    files=[temp_file]
                )
            else:
                return CodeResult(
                    output="",
                    error=f"Execution of {language} not implemented"
                )
                
        except Exception as e:
            return CodeResult(
                output="",
                error=str(e)
            )
            
        finally:
            # Cleanup temp file
            try:
                os.unlink(temp_file)
            except:
                pass
    
    async def cleanup(self) -> None:
        """Clean up resources"""
        # Clean workspace if using temp dir
        if self.workspace_dir and self.workspace_dir.startswith(tempfile.gettempdir()):
            try:
                for root, dirs, files in os.walk(self.workspace_dir, topdown=False):
                    for name in files:
                        os.remove(os.path.join(root, name))
                    for name in dirs:
                        os.rmdir(os.path.join(root, name))
                os.rmdir(self.workspace_dir)
            except:
                pass
        
        await super().cleanup()
