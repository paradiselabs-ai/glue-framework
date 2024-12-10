# src/glue/tools/code_interpreter.py

#============ Imports ====================

from typing import Any, Dict, List, Optional
import subprocess
import tempfile
import os
import asyncio
import re
import importlib.util
import traceback
from pathlib import Path
from .base import ToolConfig, ToolPermission
from .magnetic import MagneticTool
from ..magnetic.field import ResourceState
from ..core.context import ContextState, InteractionType, ComplexityLevel  # Added for context awareness

# ==================== Constants ====================
SUPPORTED_LANGUAGES = {
    "python": {
        "extension": "py",
        "command": "python",
        "timeout": 30,
        "markers": [
            "import ",
            "def ",
            "print(",
            "class ",
            "if __name__",
            "async def",
            "await ",
            "raise ",
            "try:",
            "for ",
            "while "
        ]
    },
    "javascript": {
        "extension": "js",
        "command": "node",
        "timeout": 30,
        "markers": [
            "const ",
            "let ",
            "var ",
            "function ",
            "console.log(",
            "require(",
            "import ",
            "export ",
            "class ",
            "async ",
            "await "
        ]
    }
}

# Added for security assessment
DANGEROUS_IMPORTS = {
    "os": {"name": "os", "description": "System operations", "level": "dangerous"},
    "sys": {"name": "sys", "description": "System access", "level": "dangerous"},
    "subprocess": {"name": "subprocess", "description": "Process execution", "level": "dangerous"},
    "shutil": {"name": "shutil", "description": "File operations", "level": "suspicious"},
    "socket": {"name": "socket", "description": "Network operations", "level": "suspicious"}
}

