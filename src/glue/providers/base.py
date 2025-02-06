"""GLUE Provider Base System

This base class intentionally maintains features that are essential for a framework:
- Model inheritance: Required for model capabilities and type safety
- Workspace formatting: Needed for providing tool context to models
- Team context: Required for multi-model collaboration
- Conversation history: Needed for context preservation
- Detailed system prompts: Required for consistent model behavior

While these features add complexity, they are necessary for a robust framework
that others will use to build AI applications. This is different from a simple
provider base that might be used in a single application.
"""

from typing import Dict, Any, Optional, List, Set
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
        provider: str,
        team: str,
        available_adhesives: Set[AdhesiveType],
        api_key: str,
        config: Optional[ModelConfig] = None,
        base_url: Optional[str] = None
    ):
        super().__init__(
            name=name,
            provider=provider,
            team=team,
            available_adhesives=available_adhesives,
            api_key=api_key,
            config=config
        )
        self.base_url = base_url
        self._session = None
        self._conversation_history = []

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

Available Tools:
{workspace_context}

How to Use Tools:
1. Express your intentions naturally when using tools. For example:
   - "Let me search the web for information about that topic"
   - "I'll save these findings to a file for later reference"
   - "I can run some Python code to analyze this data"

2. Choose the right adhesive type:
   - GLUE: Share results with team (use for research and important findings)
     Example: "I'll search for this information and share it with the team"
   
   - VELCRO: Keep results for your session
     Example: "I'll save this data for my own reference during this session"
   
   - TAPE: One-time use, no persistence
     Example: "Let me quickly check something using the code interpreter"

3. Tool-Specific Examples:
   - web_search: "I'll search for recent articles about machine learning"
   - file_handler: "Let me save these results to a file called 'research.txt'"
   - code_interpreter: "I can analyze this data using Python"

4. Team Communication:
   - Share important findings with the team
   - Use team context to coordinate with others
   - Keep track of shared knowledge

Remember: Be clear about your intentions when using tools, and specify if you want to share results with the team (GLUE), keep them for your session (VELCRO), or just use them once (TAPE)."""

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
        if not self._validate_api_key():
            raise ValueError("Invalid API key")
            
        try:
            # Prepare and validate request
            request_data = await self._prepare_request(prompt)
            if not request_data:
                raise ValueError("Failed to prepare request")
                
            # Make request with retry support
            max_retries = 1  # Allow one retry for fallback
            for attempt in range(max_retries + 1):
                try:
                    response = await self._make_request(request_data)
                    result = await self._process_response(response)
                    if result:
                        return result
                except ValueError as e:
                    if "Retrying with fallback" in str(e) and attempt < max_retries:
                        # Update request data with new model
                        request_data = await self._prepare_request(prompt)
                        continue
                    raise
                except Exception as e:
                    await self._handle_error(e)
                    raise
            
            raise ValueError("Failed to generate response after retries")
            
        except ValueError as e:
            # Log error and re-raise ValueError
            if hasattr(self, 'logger'):
                self.logger.error(f"Generation failed for {self.name}: {str(e)}")
            raise
        except Exception as e:
            # Log error details and convert to RuntimeError
            error_msg = f"Generation failed for {self.name}: {str(e)}"
            if hasattr(self, 'logger'):
                self.logger.error(error_msg)
            raise RuntimeError(error_msg)

    @abstractmethod
    async def _make_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Make the actual API request"""
        pass

    @abstractmethod
    async def _handle_error(self, error: Exception) -> None:
        """Handle provider-specific errors"""
        pass

    # ==================== Utility Methods ====================
    def _validate_api_key(self) -> bool:
        """Validate the API key format"""
        if not self.api_key:
            return False
        if not isinstance(self.api_key, str):
            return False
        if len(self.api_key.strip()) == 0:
            return False
        return True

    def _get_headers(self) -> Dict[str, str]:
        """Get the common headers for API requests"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def cleanup(self) -> None:
        """Clean up provider resources"""
        self._conversation_history = []
        if self._session:
            await self._session.close()
            self._session = None
