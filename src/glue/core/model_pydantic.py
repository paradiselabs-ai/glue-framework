"""Model implementation with Pydantic and Prefect integration"""

from typing import Dict, Any, Optional, List, Set, Union, TYPE_CHECKING
from datetime import datetime
import logging
from prefect import task, flow

from .pydantic_models import (
    ModelConfig, ModelState, ToolResult, ToolBinding,
    ConversationMessage, TeamContext, SmolAgentsTool
)
from .types import AdhesiveType, IntentAnalysis
from .logger import get_logger

if TYPE_CHECKING:
    from .team_pydantic import Team

logger = get_logger("model")

class Model:
    """Base class for models that can use tools and communicate"""
    def __init__(
        self, 
        name: str,
        provider: str,
        team: str,
        available_adhesives: Set[AdhesiveType],
        api_key: Optional[str] = None,
        config: Optional[ModelConfig] = None
    ):
        # Initialize model state using Pydantic
        self.state = ModelState(
            name=name,
            provider=provider,
            team=team,
            available_adhesives=available_adhesives,
            config=config or ModelConfig(),
        )
        self.api_key = api_key
        
        # Initialize SmolAgents tool registry
        self._smol_tools: Dict[str, SmolAgentsTool] = {}
        
        # Reference to team instance (set by team when adding model)
        self._team: Optional['Team'] = None
        
        # Set up logging
        self.logger = logger

    @property
    def team(self) -> Optional['Team']:
        """Get the model's team"""
        return self._team

    @team.setter
    def team(self, team: 'Team') -> None:
        """Set the model's team"""
        self._team = team
        self.state.team = team.name

    def set_role(self, role: str) -> None:
        """Set the model's role"""
        self.state.role = role
        if not self.state.config.system_prompt:
            self.state.config = ModelConfig(
                temperature=self.state.config.temperature,
                max_tokens=self.state.config.max_tokens,
                top_p=self.state.config.top_p,
                presence_penalty=self.state.config.presence_penalty,
                frequency_penalty=self.state.config.frequency_penalty,
                stop_sequences=self.state.config.stop_sequences,
                system_prompt=role,
                provider_config=self.state.config.provider_config
            )

    @task(retries=3, retry_delay_seconds=10)
    async def use_tool(self, tool_name: str, adhesive: AdhesiveType, input_data: Any) -> ToolResult:
        """Use tools naturally like office tools"""
        # Validate tool access
        if not self.team:
            raise ValueError(f"Model {self.state.name} is not part of a team")
            
        if tool_name not in self.team.tools:
            raise ValueError(f"Tool {tool_name} not available in team {self.team.name}")
            
        if tool_name not in self._smol_tools:
            raise ValueError(f"Tool {tool_name} not bound to model {self.state.name}")
            
        # Validate adhesive
        if adhesive not in self.state.available_adhesives:
            raise ValueError(f"Model {self.state.name} cannot use {adhesive.name} adhesive")
            
        # Get tool binding
        binding = self.team.tool_bindings.get(tool_name)
        if not binding:
            binding = ToolBinding(
                tool_name=tool_name,
                adhesive=adhesive
            )
            self.team.tool_bindings[tool_name] = binding
            
        # Track tool usage
        self.logger.info(f"Model {self.state.name} using tool {tool_name} with {adhesive.name}")
            
        # Execute tool using SmolAgents
        smol_tool = self._smol_tools[tool_name]
        try:
            result = await smol_tool.forward_func(input_data)
        except Exception as e:
            self.logger.error(f"Tool execution failed: {str(e)}")
            raise
        
        # Create tool result
        tool_result = ToolResult(
            tool_name=tool_name,
            result=result,
            adhesive=adhesive,
            timestamp=datetime.now()
        )
        
        # Handle result based on adhesive
        if adhesive == AdhesiveType.GLUE:
            # Store in team's shared context
            self.team.context.shared_results[tool_name] = tool_result
        elif adhesive == AdhesiveType.VELCRO:
            # Store in session results
            self.state.session_results[tool_name] = tool_result
        
        # Log result
        self.logger.info(f"Tool {tool_name} execution successful")
            
        return tool_result

    def _store_interaction(self, content: Any, interaction_type: str = "message") -> None:
        """Store an interaction in conversation history"""
        message = ConversationMessage(
            type=interaction_type,
            content=content,
            team=self.state.team,
            tools_used=[t.tool_name for t in list(self.state.session_results.values())[-3:]]
        )
        self.state.conversation_history.append(message)

    def _get_relevant_context(self) -> Dict[str, Any]:
        """Get relevant context from history and team"""
        return {
            "recent_history": self.state.conversation_history[-3:],
            "recent_tools": list(self.state.session_results.values())[-3:],
            "team": {
                "name": self.state.team,
                "shared_knowledge": self.team.context.shared_knowledge if self.team else {},
                "shared_results": self.team.context.shared_results if self.team else {}
            }
        }

    def _get_available_tools(self) -> List[str]:
        """Get list of available tools"""
        return list(self._smol_tools.keys())

    @flow(name="process_prompt")
    async def process(self, prompt: str) -> str:
        """Process a prompt naturally like a team member would"""
        # Store the interaction
        self._store_interaction(prompt)
        
        # Consider the context naturally
        context = self._get_relevant_context()
        self.logger.debug(f"Context for {self.state.name}:\n{context}")
        
        # Generate response with natural thinking
        response = await self.generate(prompt)
        self.logger.info(f"\nModel {self.state.name} generated response:\n{response}")
            
        # Check if response indicates tool usage
        if any(tool_name in response.lower() for tool_name in self._smol_tools.keys()):
            # Initialize SmolAgents tool executor
            from ..tools.executor import SmolAgentsToolExecutor
            executor = SmolAgentsToolExecutor(
                team=self.team,
                available_adhesives=self.state.available_adhesives
            )
            
            try:
                # Let SmolAgents handle tool execution
                self.logger.info(f"Tool usage detected, using SmolAgents executor")
                result = await executor.execute(response)
                self.logger.info(f"Tool execution successful:\n{result.result}")
                
                # Handle result based on adhesive type
                if result.adhesive == AdhesiveType.GLUE:
                    self.logger.info(f"Sharing result with team using GLUE")
                    await self.team.share_result(result.tool_name, result)
                elif result.adhesive == AdhesiveType.VELCRO:
                    self.logger.info(f"Storing result in session using VELCRO")
                    self.state.session_results[result.tool_name] = result
                    
                return str(result.result)
                
            except Exception as e:
                self.logger.error(f"Tool execution failed: {str(e)}")
                # Fall back to natural response
                return response
        else:
            # No tool usage detected, return natural chat response
            self.logger.debug("No tool usage detected, using natural chat response")
            return response

    @task(retries=2)
    async def send_message(self, receiver: str, content: Any) -> None:
        """Send a message to another model"""
        if not self.team:
            raise ValueError(f"Model {self.state.name} is not part of a team")
            
        if receiver in self.state.repelled_by:
            raise ValueError(f"Cannot send message to {receiver} - repelled")
            
        # Message sending handled by Team class
        await self.team.send_message(self.state.name, receiver, content)
        
    async def receive_message(self, sender: str, content: Any) -> None:
        """Receive a message from another model"""
        if sender in self.state.repelled_by:
            raise ValueError(f"Cannot receive message from {sender} - repelled")
            
        # Process message (to be implemented by provider)
        await self.process_message(sender, content)
        
    async def process_message(self, sender: str, content: Any) -> None:
        """Process a received message from another team member"""
        if isinstance(content, dict) and content.get('type') == 'tool_result':
            # Store tool result in shared results if using GLUE
            tool_name = content.get('tool')
            result = content.get('result')
            if tool_name and result:
                tool_result = ToolResult(
                    tool_name=tool_name,
                    result=result,
                    adhesive=AdhesiveType.GLUE,
                    timestamp=datetime.now()
                )
                if self.team:
                    self.team.context.shared_results[tool_name] = tool_result
        
    async def generate(self, prompt: str) -> str:
        """Generate a response (to be implemented by provider)"""
        raise NotImplementedError
