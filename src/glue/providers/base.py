# src/glue/providers/base.py

# ==================== Imports ====================
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime
from ..core.model import Model, ModelConfig
from ..core.types import AdhesiveType, ToolResult

# ==================== Base Provider Class ====================
class BaseProvider(Model, ABC):
    """Base class for all provider implementations"""
    def __init__(
        self,
        name: str,
        api_key: str,
        config: Optional[ModelConfig] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            name=name,
            provider=self.__class__.__name__,
            api_key=api_key,
            config=config
        )
        self.base_url = base_url
        self._session = None

    # ==================== Abstract Methods ====================
    def _format_workspace(self) -> str:
        """Format available tools like a physical workspace"""
        tools = []
        for name, tool in self._tools.items():
            desc = tool.description if hasattr(tool, 'description') else name
            tools.append(f"- {name}: {desc}")
        return "\n".join(tools) if tools else "No tools available"

    def _format_team_context(self) -> str:
        """Format team info like an org chart"""
        if not hasattr(self, "team") or not self.team:
            return "Working independently"
            
        members = []
        if hasattr(self.team, 'members'):
            for name, role in self.team.members.items():
                members.append(f"- {name}: {role}")
        return "\n".join(members) if members else "No team members"

    def _format_conversation(self) -> str:
        """Format recent conversation history"""
        if not self._conversation_history:
            return "No previous conversation"
            
        recent = self._conversation_history[-3:]  # Last 3 interactions
        formatted = []
        for interaction in recent:
            content = interaction.get('content', '')
            formatted.append(f"- {content}")
        return "\n".join(formatted)

    @abstractmethod
    async def _prepare_request(self, prompt: str) -> Dict[str, Any]:
        """Prepare the request payload for the API"""
        # Build natural context
        workspace_context = self._format_workspace()
        team_context = self._format_team_context()
        conversation_context = self._format_conversation()
        
        system_prompt = f"""You are {self.name}, working in the {self.team} team.

Your role: {self.role}

Your workspace:
{workspace_context}

Your team:
{team_context}

Recent conversation:
{conversation_context}

Work naturally with your team. If you need to use a tool, think about why you need it and use it like you would use any tool in your workspace."""

        return {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        }

    @abstractmethod
    async def _process_response(self, response: Dict[str, Any]) -> str:
        """Process the API response into a string"""
        pass

    # ==================== Shared Methods ====================
    async def generate(self, prompt: str) -> str:
        """Generate a response using the provider's API"""
        try:
            request_data = await self._prepare_request(prompt)
            response = await self._make_request(request_data)
            return await self._process_response(response)
        except Exception as e:
            raise RuntimeError(f"Generation failed: {str(e)}")

    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make the actual API request"""
        raise NotImplementedError("Provider must implement _make_request")

    async def _handle_error(self, error: Exception) -> None:
        """Handle provider-specific errors"""
        raise NotImplementedError("Provider must implement _handle_error")

    # ==================== Utility Methods ====================
    def _validate_api_key(self) -> bool:
        """Validate the API key format"""
        return bool(self.api_key and isinstance(self.api_key, str))

    def _get_headers(self) -> Dict[str, str]:
        """Get the common headers for API requests"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
