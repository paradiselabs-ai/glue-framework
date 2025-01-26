"""OpenRouter Provider Implementation"""

import os
import re
import json
import aiohttp
from typing import Dict, List, Any, Optional, Set
from .simple_base import SimpleBaseProvider
from ..core.model import ModelConfig
from ..core.logger import get_logger
from ..core.simple_resource import SimpleResource
from ..core.state import ResourceState, StateManager
from ..core.types import IntentAnalysis

class OpenRouterProvider(SimpleBaseProvider):
    """
    Provider for OpenRouter API.
    
    Features:
    - API integration
    - State tracking
    - Conversation history
    - Resource lifecycle
    """
    
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API request"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/paradiseLabs-ai/glue-framework",
            "Accept": "application/json",
            "X-Title": "GLUE Framework"
        }
        return headers

    def _configure_tools(self) -> None:
        """Configure tools and update system prompt"""
        if not hasattr(self, "_tools"):
            self._tools = {}
            self._tool_bindings = {}  # Initialize tool bindings dict
            
        # If inheriting from parent, copy tools and role
        if hasattr(self, "_parent"):
            parent = self._parent
            self._tools = parent._tools.copy()
            self._tool_bindings = parent._tool_bindings.copy()  # Copy bindings
            self.role = parent.role
            self.config.system_prompt = parent.config.system_prompt
            
        # Update system prompt with tool info
        if self._tools and self.messages and self.messages[0]["role"] == "system":
            system_prompt = self.messages[0]["content"]
            tool_info = "\n\nYou have access to the following tools:\n"
            for name, tool in self._tools.items():
                binding_type = self._tool_bindings.get(name, "unknown")
                persistence = {
                    "glue": "(permanent access)",
                    "velcro": "(flexible access)",
                    "tape": "(temporary access)",
                    "unknown": ""
                }
                tool_info += f"- {name}: {tool.description} {persistence.get(binding_type, '')}\n"
            
            tool_info += """
To use a tool:
<think>Explain why you need this tool</think>
<tool>tool_name</tool>
<input>what you want the tool to do</input>

Examples:

1. Web Search:
<think>I need to search for recent news about AI</think>
<tool>web_search</tool>
<input>latest developments in open source AI models</input>

2. File Handling:
<think>I need to save this information</think>
<tool>file_handler</tool>
<input>Title: AI News Summary
Latest developments in open source AI:
1. ...
2. ...</input>

3. Code Execution:
<think>I need to analyze some data with Python</think>
<tool>code_interpreter</tool>
<input>
import pandas as pd

# Create sample data
data = {'Model': ['GPT-4', 'Claude', 'Llama'],
        'Score': [95, 92, 88]}
df = pd.DataFrame(data)

# Calculate average
print(f"Average score: {df['Score'].mean()}")
</input>"""
            self.messages[0]["content"] = system_prompt + tool_info

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "meta-llama/llama-3.1-70b-instruct:free",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        name: Optional[str] = None
    ):
        # Create model config
        config = ModelConfig(
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt
        )
        
        # Initialize base provider
        super().__init__(
            name=name or model,
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            config=config,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # Store model ID separately
        self.model_id = model
        
        if not self.api_key:
            raise ValueError("OpenRouter API key not found")
        
        # Initialize logger
        self.logger = get_logger()
        
        # Initialize conversation history
        self.messages: List[Dict[str, str]] = []
        
        # Initialize with state management
        self._state_manager = StateManager()
        
        # Initialize system prompt
        default_prompt = (
            "You are a helpful AI assistant. "
            "You may work independently or as part of a team. "
            "You have access to specific tools based on your assigned capabilities. "
            "Always think carefully about what tools you need and how to use them effectively.\n\n"
            "To use a tool, format your response like this:\n"
            "<think>Explain why you need to use this tool</think>\n"
            "<tool>tool_name</tool>\n"
            "<input>what you want the tool to do</input>\n\n"
            "For example:\n"
            "1. To search the web:\n"
            "<think>I need to find recent information about AI developments</think>\n"
            "<tool>web_search</tool>\n"
            "<input>latest developments in open source AI models</input>\n\n"
            "2. To save information to a file:\n"
            "<think>I need to save this research summary</think>\n"
            "<tool>file_handler</tool>\n"
            "<input>Title: AI Research Summary\nContent: ...</input>"
        )
        
        system_prompt = system_prompt or default_prompt
        self.logger.debug(f"Initializing with system prompt: {system_prompt}")
        self.messages.append({
            "role": "system",
            "content": system_prompt
        })
        
        # Initialize tools and bindings
        self._tools = {}
        self._tool_bindings = {}
        
        # Configure tools (will update system prompt if needed)
        self._configure_tools()
        
        # Log final configuration
        self.logger.debug(f"Provider initialized: {self.name}")
        self.logger.debug(f"Model: {self.model_id}")
        self.logger.debug(f"Temperature: {self.config.temperature}")
        self.logger.debug(f"Max tokens: {self.config.max_tokens}")
    
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare request for OpenRouter API"""
        # Add user prompt to conversation
        self.messages.append({
            "role": "user",
            "content": prompt
        })
        
        request_data = {
            "model": self.model_id,  # Use model ID for API calls
            "messages": self.messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens
        }
        
        # Only add optional parameters if they exist and are not None
        if hasattr(self.config, 'top_p') and self.config.top_p is not None:
            request_data["top_p"] = self.config.top_p
        if hasattr(self.config, 'presence_penalty') and self.config.presence_penalty is not None:
            request_data["presence_penalty"] = self.config.presence_penalty
        if hasattr(self.config, 'frequency_penalty') and self.config.frequency_penalty is not None:
            request_data["frequency_penalty"] = self.config.frequency_penalty
        if hasattr(self.config, 'stop_sequences') and self.config.stop_sequences:
            request_data["stop"] = self.config.stop_sequences
        
        # Log request details
        safe_data = {k: v for k, v in request_data.items() if k != "messages"}
        self.logger.debug(f"Preparing request:\n{json.dumps(safe_data, indent=2)}")
        self.logger.debug("Messages history:")
        for msg in self.messages:
            self.logger.debug(f"{msg['role']}: {msg['content']}")
        
        return request_data
    
    def _parse_intent_analysis(self, analysis: str) -> IntentAnalysis:
        """Parse intent analysis from model output"""
        # Default values
        score = 0.0
        needed_tools: Set[str] = set()
        reasoning = ""
        
        try:
            # Extract score (look for numbers between 0-1)
            score_match = re.search(r"Score:?\s*(0?\.\d+|1\.0|1)", analysis)
            if score_match:
                score = float(score_match.group(1))
                
            # Extract needed tools (look for tool names after "tools needed:" or similar)
            tools_match = re.search(r"Tools?\s*(?:needed|required)?:?\s*([^\n]+)", analysis)
            if tools_match:
                tool_list = tools_match.group(1).strip()
                needed_tools = {t.strip() for t in tool_list.split(',') if t.strip()}
                
            # Extract reasoning (everything else)
            reasoning = analysis.strip()
            
        except Exception as e:
            self.logger.error(f"Error parsing intent analysis: {str(e)}")
            self.logger.error(f"Raw analysis: {analysis}")
            
        return IntentAnalysis(
            score=score,
            needed_tools=needed_tools,
            reasoning=reasoning
        )
        
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process response from OpenRouter API"""
        try:
            # Log full response for debugging
            self.logger.debug("Full API Response:")
            self.logger.debug(json.dumps(response, indent=2))
            
            # Handle API errors first
            if "error" in response:
                await self._handle_error(response)
            
            # Validate response structure
            if "choices" not in response:
                self.logger.error("No choices in response")
                self.logger.error(f"Response structure: {json.dumps(response, indent=2)}")
                raise RuntimeError("Invalid response format from OpenRouter API")
                
            if not response["choices"]:
                self.logger.error("Empty choices array")
                self.logger.error(f"Response structure: {json.dumps(response, indent=2)}")
                raise RuntimeError("No completion choices from OpenRouter API")
                
            # Extract message and content
            assistant_message = response["choices"][0].get("message")
            if not assistant_message:
                self.logger.error("No message in first choice")
                self.logger.error(f"First choice: {json.dumps(response['choices'][0], indent=2)}")
                raise RuntimeError("Invalid message format from OpenRouter API")
                
            content = assistant_message.get("content")
            if not content:
                self.logger.error("Empty content in message")
                self.logger.error(f"Message: {json.dumps(assistant_message, indent=2)}")
                raise RuntimeError("Empty response content from OpenRouter API")
            
            # Log successful content
            self.logger.debug("Received content:")
            self.logger.debug(content)
            
            # Look for tool usage
            if "<tool>" in content and "<input>" in content and hasattr(self, "_tools"):
                # Extract tool name and input
                tool_match = re.search(r"<tool>(.*?)</tool>", content)
                input_match = re.search(r"<input>(.*?)</input>", content)
                thought_match = re.search(r"<think>(.*?)</think>", content)
                
                if tool_match and input_match:
                    tool_name = tool_match.group(1).strip()
                    tool_input = input_match.group(1).strip()
                    thought = thought_match.group(1).strip() if thought_match else ""
                    
                    # Handle unknown tools
                    if tool_name not in self._tools:
                        error_msg = f"Tool '{tool_name}' is not available. Available tools: {', '.join(self._tools.keys())}"
                        self.messages.append({
                            "role": "system",
                            "content": f"Error: {error_msg}"
                        })
                        # Let model try again
                        request_data = {
                            "model": self.model_id,
                            "messages": self.messages,
                            "temperature": self.config.temperature,
                            "max_tokens": self.config.max_tokens
                        }
                        response = await self._make_request(request_data)
                        return await self._process_response(response)
                    
                    # Execute valid tool
                    tool = self._tools[tool_name]
                    result = await tool.execute(tool_input)
                    
                    # Add tool interaction to conversation
                    self.messages.append({
                        "role": "assistant",
                        "content": f"{thought}\n\nUsing {tool_name}...\nInput: {tool_input}"
                    })
                    self.messages.append({
                        "role": "system",
                        "content": f"Tool output: {result}"
                    })
                    
                    # Let model process the result
                    request_data = {
                        "model": self.model_id,
                        "messages": self.messages,
                        "temperature": self.config.temperature,
                        "max_tokens": self.config.max_tokens
                    }
                    response = await self._make_request(request_data)
                    return await self._process_response(response)
            
            # No tool usage, treat as regular response
            self.messages.append(assistant_message)
            return content
                
        except KeyError as e:
            self.logger.error(f"Error processing response: {str(e)}")
            self.logger.error(f"Response structure: {json.dumps(response, indent=2)}")
            raise ValueError(f"Unexpected response format: {response}")
    
    async def _handle_error(self, error: Dict[str, Any]) -> None:
        """Handle OpenRouter API errors"""
        error_msg = error.get("error", {}).get("message", "Unknown API error")
        error_type = error.get("error", {}).get("type", "unknown")
        
        # Log full error details
        self.logger.error("OpenRouter API Error:")
        self.logger.error(f"Type: {error_type}")
        self.logger.error(f"Message: {error_msg}")
        self.logger.error(f"Full error: {json.dumps(error, indent=2)}")
        
        if "rate limit" in error_msg.lower():
            raise RuntimeError(f"Rate limit exceeded: {error_msg}")
        elif "invalid api key" in error_msg.lower():
            raise RuntimeError(f"Authentication error: {error_msg}")
        elif "model" in error_msg.lower():
            raise RuntimeError(f"Model error: {error_msg}")
        elif "invalid request" in error_msg.lower():
            raise RuntimeError(f"Invalid request: {error_msg}")
        else:
            raise RuntimeError(f"API error ({error_type}): {error_msg}")
    
    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to OpenRouter API"""
        headers = self._get_headers()
        
        try:
            async with aiohttp.ClientSession() as session:
                self.logger.debug(f"Making request to: {self.base_url}/chat/completions")
                self.logger.debug(f"Request data: {json.dumps(request_data, indent=2)}")
                
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=request_data
                ) as response:
                    result = await response.json()
                    
                    if response.status != 200:
                        self.logger.error(f"API Error (Status {response.status}):")
                        self.logger.error(f"Response headers: {dict(response.headers)}")
                        self.logger.error(f"Response body: {json.dumps(result, indent=2)}")
                        self.logger.error(f"Request data: {json.dumps(request_data, indent=2)}")
                        await self._handle_error(result)
                    
                    self.logger.debug(f"API Response: {json.dumps(result, indent=2)}")
                    return result
                    
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error: {str(e)}")
            self.logger.error(f"Request data: {json.dumps(request_data, indent=2)}")
            raise RuntimeError(f"Failed to connect to OpenRouter API: {str(e)}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON response: {str(e)}")
            self.logger.error(f"Request data: {json.dumps(request_data, indent=2)}")
            raise RuntimeError("Invalid response format from OpenRouter API")
    
    async def generate(self, prompt: str) -> str:
        """Generate a response using OpenRouter API"""
        # Simple state transition
        await self.transition_to_active()
        
        try:
            request_data = await self._prepare_request(prompt)
            response = await self._make_request(request_data)
            return await self._process_response(response)
        finally:
            # Always return to IDLE
            await self.transition_to_idle()
    
    def clear_history(self) -> None:
        """Clear conversation history"""
        self.messages = []
        if self.config.system_prompt:
            self.messages.append({
                "role": "system",
                "content": self.config.system_prompt
            })
            # Reconfigure tools to update prompt
            self._configure_tools()
    
    async def cleanup(self) -> None:
        """Cleanup provider resources"""
        self.clear_history()
        await super().exit_field()
    
    def __str__(self) -> str:
        """String representation"""
        status = super().__str__()
        return f"{status} | Model: {self.model_id}"
