"""Simplified Conversation Manager"""

import os
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from .logger import get_logger

class SimpleConversationManager:
    """
    Simplified conversation manager focused on basic tool execution.
    
    Features:
    - Basic conversation history
    - Simple tool execution
    - Minimal state management
    """
    
    def __init__(self, sticky: bool = False, workspace_dir: Optional[str] = None):
        """Initialize conversation manager"""
        self.sticky = sticky
        self.workspace_dir = os.path.abspath(workspace_dir or "workspace")
        self.history: List[Dict[str, Any]] = []
        self.logger = get_logger()
        
        # Load history if sticky
        if self.sticky:
            self._load_history()

    def _extract_tool_usage(self, response: str) -> Optional[Tuple[str, str, str]]:
        """Extract tool name, thought, and input from response"""
        # Look for tool usage pattern
        tool_match = re.search(r'<tool>(.*?)</tool>', response)
        input_match = re.search(r'<input>(.*?)</input>', response)
        thought_match = re.search(r'<think>(.*?)</think>', response)
        
        if tool_match and input_match:
            tool_name = tool_match.group(1).strip()
            tool_input = input_match.group(1).strip()
            thought = thought_match.group(1).strip() if thought_match else ""
            return (tool_name, thought, tool_input)
            
        return None

    async def process(
        self,
        models: Dict[str, Any],
        binding_patterns: Dict[str, Any],
        user_input: str,
        tools: Optional[Dict[str, Any]] = None
    ) -> str:
        """Process user input through models and tools"""
        try:
            # Store user input
            message = {
                "role": "user",
                "content": user_input,
                "timestamp": datetime.now().isoformat()
            }
            self.history.append(message)
            
            # Process through first model
            if not models:
                return "No models available"
                
            model = next(iter(models.values()))
            current_input = user_input
            
            while True:  # Allow multiple tool uses
                # Get model's response
                response = await model.generate(current_input)
                
                # Check for tool usage
                tool_usage = self._extract_tool_usage(response)
                if tool_usage and tools:
                    tool_name, thought, tool_input = tool_usage
                    
                    # Log the attempt
                    self.logger.debug(f"Tool usage detected: {tool_name}")
                    self.logger.debug(f"Thought: {thought}")
                    self.logger.debug(f"Input: {tool_input}")
                    
                    # Store assistant's thought and tool request
                    self.history.append({
                        "role": "assistant",
                        "content": f"{thought}\n\nUsing {tool_name}...\nInput: {tool_input}",
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Execute tool if available
                    if tool_name in tools:
                        try:
                            tool = tools[tool_name]
                            result = await tool.execute(tool_input)
                            
                            # Store tool result
                            self.history.append({
                                "role": "system",
                                "content": f"Tool output: {result}",
                                "timestamp": datetime.now().isoformat()
                            })
                            
                            # Update input for next iteration
                            current_input = f"Tool output: {result}"
                            continue
                            
                        except Exception as e:
                            error = f"Tool execution failed: {str(e)}"
                            self.logger.error(error)
                            # Store error and break
                            self.history.append({
                                "role": "system",
                                "content": f"Error: {error}",
                                "timestamp": datetime.now().isoformat()
                            })
                            return error
                    else:
                        error = f"Tool not available: {tool_name}"
                        self.logger.error(error)
                        # Store error and break
                        self.history.append({
                            "role": "system",
                            "content": f"Error: {error}",
                            "timestamp": datetime.now().isoformat()
                        })
                        return error
                
                # No tool usage, store final response
                self.history.append({
                    "role": "assistant",
                    "content": response,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Save if sticky
                if self.sticky:
                    self._save_history()
                
                return response
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self.logger.error(error_msg)
            self.history.append({
                "role": "error",
                "content": error_msg,
                "timestamp": datetime.now().isoformat()
            })
            if self.sticky:
                self._save_history()
            return error_msg

    def _get_history_path(self) -> str:
        """Get history file path"""
        os.makedirs(self.workspace_dir, exist_ok=True)
        return os.path.join(self.workspace_dir, "chat_history.json")

    def _save_history(self) -> None:
        """Save history if sticky"""
        if not self.sticky:
            return
        
        path = self._get_history_path()
        with open(path, 'w') as f:
            json.dump(self.history, f, indent=2)

    def _load_history(self) -> None:
        """Load history if sticky"""
        if not self.sticky:
            return
            
        path = self._get_history_path()
        if os.path.exists(path):
            with open(path, 'r') as f:
                self.history = json.load(f)

    def get_history(self) -> List[Dict[str, Any]]:
        """Get conversation history"""
        return self.history

    def clear_history(self) -> None:
        """Clear history"""
        self.history = []
        if self.sticky:
            path = self._get_history_path()
            if os.path.exists(path):
                os.remove(path)

    def save_state(self) -> Dict[str, Any]:
        """Save manager state"""
        state = {"history": self.history}
        if self.sticky:
            self._save_history()
        return state

    def load_state(self, state: Dict[str, Any]) -> None:
        """Load manager state"""
        if self.sticky:
            self._load_history()
        else:
            self.history = state.get("history", [])