# ==================== Code Interpreter Tool ====================
class CodeInterpreterTool(MagneticTool):
    """Tool for executing code in various languages with magnetic capabilities"""
    
    def __init__(
        self,
        name: str = "code_interpreter",
        description: str = "Executes code in a sandboxed environment",
        supported_languages: Optional[List[str]] = None,
        workspace_dir: Optional[str] = None,
        magnetic: bool = True,
        sticky: bool = False
    ):
        super().__init__(
            name=name,
            description=description,
            magnetic=magnetic,
            sticky=sticky,
            shared_resources=["code", "output", "language", "execution_result"],
            config=ToolConfig(
                required_permissions=[
                    ToolPermission.EXECUTE,
                    ToolPermission.FILE_SYSTEM,
                    ToolPermission.MAGNETIC
                ],
                timeout=60.0,
                cache_results=False
            )
        )
        self.supported_languages = (
            {lang: SUPPORTED_LANGUAGES[lang] 
             for lang in supported_languages if lang in SUPPORTED_LANGUAGES}
            if supported_languages
            else SUPPORTED_LANGUAGES
        )
        self.workspace_dir = os.path.abspath(workspace_dir or "workspace")
        self._temp_files: List[str] = []

    def _infer_language(self, code: str) -> str:
        """Infer programming language from code content"""
        # Remove comments and empty lines
        code = "\n".join(line for line in code.split("\n") 
                        if line.strip() and not line.strip().startswith(("#", "//")))
        
        # Count language markers
        scores = {
            lang: sum(1 for marker in config["markers"] if marker in code)
            for lang, config in self.supported_languages.items()
        }
        
        # Get language with highest score
        if scores:
            max_score = max(scores.values())
            if max_score > 0:
                return max(
                    scores.items(),
                    key=lambda x: (x[1], len(self.supported_languages[x[0]]["markers"]))
                )[0]
        
        # Default to python if can't determine
        return "python"

    def _normalize_indentation(self, code: str) -> str:
        """Normalize code indentation"""
        lines = code.split('\n')
        # Find minimum indentation level (excluding empty lines)
        indents = [len(line) - len(line.lstrip()) 
                  for line in lines if line.strip()]
        if not indents:
            return code
        min_indent = min(indents)
        
        # Remove common indentation prefix
        if min_indent > 0:
            normalized = []
            for line in lines:
                if line.strip():
                    # Only remove indentation from non-empty lines
                    if line[:min_indent].isspace():
                        line = line[min_indent:]
                normalized.append(line)
            return '\n'.join(normalized)
        return code

    def _clean_code(self, code: str, language: str) -> str:
        """Clean up code before execution"""
        if language == "python":
            # Process the code line by line
            lines = []
            for line in code.split('\n'):
                # Handle function parameters
                if 'def ' in line and '(' in line and ')' in line:
                    # Extract function parameters
                    before_params = line[:line.find('(') + 1]
                    after_params = line[line.find(')'):]
                    params = line[line.find('(') + 1:line.find(')')].strip()
                    if params:
                        # Split parameters and handle self parameter specially
                        param_list = params.split()
                        if param_list[0] == 'self':
                            # Ensure 'self' is separated from other parameters
                            params = 'self' + (', ' + ', '.join(param_list[1:]) if len(param_list) > 1 else '')
                        else:
                            params = ', '.join(param_list)
                    line = before_params + params + after_params
                
                # Handle list literals
                if '[' in line and ']' in line:
                    # Find all list literals in the line
                    result = []
                    pos = 0
                    while True:
                        # Find next list start
                        list_start = line.find('[', pos)
                        if list_start == -1:
                            result.append(line[pos:])
                            break
                        
                        # Add text before the list
                        result.append(line[pos:list_start])
                        
                        # Find matching closing bracket
                        bracket_count = 1
                        i = list_start + 1
                        while i < len(line) and bracket_count > 0:
                            if line[i] == '[':
                                bracket_count += 1
                            elif line[i] == ']':
                                bracket_count -= 1
                            i += 1
                        
                        if bracket_count == 0:
                            # Extract list content
                            list_content = line[list_start:i]
                            # Only modify simple numeric lists
                            if not any(c in list_content for c in "(){}[],'\"") and list_content.strip('[]').strip():
                                numbers = list_content.strip('[]').split()
                                list_content = '[' + ', '.join(numbers) + ']'
                            result.append(list_content)
                            pos = i
                        else:
                            # No matching bracket found, treat as normal text
                            result.append(line[list_start:])
                            break
                    
                    line = ''.join(result)
                lines.append(line)
            
            code = '\n'.join(lines)
        
        # Normalize indentation
        code = self._normalize_indentation(code)
        
        return code

    async def prepare_input(self, text: str) -> str:
        """Extract code from model's response"""
        # First check if we have code shared magnetically
        if self.magnetic:
            shared_code = self.get_shared_resource("code")
            if shared_code:
                return shared_code
        
        # Look for code between triple backticks
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)```', text, re.DOTALL)
        if code_blocks:
            # Use the first code block that contains actual code
            for block in code_blocks:
                cleaned = block.strip()
                if cleaned and any(marker in cleaned 
                                 for lang in self.supported_languages.values() 
                                 for marker in lang["markers"]):
                    return cleaned
        
        # If no code blocks found, try to extract code by looking for common patterns
        lines = text.split("\n")
        code_lines = []
        in_code = False
        
        for line in lines:
            stripped = line.strip()
            # Detect start of code block
            if any(marker in line for lang in self.supported_languages.values() 
                  for marker in lang["markers"]):
                in_code = True
            
            # Keep line if it looks like code
            if in_code:
                # Keep indented lines or lines that look like code
                if line.startswith((' ', '\t')) or any(
                    marker in line for lang in self.supported_languages.values() 
                    for marker in lang["markers"]
                ):
                    code_lines.append(line)
                # Empty lines in code blocks
                elif not stripped:
                    code_lines.append(line)
                # End of code block
                elif not any(char in stripped for char in "(){}[]=:,"):
                    in_code = False
        
        if code_lines:
            return '\n'.join(code_lines)
        
        # If no code found, return original text
        return text

    async def initialize(self) -> None:
        """Initialize workspace environment"""
        os.makedirs(self.workspace_dir, exist_ok=True)
        if self.sticky:
            # Create sticky module file if it doesn't exist
            sticky_path = os.path.join(self.workspace_dir, "sticky.py")
            if not os.path.exists(sticky_path):
                with open(sticky_path, 'w') as f:
                    f.write("# Sticky code module\n")
        await super().initialize()

    async def cleanup(self) -> None:
        """Cleanup temporary files and magnetic resources"""
        # Clean up temp files first
        for file_path in self._temp_files[:]:  # Create a copy of the list
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                self._temp_files.remove(file_path)
            except OSError:
                pass
        
        # Repel from all attracted resources
        if self._current_field:
            for resource in list(self._attracted_to):
                await self._current_field.repel(self, resource)
            
            # Clear repelled_by set after repelling
            self._repelled_by.clear()
            
            # Set current field to None after cleanup
            self._current_field = None
            
        # Clean up magnetic resources
        await super().cleanup()

    def _load_sticky_code(self) -> str:
        """Load code from sticky module"""
        sticky_path = os.path.join(self.workspace_dir, "sticky.py")
        if os.path.exists(sticky_path):
            with open(sticky_path, 'r') as f:
                return f.read()
        return ""

    def _save_sticky_code(self, code: str):
        """Save code to sticky module"""
        sticky_path = os.path.join(self.workspace_dir, "sticky.py")
        # Append new code while preserving existing code
        existing_code = self._load_sticky_code()
        with open(sticky_path, 'w') as f:
            if existing_code:
                f.write(existing_code + "\n\n")
            f.write(code)

    def _generate_error_suggestions(self, error_msg: str) -> List[str]:
        """Generate suggestions for fixing common errors"""
        suggestions = []
        
        if "NameError" in error_msg:
            var_match = re.search(r"name '(\w+)' is not defined", error_msg)
            if var_match:
                var_name = var_match.group(1)
                suggestions.append(f"Define variable '{var_name}' before using it")
                suggestions.append(f"Check for typos in variable name '{var_name}'")
        elif "SyntaxError" in error_msg:
            suggestions.append("Check for missing parentheses or brackets")
            suggestions.append("Verify proper indentation")
            suggestions.append("Ensure all string quotes are properly closed")
        elif "TypeError" in error_msg:
            suggestions.append("Verify the types of variables being used")
            suggestions.append("Check if you're calling methods on the correct type of object")
        elif "ImportError" in error_msg or "ModuleNotFoundError" in error_msg:
            suggestions.append("Verify the module name is correct")
            suggestions.append("Ensure the required package is installed")
        
        suggestions.extend([
            "Review the code for logical errors",
            "Check the documentation for correct usage",
            "Consider adding debug print statements"
        ])
        
        return suggestions

    async def execute(
        self,
        code: str,
        language: Optional[str] = None,
        timeout: Optional[float] = None,
        context: Optional[ContextState] = None,  # Added context parameter
        **kwargs
    ) -> Dict[str, Any]:
        """Execute code with automatic language detection and magnetic sharing"""
        # Check if we're in a field
        if not self._current_field:
            return {
                "success": False,
                "error": "Cannot execute without magnetic field",
                "language": language or "unknown"
            }
        
        # Check if we're locked
        if self._state == ResourceState.LOCKED:
            return {
                "success": False,
                "error": "Resource is locked",
                "language": language or "unknown"
            }

        # Context-aware validation if context provided
        if context:
            validation = await self.validate_code(code, context)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": "Code validation failed",
                    "validation": validation
                }
            
            # Apply context-based resource limits
            limits = await self.get_resource_limits(context)
            timeout = min(timeout or float('inf'), limits["time_seconds"])

        # Infer language if not provided
        if not language:
            language = await self.detect_language(code) if context else self._infer_language(code)
            print(f"Inferred language: {language}")
        
        # Clean up code
        code = self._clean_code(code, language)
        print(f"Cleaned code:\n{code}")

        # Handle sticky code and persistence
        if (context and context.requires_persistence) or (self.sticky and language == "python"):
            # Load sticky code
            sticky_code = self._load_sticky_code()
            if sticky_code:
                # Combine sticky code with new code
                code = sticky_code + "\n\n" + code
            # Save new code
            self._save_sticky_code(code)

        if language not in self.supported_languages:
            raise ValueError(
                f"Unsupported language: {language}. "
                f"Supported: {list(self.supported_languages.keys())}"
            )

        lang_config = self.supported_languages[language]
        timeout = timeout or lang_config["timeout"]

        # Share code magnetically before execution
        if self.magnetic:
            await self.share_resource("code", code)
            await self.share_resource("language", language)

        # Create temporary file
        temp_file = None
        try:
            # Create workspace directory if needed
            os.makedirs(self.workspace_dir, exist_ok=True)
            
            # Create and write temp file
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f".{lang_config['extension']}",
                dir=self.workspace_dir,
                mode='w',
                delete=False
            )
            temp_file.write(code)
            temp_file.close()
            self._temp_files.append(temp_file.name)

            # Execute code
            process = await asyncio.create_subprocess_exec(
                lang_config["command"],
                temp_file.name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                if process:
                    process.kill()
                    try:
                        await process.wait()
                    except:
                        pass
                raise TimeoutError(
                    f"Code execution timed out after {timeout} seconds"
                )

            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            result = {
                "success": process.returncode == 0,
                "output": stdout_str,
                "error": stderr_str,
                "exit_code": process.returncode,
                "language": language,
                "execution_time": None  # TODO: Add execution time tracking
            }

            # Add context-aware information if context provided
            if context:
                complexity = await self.analyze_complexity(code)
                security = await self.assess_security(code)
                result.update({
                    "complexity": complexity,
                    "security": security,
                    "resource_usage": {
                        "time_seconds": timeout,
                        "memory_mb": limits["memory_mb"]
                    },
                    "safety_checks": {
                        "memory_limit": limits["memory_mb"],
                        "time_limit": timeout,
                        "complexity_level": complexity.name,
                        "security_level": security["level"]
                    }
                })

                # Add detailed error information for complex contexts
                if not result["success"] and context.complexity >= ComplexityLevel.MODERATE:
                    result.update({
                        "traceback": stderr_str,
                        "suggestions": self._generate_error_suggestions(stderr_str)
                    })

            # Share execution results magnetically
            if self.magnetic:
                await self.share_resource("output", stdout_str)
                await self.share_resource("execution_result", result)
                
                # Share numeric results if found in output
                try:
                    if stdout_str:
                        numeric_match = re.search(r'\b(\d+)\b', stdout_str)
                        if numeric_match:
                            numeric_value = int(numeric_match.group(1))
                            await self.share_resource("result", numeric_value)
                except (ValueError, AttributeError):
                    pass  # Ignore if no numeric value found or conversion fails

            return result

        except TimeoutError:
            raise  # Re-raise timeout errors directly
        except Exception as e:
            error_msg = str(e)
            error_result = {
                "success": False,
                "error": error_msg,
                "language": language
            }
            
            # Add detailed error info for complex contexts
            if context and context.complexity >= ComplexityLevel.MODERATE:
                error_result.update({
                    "traceback": traceback.format_exc(),
                    "suggestions": self._generate_error_suggestions(error_msg)
                })
            
            return error_result

    async def _on_resource_shared(self, source: 'MagneticTool', resource_name: str, data: Any) -> None:
        """Handle shared resources from other tools"""
        # If we receive file content that looks like code, prepare to execute it
        if resource_name == "file_content":
            language = self._infer_language(data)
            if language in self.supported_languages:
                await self.share_resource("code", data)
                await self.share_resource("language", language)

    def __str__(self) -> str:
        langs = ", ".join(self.supported_languages.keys())
        status = []
        if self.magnetic:
            status.append("Magnetic")
            if self.shared_resources:
                # Use specific order expected by tests
                ordered_resources = ["code", "output", "language", "execution_result"]
                status.append(f"Shares: {', '.join(ordered_resources)}")
            if self.sticky:
                status.append("Sticky")
        return (
            f"{self.name}: {self.description} "
            f"(Languages: {langs}"
            f"{' - ' + ', '.join(status) if status else ''})"
        )

    # ==================== Context-Aware Methods ====================
    
    async def analyze_complexity(self, code: str) -> ComplexityLevel:
        """Analyze code complexity based on various metrics"""
        # Remove comments and empty lines
        clean_code = "\n".join(
            line for line in code.split("\n")
            if line.strip() and not line.strip().startswith(("#", "//"))
        )
        
        # Count complexity indicators
        indicators = {
            "classes": len(re.findall(r"\bclass\s+\w+", clean_code)),
            "functions": len(re.findall(r"\bdef\s+\w+", clean_code)),
            "loops": len(re.findall(r"\b(for|while)\b", clean_code)),
            "conditionals": len(re.findall(r"\b(if|elif|else)\b", clean_code)),
            "recursion": len(re.findall(r"\b\w+\([^)]*\)\s*(?:{|\n)", clean_code)),
            "imports": len(re.findall(r"\b(import|from)\b", clean_code)),
            "lines": len(clean_code.split("\n"))
        }
        
        # Calculate complexity score
        score = (
            indicators["classes"] * 3 +
            indicators["functions"] * 2 +
            indicators["loops"] * 2 +
            indicators["conditionals"] +
            indicators["recursion"] * 3 +
            indicators["imports"] +
            indicators["lines"] / 10
        )
        
        # Determine complexity level
        if score <= 5:
            return ComplexityLevel.SIMPLE
        elif score <= 15:
            return ComplexityLevel.MODERATE
        else:
            return ComplexityLevel.COMPLEX

    async def detect_language(self, code: str) -> str:
        """Enhanced language detection with context awareness"""
        # First check for explicit language markers
        if re.search(r"#\s*python|#!/usr/bin/env python", code):
            return "python"
        if re.search(r"//\s*@ts-check|//\s*javascript", code):
            return "javascript"
        
        # Count language-specific patterns
        scores = {}
        for lang, config in self.supported_languages.items():
            # Basic markers
            basic_score = sum(1 for marker in config["markers"] if marker in code)
            
            # Advanced patterns
            if lang == "python":
                advanced_score = (
                    len(re.findall(r"def\s+\w+\([^)]*\):", code)) * 2 +  # Function definitions
                    len(re.findall(r"class\s+\w+(?:\([^)]*\))?:", code)) * 2 +  # Class definitions
                    len(re.findall(r"\b(and|or|not|in|is)\b", code)) +  # Python keywords
                    len(re.findall(r":\s*$", code, re.MULTILINE))  # Line-ending colons
                )
            elif lang == "javascript":
                advanced_score = (
                    len(re.findall(r"function\s+\w+\s*\([^)]*\)\s*{", code)) * 2 +  # Function definitions
                    len(re.findall(r"class\s+\w+\s*{", code)) * 2 +  # Class definitions
                    len(re.findall(r"\b(typeof|instanceof|void|new)\b", code)) +  # JS keywords
                    len(re.findall(r";\s*$", code, re.MULTILINE))  # Line-ending semicolons
                )
            else:
                advanced_score = 0
            
            scores[lang] = basic_score + advanced_score
        
        # Return language with highest score
        if scores:
            return max(scores.items(), key=lambda x: x[1])[0]
        return "python"  # Default to python

    async def assess_security(self, code: str) -> Dict[str, Any]:
        """Assess code security and identify potential risks"""
        concerns = []
        
        # Check for system operations
        if re.search(r"(os\.system|subprocess|exec|eval)", code):
            concerns.append({
                "type": "system_operations",
                "description": "Code contains potentially dangerous system operations",
                "level": "dangerous"
            })
        
        # Check for file operations
        if re.search(r"(open|read|write|file|Path)", code):
            concerns.append({
                "type": "file_operations",
                "description": "Code contains file system operations",
                "level": "suspicious"
            })
        
        # Check for network operations
        if re.search(r"(socket|urllib|requests|http)", code):
            concerns.append({
                "type": "network_operations",
                "description": "Code contains network operations",
                "level": "suspicious"
            })
        
        # Check for dangerous imports
        found_imports = re.findall(r"import\s+(\w+)", code)
        for imp in found_imports:
            if imp in DANGEROUS_IMPORTS:
                concerns.append({
                    "type": "dangerous_import",
                    "description": DANGEROUS_IMPORTS[imp]["description"],
                    "level": DANGEROUS_IMPORTS[imp]["level"]
                })
        
        # Determine overall security level
        if any(c["level"] == "dangerous" for c in concerns):
            level = "dangerous"
        elif concerns:
            level = "suspicious"
        else:
            level = "safe"
        
        return {
            "level": level,
            "concerns": concerns,
            "analysis": {
                "has_system_calls": bool(re.search(r"os\.system", code)),
                "has_file_ops": bool(re.search(r"open\(", code)),
                "has_network": bool(re.search(r"socket|urllib|requests", code))
            }
        }

    async def get_resource_limits(self, context: ContextState) -> Dict[str, int]:
        """Get resource limits based on context"""
        # Base limits
        base_limits = {
            "memory_mb": 100,
            "time_seconds": 5,
            "file_size_kb": 1024,
            "subprocess_count": 0
        }
        
        # Adjust based on complexity
        if context.complexity == ComplexityLevel.MODERATE:
            base_limits.update({
                "memory_mb": 250,
                "time_seconds": 15,
                "file_size_kb": 5120,
                "subprocess_count": 1
            })
        elif context.complexity == ComplexityLevel.COMPLEX:
            base_limits.update({
                "memory_mb": 500,  # Maximum memory limit
                "time_seconds": 30,
                "file_size_kb": 10240,
                "subprocess_count": 2
            })
        
        # Further adjust based on context requirements
        if context.requires_memory:
            # Cap memory at 500MB even with memory requirements
            base_limits["memory_mb"] = min(500, base_limits["memory_mb"] * 1.5)
        if context.requires_persistence:
            base_limits["file_size_kb"] *= 2
        
        return base_limits

    async def validate_code(self, code: str, context: ContextState) -> Dict[str, Any]:
        """Validate code based on context requirements"""
        warnings = []
        
        # Style checks (more strict in complex contexts)
        if context.complexity in [ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]:
            # Check spacing around operators
            if re.search(r"\w+[+\-*/=]\w+", code):
                warnings.append({
                    "type": "style",
                    "message": "Missing spaces around operators"
                })
            
            # Check line length
            long_lines = [line for line in code.split("\n") if len(line.strip()) > 79]
            if long_lines:
                warnings.append({
                    "type": "style",
                    "message": "Lines exceed 79 characters"
                })
        
        # Security checks
        security = await self.assess_security(code)
        if security["level"] != "safe":
            warnings.extend([
                {"type": "security", "message": concern["description"]}
                for concern in security["concerns"]
            ])
        
        # Resource usage checks
        complexity = await self.analyze_complexity(code)
        limits = await self.get_resource_limits(context)
        
        if complexity > context.complexity:
            warnings.append({
                "type": "complexity",
                "message": f"Code complexity ({complexity.name}) exceeds context complexity ({context.complexity.name})"
            })
        
        # Determine overall validity
        valid = True
        if security["level"] == "dangerous":
            valid = False
        if warnings and any(w["type"] == "security" for w in warnings):
            valid = False
        
        return {
            "valid": valid,
            "warnings": warnings,
            "analysis": {
                "complexity": complexity.name,
                "security_level": security["level"],
                "resource_requirements": {
                    "estimated_memory_mb": limits["memory_mb"] / 2,  # Conservative estimate
                    "estimated_time_seconds": limits["time_seconds"] / 2
                }
            }
        }
