"""Code Interpreter Tool with Advanced Features"""

import os
import sys
import asyncio
import tempfile
import re
import importlib.util
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass

from .simple_base import SimpleBaseTool
from ..core.types import AdhesiveType
from ..core.context import ContextState, ComplexityLevel
from ..core.state import ResourceState
from ..core.logger import get_logger

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

# ==================== Code Result ====================
@dataclass
class CodeResult:
    """Result from code execution"""
    output: str
    error: Optional[str] = None
    files: List[str] = None
    success: bool = True
    error_type: Optional[str] = None
    error_context: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    analysis: Optional[Dict[str, Any]] = None
    resource_usage: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.files is None:
            self.files = []
        if self.error_context is None:
            self.error_context = {}
        if self.suggestions is None:
            self.suggestions = []
        if self.analysis is None:
            self.analysis = {}
        if self.resource_usage is None:
            self.resource_usage = {}

# ==================== Code Interpreter Tool ====================
class CodeInterpreterTool(SimpleBaseTool):
    """
    Advanced code interpreter tool with security and analysis features.
    
    Features:
    - Code execution in multiple languages
    - Security checks and analysis
    - Resource tracking
    - Error suggestions
    - Adhesive-based persistence
    """
    
    def __init__(
        self,
        name: str = "code_interpreter",
        description: str = "Executes code in a sandboxed environment",
        workspace_dir: Optional[str] = None,
        supported_languages: Optional[List[str]] = None,
        adhesive_type: Optional[AdhesiveType] = None,
        enable_security_checks: bool = True,
        enable_code_analysis: bool = True,
        enable_error_suggestions: bool = True,
        max_memory_mb: int = 500,
        max_execution_time: int = 30,
        max_file_size_kb: int = 10240,
        max_subprocess_count: int = 2
    ):
        super().__init__(
            name=name,
            description=description,
            adhesive_type=adhesive_type
        )
        
        # Initialize logger
        self.logger = get_logger()
        
        # Feature flags
        self.enable_security_checks = enable_security_checks
        self.enable_code_analysis = enable_code_analysis
        self.enable_error_suggestions = enable_error_suggestions
        
        # Resource limits
        self.max_memory_mb = max_memory_mb
        self.max_execution_time = max_execution_time
        self.max_file_size_kb = max_file_size_kb
        self.max_subprocess_count = max_subprocess_count
        
        # Initialize languages and workspace
        self.supported_languages = (
            {lang: SUPPORTED_LANGUAGES[lang] 
             for lang in supported_languages if lang in SUPPORTED_LANGUAGES}
            if supported_languages
            else SUPPORTED_LANGUAGES
        )
        self.workspace_dir = os.path.abspath(workspace_dir or "workspace")
        self._temp_files: List[str] = []
        
        # Ensure workspace exists
        os.makedirs(self.workspace_dir, exist_ok=True)

                    continue
                
                await self._transition_state(ResourceState.IDLE)
                return CodeResult(
                    output="",
                    error=str(e),
                    success=False,
                    error_type=error_type,
                    error_context=error_context,
                    suggestions=self._generate_error_suggestions(str(e))
                )

    async def _execute(self, code: str, language: Optional[str] = None, timeout: Optional[float] = None, context: Optional[ContextState] = None) -> Dict[str, Any]:
        """Execute code with automatic language detection and validation"""
        
        # Validate code if enabled
        if self.enable_security_checks and context:
            validation = await self.validate_code(code, context)
            if not validation["valid"]:
                return {
                    "success": False,
                    "error": "Code validation failed",
                    "validation": validation
                }
            
            # Apply resource limits
            limits = await self.get_resource_limits(context)
            timeout = min(timeout or self.max_execution_time, self.max_execution_time)

        # Infer language if not provided
        if not language:
            language = await self.detect_language(code) if context else self._infer_language(code)
            print(f"Inferred language: {language}")
        
        # Clean up code
        code = self._clean_code(code, language)
        print(f"Cleaned code:\n{code}")

        if language not in self.supported_languages:
            raise ValueError(
                f"Unsupported language: {language}. "
                f"Supported: {list(self.supported_languages.keys())}"
            )

        lang_config = self.supported_languages[language]
        timeout = timeout or lang_config["timeout"]

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

            # Add analysis information if enabled
            if self.enable_code_analysis and context:
                complexity = await self.analyze_complexity(code)
                if self.enable_security_checks:
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
                else:
                    result.update({
                        "complexity": complexity,
                        "resource_usage": {
                            "time_seconds": timeout,
                            "memory_mb": limits["memory_mb"]
                        }
                    })

                # Add error suggestions if enabled
                if not result["success"] and self.enable_error_suggestions and context.complexity >= ComplexityLevel.MODERATE:
                    result.update({
                        "traceback": stderr_str,
                        "suggestions": self._generate_error_suggestions(stderr_str)
                    })

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

    async def cleanup(self) -> None:
        """Cleanup temporary files"""
        errors = []
        
        try:
            # Clean up temp files
            for file_path in list(self._temp_files):
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except OSError as e:
                    errors.append(f"Failed to remove {file_path}: {str(e)}")
            
            # Clean up workspace if using temp dir
            if self.workspace_dir.startswith(tempfile.gettempdir()):
                try:
                    for root, dirs, files in os.walk(self.workspace_dir, topdown=False):
                        for name in files:
                            try:
                                os.remove(os.path.join(root, name))
                            except OSError as e:
                                errors.append(f"Failed to remove file {name}: {str(e)}")
                        for name in dirs:
                            try:
                                os.rmdir(os.path.join(root, name))
                            except OSError as e:
                                errors.append(f"Failed to remove directory {name}: {str(e)}")
                    try:
                        os.rmdir(self.workspace_dir)
                    except OSError as e:
                        errors.append(f"Failed to remove workspace directory: {str(e)}")
                except Exception as e:
                    errors.append(f"Failed to clean workspace: {str(e)}")
            
        finally:
            # Always clear temp files list
            self._temp_files.clear()
            
            # Report any errors that occurred during cleanup
            if errors:
                error_msg = "\n".join(errors)
                print(f"Cleanup errors:\n{error_msg}")
                if len(errors) > 1:
                    raise RuntimeError(f"Multiple cleanup errors occurred:\n{error_msg}")
                raise RuntimeError(errors[0])

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
            lines = []
            for original_line in code.split('\n'):
                line = original_line
                # Handle function definitions
                if 'def ' in line and '(' in line and ')' in line:
                    parts = line.split('(', 1)
                    before_params = parts[0] + '('
                    params_with_closing = parts[1]
                    params = params_with_closing[:params_with_closing.rfind(')')]
                    after_params = ')' + params_with_closing[params_with_closing.rfind(')')+1:]
                    if params.strip():
                        params_list = [p.strip() for p in params.split()]
                        if params_list and params_list[0] == 'self':
                            formatted_params = 'self' + (', ' + ', '.join(params_list[1:]) if len(params_list) > 1 else '')
                        else:
                            formatted_params = ', '.join(params_list)
                        line = before_params + formatted_params + after_params

                import ast

                # Handle list literals
                if '[' in line and ']' in line:
                    def replace_list(match):
                        try:
                            list_content = match.group(0)
                            # Safely evaluate the list literal
                            parsed_list = ast.literal_eval(list_content)
                            # Format the list back into a string with proper spacing
                            formatted_content = ', '.join(repr(item) for item in parsed_list)
                            return f'[{formatted_content}]'
                        except (SyntaxError, ValueError):
                            # If parsing fails, return the original content
                            return match.group(0)

                    line = re.sub(r'\[.*?\]', replace_list, line)

                # Handle method calls
                if '.' in line and '(' in line and ')' in line:
                    parts = line.split('.')
                    if len(parts) > 1:
                        base = parts[0]
                        method_with_params = parts[1]
                        if '(' in method_with_params and ')' in method_with_params:
                            before_params = method_with_params[:method_with_params.find('(')+1]
                            params_with_closing = method_with_params[method_with_params.find('(')+1:]
                            params = params_with_closing[:params_with_closing.rfind(')')]
                            after_params = ')' + params_with_closing[params_with_closing.rfind(')')+1:]
                            if params.strip():
                                param_list = [p.strip() for p in params.split()]
                                formatted_params = ', '.join(param_list)
                                method_call = before_params + formatted_params + after_params
                                line = base + '.' + method_call
                lines.append(line)
            code = '\n'.join(lines)

        # Normalize indentation
        code = self._normalize_indentation(code)
        return code

    async def prepare_input(self, text: str) -> str:
        """Extract code from model's response"""
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

    async def analyze_complexity(self, code: str) -> ComplexityLevel:
        """Analyze code complexity based on various metrics"""
        # Remove comments and empty lines
        clean_code = "\n".join(
            line for line in code.split("\n")
            if line.strip() and not line.strip().startswith(("#", "//"))
        )
    
        # Simple patterns - basic operations, single function calls
        simple_patterns = {
            "print_statements": len(re.findall(r"\bprint\s*\(", clean_code)),
            "basic_assignments": len(re.findall(r"=(?![=])", clean_code)),
            "simple_math": len(re.findall(r"[+\-*/]=?", clean_code))
        }
    
        # Moderate patterns - basic functions, basic loops, simple recursion
        moderate_patterns = {
            "functions": len(re.findall(r"\bdef\s+\w+\s*\([^)]*\):", clean_code)),
            "basic_loops": len(re.findall(r"\b(for|while)\b", clean_code)),
            "conditionals": len(re.findall(r"\b(if|elif|else)\b", clean_code)),
            "simple_recursion": bool(
                # Check for simple recursive function (single recursive call)
                re.search(r"def\s+(\w+)[^{]*?return[^{]*?\1\s*\([^{]*$", 
                         clean_code, 
                         re.MULTILINE | re.DOTALL)
            )
        }
    
        # Complex patterns - classes, nested structures, complex recursion
        complex_patterns = {
            "classes": len(re.findall(r"\bclass\s+\w+", clean_code)),
            "nested_functions": len(re.findall(r"def.*\n\s+def\s+", clean_code)),
            "decorators": len(re.findall(r"@\w+", clean_code)),
            "comprehensions": len(re.findall(r"\[.*for.*in.*\]", clean_code)),
            "complex_recursion": bool(  # Multiple recursive calls or complex recursive pattern
                re.search(r"def\s+(\w+).*\1.*\1", clean_code, re.DOTALL) and
                not moderate_patterns["simple_recursion"]
            )
        }
    
        # Calculate scores with adjusted weights
        simple_score = sum(simple_patterns.values())
        moderate_score = sum(moderate_patterns.values()) * 2
        complex_score = sum(1 for v in complex_patterns.values() if v) * 3
    
        # Check nesting level
        max_indent = 0
        current_indent = 0
        for line in clean_code.split('\n'):
            if line.strip():
                current_indent = len(line) - len(line.lstrip())
                max_indent = max(max_indent, current_indent)
    
        # Adjust scores based on nesting
        if max_indent > 12:  # More than 3 levels of nesting
            complex_score += 2
        elif max_indent > 8:  # More than 2 levels of nesting
            moderate_score += 2
    
        # Determine complexity level based on scores and characteristics
        if (complex_score > 0 and not (
            len(complex_patterns) == 1 and complex_patterns.get("comprehensions", 0) == 1
        )) or max_indent > 12:
            return ComplexityLevel.COMPLEX
        elif moderate_score > 0 or simple_score > 3 or max_indent > 8:
            return ComplexityLevel.MODERATE
        else:
            return ComplexityLevel.SIMPLE
    
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
        
        # Check for syntax errors
        try:
            compile(code, '<string>', 'exec')
        except SyntaxError:
            valid = False
            warnings.append({
                "type": "error",
                "message": "Code contains syntax errors"
            })
        
        # Check for undefined variables in Python code
        undefined_vars = set()
        if code.strip():  # Only check if code is not empty
            try:
                # Try to compile the code to check for syntax
                compile(code, '<string>', 'exec')
                
                # Extract all variable names being used
                used_vars = set()
                defined_vars = {'print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict', 'set', 'True', 'False', 'None'}
                
                # Find all variable uses
                for match in re.finditer(r'\b([a-zA-Z_]\w*)\b', code):
                    var = match.group(1)
                    if var not in defined_vars:
                        used_vars.add(var)
                
                # Find all variable definitions
                for line in code.split('\n'):
                    stripped = line.strip()
                    if '=' in stripped and not stripped.startswith(('def ', 'class ')):
                        var_name = stripped.split('=')[0].strip()
                        defined_vars.add(var_name)
                    elif stripped.startswith('def '):
                        func_name = stripped[4:].split('(')[0].strip()
                        defined_vars.add(func_name)
                    elif stripped.startswith('class '):
                        class_name = stripped[6:].split('(')[0].strip()
                        defined_vars.add(class_name)
                
                # Find undefined variables
                undefined_vars = used_vars - defined_vars
            except Exception as e:
                warnings.append({
                    "type": "error",
                    "message": f"Error analyzing code: {str(e)}"
                })
        
        if undefined_vars:
            valid = False
            warnings.append({
                "type": "error",
                "message": f"Undefined variables: {', '.join(undefined_vars)}"
            })
        
        # Security and complexity checks
        if security["level"] == "dangerous":
            valid = False
        if warnings and any(w["type"] == "security" for w in warnings):
            valid = False
        
        # For simple context, only fail on syntax errors and undefined variables
        if context.complexity == ComplexityLevel.SIMPLE:
            # Clear any style or complexity warnings for simple context
            warnings = [w for w in warnings if w["type"] == "error"]
            valid = not (any(w["type"] == "error" for w in warnings) or undefined_vars)
        
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


    def __str__(self) -> str:
        """String representation"""
        status = f"{self.name}: {self.description}"
        if self.binding_type:
            status += f" (Binding: {self.binding_type.name})"
        return status
