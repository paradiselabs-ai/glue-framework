"""SmolAgents Provider Implementation

This provider uses SmolAgents to:
1. Create tools dynamically
2. Parse natural language into tool intents
3. Execute tools with proper adhesive bindings
4. Handle MCP tool integration
"""

from typing import Dict, Any, Optional, List, Union, Tuple, Pattern, Callable
import re
import inspect
from datetime import datetime
from .base import BaseProvider
from ..core.types import AdhesiveType, ToolResult
from ..tools.base import BaseTool
from ..tools.dynamic_tool_factory import (
    DynamicToolFactory, 
    ToolSpec, 
    MCPServerSpec,
    ToolInput
)
from smolagents.tools import Tool, AUTHORIZED_TYPES
from smolagents.agents import ToolCallingAgent


class SmolAgentsProvider(BaseProvider):
    """Provider that uses SmolAgents for enhanced tool capabilities"""
    
    def __init__(
        self,
        name: str,
        team: str,
        available_adhesives: set[AdhesiveType],
        api_key: str,
        config: Optional[Dict[str, Any]] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            name=name,
            provider="smolagents",
            team=team,
            available_adhesives=available_adhesives,
            api_key=api_key,
            config=config
        )
        self.base_url = base_url
        self.tool_factory = DynamicToolFactory()
        self.team = team  # Store team name
        self._available_adhesives = available_adhesives  # Store available adhesives
        
    async def create_tool(self, name: str, description: str, function: Callable) -> BaseTool:
        """Create a new tool on the fly with enhanced validation and documentation"""
        # Extract function signature and docstring
        sig = inspect.signature(function)
        doc = inspect.getdoc(function) or ""
        
        # Parse docstring for parameter descriptions
        param_docs = {}
        param_section = False
        for line in doc.split('\n'):
            if ':param' in line:
                param_section = True
                param_match = re.match(r':param\s+(\w+):\s+(.+)', line)
                if param_match:
                    param_docs[param_match.group(1)] = param_match.group(2)
            elif param_section and not line.strip():
                param_section = False
        
        # Create input specifications for each parameter
        inputs = {}
        for param_name, param in sig.parameters.items():
            # Get description from docstring or generate default
            param_desc = param_docs.get(param_name, f"Input parameter: {param_name}")
            
            # Determine if parameter is optional
            is_optional = param.default != inspect.Parameter.empty
            default_value = param.default if is_optional else None
            
            # Create input specification
            inputs[param_name] = ToolInput(
                type="string",  # Default to string, can be enhanced based on type hints
                description=param_desc,
                optional=is_optional,
                default=default_value
            )
        
        # Create tool specification
        spec = ToolSpec(
            name=name,
            description=description,
            inputs=inputs,
            output_type="string",
            team_name=self.team,
            function=function
        )
        
        # Validate inputs against SmolAgents requirements
        validate_tool_inputs(inputs)
        return await self.tool_factory.create_tool_from_spec(spec, self.team)
        
    async def create_mcp_tool(self, server_name: str, tool_name: str) -> BaseTool:
        """Create tool from MCP server"""
        # Get tool schema from MCP
        schema = await self._get_mcp_schema(server_name, tool_name)
        
        spec = MCPServerSpec(
            name=server_name,
            tools=[ToolSpec(
                name=tool_name,
                description=schema.get("description", "MCP Tool"),
                inputs={
                    "arguments": {
                        "type": "object",
                        "description": "Arguments for the MCP tool"
                    }
                },
                output_type="string",
                team_name=self.team
            )]
        )
        
        tools = await self.tool_factory.create_mcp_server_from_spec(spec, self.team)
        return tools[tool_name]

    async def handle_tool_creation_request(self, request: str) -> Optional[BaseTool]:
        """Handle natural language tool creation requests"""
        request_lower = request.lower()
        
        # Handle citation tool creation
        if "citation" in request_lower and "format" in request_lower:
            async def format_citation(text: str) -> str:
                # Extract author, title, year
                import re
                
                # Extract title (handles both single and double quotes)
                title_match = re.search(r'["\']([^"\']+)["\']', text)
                title = title_match.group(1) if title_match else "Unknown Title"
                
                # Extract author (handles various formats)
                author_match = (
                    re.search(r'by\s+([^,\.]+(?:\s+[^,\.]+)*)', text) or  # "by John Smith"
                    re.search(r'([^,\.]+(?:\s+[^,\.]+)*)\s*,?\s*\(?\d{4}\)?', text)  # "John Smith (2024)"
                )
                author = author_match.group(1) if author_match else "Unknown Author"
                
                # Extract year
                year_match = re.search(r'\b(19|20)\d{2}\b', text)
                year = year_match.group(0) if year_match else "n.d."
                
                # Format author name
                names = author.strip().split()
                if len(names) >= 2:
                    last_name = names[-1]
                    first_names = ' '.join(names[:-1])
                    initials = ''.join(name[0] + '.' for name in first_names.split())
                    formatted_author = f"{last_name}, {initials}"
                else:
                    formatted_author = author
                
                # Format as APA style
                citation = f"{formatted_author} ({year}). {title}."
                
                # Add italics markers for title if specified
                if "journal" in text.lower() or "article" in text.lower():
                    citation = citation.replace(title, f"_{title}_")
                
                return citation
            
            return await self.create_tool(
                name="citation_formatter",
                description="Format text in APA citation style",
                function=format_citation
            )
            
        # Handle weather tool creation
        elif "weather" in request_lower and ("forecast" in request_lower or "create" in request_lower):
            async def get_weather(city: str) -> str:
                # Simulate weather data for testing
                import random
                temp = random.randint(15, 25)
                conditions = random.choice(["sunny", "cloudy", "rainy"])
                return f"Weather in {city}: {temp}°C, {conditions}"
            
            return await self.create_tool(
                name="weather_forecast",
                description="Get weather forecast for any city",
                function=get_weather
            )
            
        # Handle tool enhancement
        elif "enhance" in request_lower or "modify" in request_lower:
            if "search" in request_lower and "summarize" in request_lower:
                async def enhanced_search(query: str) -> str:
                    # First get search results
                    from ..tools.web_search import WebSearchTool
                    search_tool = WebSearchTool()
                    results = await search_tool.forward(query=query)
                    
                    # Extract and summarize key points
                    key_points = []
                    current_title = None
                    current_snippet = []
                    
                    for line in results.split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                            
                        if line.startswith("Title:"):
                            # Process previous snippet if exists
                            if current_title and current_snippet:
                                snippet_text = " ".join(current_snippet)
                                # Extract key information from snippet
                                if len(snippet_text) > 30:  # Only process substantial snippets
                                    key_points.append(f"From '{current_title}':")
                                    # Look for sentences with key indicators
                                    for sentence in snippet_text.split(". "):
                                        if any(indicator in sentence.lower() for indicator in 
                                              ["found", "discovered", "shows", "reveals", "suggests",
                                               "concludes", "demonstrates", "key", "important",
                                               "significant", "breakthrough", "new"]):
                                            key_points.append(f"- {sentence.strip()}.")
                            
                            current_title = line.split(":", 1)[1].strip()
                            current_snippet = []
                            
                        elif line.startswith("Snippet:"):
                            current_snippet = [line.split(":", 1)[1].strip()]
                        else:
                            current_snippet.append(line)
                    
                    # Process the last snippet
                    if current_title and current_snippet:
                        snippet_text = " ".join(current_snippet)
                        if len(snippet_text) > 30:
                            key_points.append(f"From '{current_title}':")
                            for sentence in snippet_text.split(". "):
                                if any(indicator in sentence.lower() for indicator in 
                                      ["found", "discovered", "shows", "reveals", "suggests",
                                       "concludes", "demonstrates", "key", "important",
                                       "significant", "breakthrough", "new"]):
                                    key_points.append(f"- {sentence.strip()}.")
                    
                    # Format output
                    output = [
                        "Search Results:",
                        "=" * 40,
                        results,
                        "\nKey Points & Findings:",
                        "=" * 40
                    ]
                    
                    if key_points:
                        output.extend(key_points)
                    else:
                        output.append("No significant findings extracted from the search results.")
                    
                    return "\n".join(output)
                
                return await self.create_tool(
                    name="enhanced_web_search",
                    description="Search the web and extract key points from results",
                    function=enhanced_search
                )
        
        # Default to factory's natural request parser
        return await self.tool_factory.parse_natural_request(request, self.team)
        
    async def use_tool(self, tool_name: str, adhesive: AdhesiveType, input_data: Any) -> ToolResult:
        """Use tool with enhanced execution and error handling"""
        try:
            # Validate adhesive
            if adhesive not in self.available_adhesives:
                raise ValueError(f"Model {self.name} cannot use {adhesive.name} adhesive")
            
            # Get tool with enhanced error handling
            tool = None
            if tool_name in self.team.tools:
                tool = self.team.tools[tool_name]
            elif hasattr(self, '_dynamic_tools') and tool_name in self._dynamic_tools:
                tool = self._dynamic_tools[tool_name]
            
            if not tool:
                available_tools = list(self.team.tools.keys())
                if hasattr(self, '_dynamic_tools'):
                    available_tools.extend(self._dynamic_tools.keys())
                raise ValueError(
                    f"Tool '{tool_name}' not available to team {self.team.name}.\n"
                    f"Available tools: {', '.join(available_tools)}"
                )
            
            # Pre-execution validation
            if not input_data:
                raise ValueError("Input data cannot be empty")
                
            # Import team data if using GLUE
            if adhesive == AdhesiveType.GLUE:
                if hasattr(tool, 'import_team_data'):
                    shared_data = self.team.shared_results.get(tool_name)
                    if shared_data:
                        await tool.import_team_data(shared_data)
            
            # Execute through SmolAgents with timeout handling
            from smolagents import ToolCallingAgent
            import asyncio
            
            agent = ToolCallingAgent()
            smol_tool = await self._convert_tool(tool)
            
            # Get first input key from tool's inputs
            input_key = next(iter(tool.inputs))
            # Create kwargs with the correct parameter name
            kwargs = {input_key: input_data}
            
            try:
                # Execute with timeout
                result = await asyncio.wait_for(
                    agent.execute(smol_tool, **kwargs),
                    timeout=30.0  # 30 second timeout
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Tool execution timed out after 30 seconds")
            
            # Validate result
            if result is None:
                raise ValueError("Tool execution returned None")
            
            # Create result with metadata
            tool_result = ToolResult(
                tool_name=tool_name,
                result=result,
                adhesive=adhesive,
                timestamp=datetime.now(),
                metadata={
                    "input": input_data,
                    "tool_type": tool.__class__.__name__,
                    "execution_time": datetime.now().isoformat()
                }
            )
            
            # Handle based on adhesive with error handling
            try:
                if adhesive == AdhesiveType.GLUE:
                    await self.team.share_result(tool_result)
                elif adhesive == AdhesiveType.VELCRO:
                    if not hasattr(self, '_session_results'):
                        self._session_results = {}
                    self._session_results[tool_name] = tool_result
            except Exception as e:
                print(f"Warning: Failed to handle adhesive result: {str(e)}")
                # Continue since we still want to return the result
            
            return tool_result
            
        except Exception as e:
            # Enhanced error handling with context
            error_msg = f"Tool execution failed: {str(e)}"
            if "timeout" in str(e).lower():
                error_msg += "\nTool execution took too long. Please try again or use a simpler query."
            elif "validation" in str(e).lower():
                error_msg += f"\nPlease check the input format for {tool_name}."
            raise ValueError(error_msg)
        
    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to SmolAgents with enhanced processing and error handling"""
        try:
            from smolagents import ToolCallingAgent
            import asyncio
            
            # Validate request data
            if not isinstance(request_data, dict):
                raise TypeError("Request data must be a dictionary")
            
            if "messages" not in request_data:
                raise ValueError("Request data must contain 'messages' key")
            
            if not request_data["messages"]:
                raise ValueError("Messages list cannot be empty")
            
            # Get available tools with validation
            tools = []
            if hasattr(self.team, 'tools'):
                tools.extend(self.team.tools.values())
            if hasattr(self, '_dynamic_tools'):
                tools.extend(self._dynamic_tools.values())
            
            if not tools:
                raise ValueError(
                    f"No tools available for team {self.team.name}. "
                    "Please ensure tools are properly initialized."
                )
            
            # Initialize agent with configuration
            agent = ToolCallingAgent()
            
            # Process request with timeout
            try:
                response = await asyncio.wait_for(
                    agent.process_message(
                        request_data["messages"],
                        tools=tools
                    ),
                    timeout=30.0  # 30 second timeout
                )
            except asyncio.TimeoutError:
                raise TimeoutError("Request processing timed out after 30 seconds")
            
            # Validate response
            if not response:
                raise ValueError("Received empty response from SmolAgents")
            
            if "choices" not in response:
                raise ValueError("Invalid response format: missing 'choices' key")
            
            # Add metadata to response
            response["metadata"] = {
                "timestamp": datetime.now().isoformat(),
                "team_name": self.team.name,
                "num_tools_available": len(tools),
                "request_type": request_data["messages"][-1].get("role", "unknown")
            }
            
            return response
            
        except Exception as e:
            # Enhanced error handling with context
            error_msg = f"Failed to make request: {str(e)}"
            if isinstance(e, TimeoutError):
                error_msg += "\nRequest took too long to process. Try simplifying your request."
            elif "no tools available" in str(e).lower():
                error_msg += f"\nAvailable tools: {', '.join(t.name for t in tools) if tools else 'None'}"
            elif "invalid response format" in str(e).lower():
                error_msg += "\nReceived unexpected response format from SmolAgents"
            raise ValueError(error_msg)
            
    async def _handle_error(self, error: Exception) -> None:
        """Handle SmolAgents errors with enhanced logging and context"""
        import traceback
        from datetime import datetime
        
        try:
            # Get error context
            error_type = error.__class__.__name__
            error_msg = str(error)
            stack_trace = traceback.format_exc()
            
            # Create detailed error log
            error_log = {
                "timestamp": datetime.now().isoformat(),
                "error_type": error_type,
                "message": error_msg,
                "stack_trace": stack_trace,
                "context": {
                    "team": self.team.name if hasattr(self, 'team') else None,
                    "provider": self.provider,
                    "available_adhesives": [a.name for a in self._available_adhesives] if hasattr(self, '_available_adhesives') else [],
                    "tools": list(self.team.tools.keys()) if hasattr(self.team, 'tools') else []
                }
            }
            
            # Log error details
            print("\nSmolAgents Error Details:")
            print("=" * 50)
            print(f"Time: {error_log['timestamp']}")
            print(f"Type: {error_log['error_type']}")
            print(f"Message: {error_log['message']}")
            print("\nContext:")
            for key, value in error_log["context"].items():
                print(f"- {key}: {value}")
            print("\nStack Trace:")
            print(stack_trace)
            print("=" * 50)
            
            # Construct user-friendly error message
            user_msg = f"SmolAgents error: {error_msg}"
            
            # Add context-specific help
            if "timeout" in error_msg.lower():
                user_msg += "\nThe operation took too long to complete. Try breaking it into smaller steps."
            elif "validation" in error_msg.lower():
                user_msg += "\nThe input provided was invalid. Check the tool's requirements and try again."
            elif "permission" in error_msg.lower():
                user_msg += "\nThe tool doesn't have the necessary permissions. Contact your administrator."
            elif "not found" in error_msg.lower():
                available_tools = error_log["context"]["tools"]
                user_msg += f"\nAvailable tools: {', '.join(available_tools)}" if available_tools else "\nNo tools currently available."
            
            # Re-raise with enhanced message
            raise ValueError(user_msg)
            
        except Exception as e:
            # Fallback error handling if error processing fails
            print(f"Error while handling error: {str(e)}")
            raise ValueError(f"SmolAgents error: {str(error)} (Error handling failed)")
        
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare request with SmolAgents context"""
        # Get natural context
        workspace_context = self._format_workspace()
        team_context = self._format_team_context()
        conversation_context = self._format_conversation()
        
        # Create system prompt that encourages natural tool usage
        system_prompt = f"""You are {self.name}, working in the {self.team} team.

Your role: {self.role}

Your workspace:
{workspace_context}

Your team:
{team_context}

Recent conversation:
{conversation_context}

You can use tools naturally by describing what you want to do. For example:
- "Let me search for information about that topic"
- "I'll save these findings to a file"
- "I need to analyze this data"

When using tools, be clear about your intentions:
- Share with team (GLUE): "I'll search for this and share it with the team"
- Keep for session (VELCRO): "I'll save this for my reference"
- One-time use (TAPE): "Let me quickly check something"

You can also request new tools if needed:
- "I need a tool that can format text in APA style"
- "Could we create a tool to analyze sentiment?"
- "Let's create an MCP server for weather data"

Available Tools:
{workspace_context}"""

        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }
        
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process response and execute any tool intents"""
        try:
            content = response["choices"][0]["message"]["content"]
            
            # Parse natural language into tool intent
            from smolagents import ToolCallingAgent
            agent = ToolCallingAgent()
            
            # First check for tool creation request
            if any(phrase in content.lower() for phrase in ["create a tool", "create an mcp", "enhance the", "modify the"]):
                tool = await self.handle_tool_creation_request(content)
                if tool:
                    # For citation tool, add example usage
                    if "citation" in tool.name.lower():
                        return (
                            f"Created new tool: {tool.name}\n"
                            f"{tool.description}\n\n"
                            "Example usage: Format this citation: 'Title' by Author, Year"
                        )
                    # For weather tool, add example usage
                    elif "weather" in tool.name.lower():
                        return (
                            f"Created new tool: {tool.name}\n"
                            f"{tool.description}\n\n"
                            "Example usage: What's the weather in London?"
                        )
                    # For enhanced tools, show what's new
                    elif "enhanced" in content.lower():
                        return (
                            f"Enhanced tool: {tool.name}\n"
                            f"New capabilities: {tool.description}"
                        )
                    else:
                        return f"Created new tool: {tool.name}\n{tool.description}"
            
            # Then try to parse tool usage intent
            try:
                intent = await agent.parse_message(content)
                
                if intent and "tool" in intent:
                    # Execute tool
                    result = await self.use_tool(
                        tool_name=intent["tool"],
                        adhesive=AdhesiveType[intent.get("adhesive", "TAPE").upper()],
                        input_data=intent["input"]
                    )
                    return str(result.result)
                    
            except Exception as e:
                # If tool execution fails, return original response
                pass
                
            return content
            
        except Exception as e:
            raise ValueError(f"Failed to process response: {str(e)}")
            
    async def _convert_tool(self, tool: BaseTool) -> Any:
        """Convert GLUE tool to SmolAgents tool with enhanced validation and error handling"""
        from smolagents import Tool, AUTHORIZED_TYPES
        from smolagents.tool_validation import validate_tool_inputs
        import inspect
        
        class ConvertedTool(Tool):
            name = tool.name
            description = (
                f"{tool.description}\n\n"
                f"Input format: {next(iter(tool.inputs.keys()))} (string)\n"
                f"Example usage: {self._get_example_for_tool(tool)}"
            )
            
            # Validate and convert input specifications
            inputs = {
                name: {
                    # Ensure type is one of SmolAgents' authorized types
                    "type": (
                        input_spec.type if input_spec.type in AUTHORIZED_TYPES 
                        else "string"  # Default to string if type not authorized
                    ),
                    "description": (
                        f"{input_spec.description}\n"
                        f"Format: {self._get_format_hint(name, tool)}"
                    ),
                    "optional": input_spec.optional,
                    "default": input_spec.default,
                    # Enhanced validation rules
                    "validation": {
                        "min_length": 1,
                        "pattern": self._get_validation_pattern(name, tool),
                        "custom_check": self._get_custom_validator(name, tool)
                    } if input_spec.type == "string" else None
                }
                for name, input_spec in tool.inputs.items()
            }
            output_type = "string"
            
            def _get_format_hint(self, name: str, tool: BaseTool) -> str:
                """Get format hint based on input name and tool type"""
                if "city" in name.lower():
                    return "City name (letters and spaces only)"
                elif "citation" in tool.name.lower():
                    return "'Title' by Author, Year"
                elif "search" in tool.name.lower():
                    return "Search query"
                return "Text input"
            
            def _get_validation_pattern(self, name: str, tool: BaseTool) -> Optional[Pattern[str]]:
                """Get regex pattern for input validation"""
                if "city" in name.lower():
                    return re.compile(r'^[A-Za-z\s,]+$')
                elif "citation" in tool.name.lower():
                    return re.compile(r'^["\']([^"\']+)["\']\s+by\s+([^,\.]+)')
                return None
            
            def _get_custom_validator(self, name: str, tool: BaseTool):
                """Get custom validation function"""
                def validator(value: str) -> Tuple[bool, str]:
                    if "city" in name.lower():
                        if not value.replace(" ", "").isalpha():
                            return False, "City names should only contain letters and spaces"
                    elif "citation" in tool.name.lower():
                        if not ("'" in value or '"' in value):
                            return False, "Citation must include title in quotes"
                    return True, ""
                return validator
            
            async def setup(self) -> None:
                """Initialize any required resources"""
                # Validate tool configuration
                validate_tool_inputs(self.inputs)
                if hasattr(tool, 'setup'):
                    await tool.setup()
            
            async def forward(self, **kwargs) -> str:
                """Execute the GLUE tool with comprehensive error handling"""
                try:
                    # Get input key and data
                    input_key = next(iter(tool.inputs))
                    input_data = kwargs.get(input_key)
                    
                    # Basic validation
                    if input_data is None:
                        raise ValueError(f"Missing required parameter: {input_key}")
                    if not isinstance(input_data, str):
                        raise TypeError(f"Expected string input for {input_key}, got {type(input_data)}")
                    if len(input_data.strip()) == 0:
                        raise ValueError(f"Empty input provided for {input_key}")
                    
                    # Custom validation
                    validator = self._get_custom_validator(input_key, tool)
                    is_valid, error_msg = validator(input_data)
                    if not is_valid:
                        raise ValueError(error_msg)
                    
                    # Execute tool
                    result = await tool.execute(input_data)
                    
                    # Validate and format result
                    if result is None:
                        raise ValueError("Tool execution returned None")
                    return str(result)
                    
                except Exception as e:
                    # Enhanced error handling with context
                    error_context = {
                        "tool_name": tool.name,
                        "input_key": input_key,
                        "input_data": input_data,
                        "error_type": e.__class__.__name__
                    }
                    
                    error_msg = f"Tool execution failed: {str(e)}\n"
                    error_msg += self._get_error_help(error_context)
                    raise ValueError(error_msg)
            
            def _get_error_help(self, context: Dict[str, Any]) -> str:
                """Get helpful error message based on context"""
                if "city" in context["input_key"].lower():
                    return "Please provide a valid city name (letters and spaces only)"
                elif "citation" in context["tool_name"].lower():
                    return "Expected format: 'Title' by Author, Year"
                elif "timeout" in str(context["error_type"]).lower():
                    return "Operation timed out. Try with a simpler query"
                return "Check the input format and try again"
        
            def _get_example_for_tool(self, tool: BaseTool) -> str:
                """Get example usage based on tool type"""
                tool_name = tool.name.lower()
                if "citation" in tool_name:
                    return "'The Future of AI' by John Smith, 2024"
                elif "weather" in tool_name:
                    return "What's the weather in London?"
                elif "search" in tool_name:
                    return "Search for: quantum computing breakthroughs"
                elif "format" in tool_name:
                    return f"Format this text according to {tool_name.split('_')[0]} style"
                elif "analyze" in tool_name:
                    return f"Analyze this data: [your {tool_name.split('_')[0]} input]"
                elif "generate" in tool_name:
                    return f"Generate {tool_name.split('_')[0]}: [your requirements]"
                elif "convert" in tool_name:
                    return f"Convert this {tool_name.split('_')[0]}: [your input]"
                elif "extract" in tool_name:
                    return f"Extract {tool_name.split('_')[0]} from: [your input]"
                elif "summarize" in tool_name:
                    return f"Summarize this {tool_name.split('_')[0]}: [your text]"
                elif "translate" in tool_name:
                    return f"Translate this {tool_name.split('_')[0]}: [your text]"
                
                # Default example based on first input parameter
                input_key = next(iter(tool.inputs.keys()))
                return f"Example: {input_key} <your input here>"
        
        return ConvertedTool()
            
    async def _get_mcp_schema(self, server: str, tool: str) -> Dict[str, Any]:
        """Get tool schema from MCP server"""
        from ..tools.executor import SmolAgentsToolExecutor
        executor = SmolAgentsToolExecutor(self.team, self.available_adhesives)
        return await executor._get_mcp_schema(server, tool)
        
    async def _use_mcp_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Use MCP tool through SmolAgents"""
        from ..tools.executor import SmolAgentsToolExecutor
        executor = SmolAgentsToolExecutor(self.team, self.available_adhesives)
        return await executor.create_mcp_tool(server_name, tool_name)
