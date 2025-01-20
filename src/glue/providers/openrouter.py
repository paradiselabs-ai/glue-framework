"""OpenRouter Provider Implementation"""

import os
import re
import json
import aiohttp
from typing import Dict, List, Any, Optional, Set
from .base import BaseProvider
from ..core.model import ModelConfig
from ..core.logger import get_logger
from ..core.resource import Resource, ResourceState
from ..core.types import IntentAnalysis

class OpenRouterProvider(BaseProvider, Resource):
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
            "HTTP-Referer": "https://github.com/paradiseLabs-ai/glue-framework"
        }
        return headers

    def _configure_tools(self) -> None:
        """Configure tools and update system prompt"""
        if not hasattr(self, "_tools"):
            self._tools = {}
            
        # If inheriting from parent, copy tools and role
        if hasattr(self, "_parent"):
            parent = self._parent
            self._tools = parent._tools.copy()
            self.role = parent.role
            self.config.system_prompt = parent.config.system_prompt
            
        # Update system prompt with tool info
        if self._tools and self.messages and self.messages[0]["role"] == "system":
            system_prompt = self.messages[0]["content"]
            tool_info = "\n\nDo not assume you lack access to tools. You can check what tools are available and determine if you need them. Here are your available tools:\n"
            for name, tool in self._tools.items():
                tool_info += f"- {name}: {tool.description}\n"
            
            tool_info += """
When you need to use a tool:
1. Think through what you need to do
2. Use the tool in this format:
<think>your reasoning</think>
<tool>tool_name</tool>
<input>your input</input>

Always wait for tool output before continuing."""
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
        BaseProvider.__init__(
            self,
            name=model,  # Use model ID for API calls
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            config=config,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # Initialize resource
        Resource.__init__(
            self,
            name=name or model,
            category="provider",
            tags={"provider", "openrouter", model}
        )
        
        # Store model ID separately
        self.model_id = model
        
        if not self.api_key:
            raise ValueError("OpenRouter API key not found")
        
        # Initialize logger
        self.logger = get_logger()
        
        # Initialize conversation history
        self.messages: List[Dict[str, str]] = []
        
        # Set initial state to IDLE
        self._state = ResourceState.IDLE
        
        # Initialize system prompt
        if system_prompt:
            self.logger.debug(f"Initializing with system prompt: {system_prompt}")
            self.messages.append({
                "role": "system",
                "content": system_prompt
            })
            
        # Configure tools (will update system prompt if needed)
        self._configure_tools()
    
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
            self.logger.debug(f"Processing response:\n{json.dumps(response, indent=2)}")
            
            assistant_message = response["choices"][0]["message"]
            content = assistant_message["content"]
            
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
    
    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make request to OpenRouter API"""
        headers = self._get_headers()
        
        async with aiohttp.ClientSession() as session:
            self.logger.debug(f"Making request to: {self.base_url}/chat/completions")
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=request_data
            ) as response:
                result = await response.json()
                
                if response.status != 200:
                    self.logger.error(f"API Error (Status {response.status}):")
                    self.logger.error(json.dumps(result, indent=2))
                    await self._handle_error(result)
                
                return result
    
    async def generate(self, prompt: str) -> str:
        """Generate a response using OpenRouter API"""
        # Check state
        if (self.state not in {ResourceState.IDLE, ResourceState.ACTIVE, ResourceState.SHARED} and 
            self.metadata.category != "tool"):
            # Try fallback if available
            if hasattr(self, "_parent"):
                self.logger.info(f"Model {self.name} busy, attempting fallback...")
                fallback = OpenRouterProvider(
                    api_key=self.api_key,
                    model=self.model_id,
                    system_prompt=self.config.system_prompt,
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    name=f"{self.name}_fallback"
                )
                # Set parent for tool and role inheritance
                fallback._parent = self
                # Configure tools and update prompt
                fallback._configure_tools()
                return await fallback.generate(prompt)
            raise RuntimeError(f"Provider {self.name} is busy (state: {self.state.name})")
        
        # Transition to ACTIVE for generation
        if self.state == ResourceState.IDLE:
            self._state = ResourceState.ACTIVE
        
        try:
            request_data = await self._prepare_request(prompt)
            response = await self._make_request(request_data)
            return await self._process_response(response)
        finally:
            # Return to IDLE if we were IDLE before
            if self._state == ResourceState.ACTIVE:
                self._state = ResourceState.IDLE
    
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
