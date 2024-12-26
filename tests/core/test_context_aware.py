# tests/core/test_context_aware.py

"""Tests for context-aware behavior"""

import pytest
from typing import Dict, Any, List
from dataclasses import dataclass
from glue.core.conversation import ConversationManager
from glue.core.context import InteractionType
from glue.core.model import Model
from glue.tools.web_search import WebSearchTool
from glue.tools.file_handler import FileHandlerTool
from glue.tools.search_providers import SearchProvider, register_provider

@dataclass
class MockSearchResult:
    """Mock search result for testing"""
    title: str
    snippet: str
    url: str

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary format"""
        return {
            "title": self.title,
            "snippet": self.snippet,
            "url": self.url
        }

class MockSearchProvider(SearchProvider):
    """Mock search provider for testing"""
    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key)
        
    async def search(self, query: str, max_results: int = 5, **kwargs) -> List[MockSearchResult]:
        """Return mock search results"""
        return [
            MockSearchResult(
                title="Test Result",
                snippet=f"Search results for: {query}",
                url="https://test.com"
            )
        ]
        
    async def initialize(self) -> None:
        """Mock initialization"""
        pass
        
    async def cleanup(self) -> None:
        """Mock cleanup"""
        pass

# Register mock provider
register_provider("test", MockSearchProvider)

class MockWebSearchTool(WebSearchTool):
    """Mock web search tool for testing"""
    def __init__(self):
        super().__init__(
            api_key="test_key",
            provider="test",
            magnetic=True
        )

class MockFileHandlerTool(FileHandlerTool):
    """Mock file handler tool for testing"""
    def __init__(self):
        super().__init__(
            magnetic=True,
            workspace_dir="test_workspace"
        )
        
    async def _execute(self, content: str, **kwargs) -> Dict[str, Any]:
        """Mock execution that returns operation details"""
        return {
            "success": True,
            "operation": "write",
            "format": "text",
            "path": f"test_workspace/{content}.txt"
        }

class MockModel(Model):
    """Mock model for testing"""
    def __init__(self, name: str, provider: str):
        super().__init__(name=name, provider=provider)
        self.tools = []  # Initialize tools list

    async def generate(self, prompt: str) -> str:
        if "hello" in prompt.lower():
            return "Hi! How can I help you today?"
        if "search" in prompt.lower() or "research" in prompt.lower():
            return "Let me search for that information."
        return "I'll help with that task."

@pytest.fixture
def conversation():
    """Create a conversation manager for testing"""
    return ConversationManager(sticky=False)

@pytest.fixture
def models():
    """Create test models"""
    model = MockModel("test", "test")
    model.set_role("You are a helpful assistant")
    # Add tools to model
    model.tools = ["web_search", "file_handler"]
    return {
        "assistant": model
    }

@pytest.fixture
def tools():
    """Create test tools"""
    return {
        "web_search": MockWebSearchTool(),
        "file_handler": MockFileHandlerTool()
    }

@pytest.mark.asyncio
async def test_chat_mode_skips_tools(conversation, models, tools):
    """Test that chat mode skips unnecessary tool use"""
    # Simple greeting should not use tools
    response = await conversation.process(
        models=models,
        binding_patterns={"tape": [("assistant", "web_search")]},
        user_input="hello",
        tools=tools
    )
    
    assert "Hi!" in response
    assert len([h for h in conversation.history if h["role"] == "tool"]) == 0

@pytest.mark.asyncio
async def test_research_mode_uses_tools(conversation, models, tools):
    """Test that research mode uses appropriate tools"""
    # Research request should use web_search
    response = await conversation.process(
        models=models,
        binding_patterns={"tape": [("assistant", "web_search")]},
        user_input="research quantum computing",
        tools=tools
    )
    
    assert len([h for h in conversation.history if h["role"] == "tool"]) > 0

@pytest.mark.asyncio
async def test_role_adaptation(conversation, models, tools):
    """Test that roles adapt based on context"""
    # First a chat interaction
    await conversation.process(
        models=models,
        binding_patterns={"tape": [("assistant", "web_search")]},
        user_input="hello",
        tools=tools
    )
    
    chat_role = conversation.model_roles["assistant"]
    assert not chat_role.tools_enabled
    
    # Then a research interaction
    await conversation.process(
        models=models,
        binding_patterns={"tape": [("assistant", "web_search")]},
        user_input="research quantum computing",
        tools=tools
    )
    
    research_role = conversation.model_roles["assistant"]
    assert research_role.tools_enabled

@pytest.mark.asyncio
async def test_tool_optimization(conversation, models, tools):
    """Test that tool chains are optimized"""
    # Complex task that could use multiple tools
    response = await conversation.process(
        models=models,
        binding_patterns={
            "tape": [
                ("assistant", "web_search"),
                ("web_search", "file_handler")
            ]
        },
        user_input="research quantum computing and save a summary",
        tools=tools
    )
    
    # Check tool usage was recorded
    assert len(conversation.tool_usage) > 0
    
    # Check tool chain was optimized
    tool_stats = conversation.tool_optimizer.get_chain_stats(
        ["web_search", "file_handler"]
    )
    assert tool_stats is not None
    assert tool_stats["success_rate"] > 0

@pytest.mark.asyncio
async def test_learning_from_interactions(conversation, models, tools):
    """Test that system learns from interactions"""
    # Perform several interactions
    inputs = [
        "hello",
        "research quantum computing",
        "hello again",
        "research artificial intelligence"
    ]
    
    for user_input in inputs:
        await conversation.process(
            models=models,
            binding_patterns={"tape": [("assistant", "web_search")]},
            user_input=user_input,
            tools=tools
        )
    
    # Check that patterns were learned
    summary = conversation.memory_manager.get_learning_summary()
    assert summary["total_patterns"] > 0
    assert InteractionType.CHAT.name in summary["context_distribution"]
    assert InteractionType.RESEARCH.name in summary["context_distribution"]

@pytest.mark.asyncio
async def test_context_aware_memory(conversation, models, tools):
    """Test that memory is context-aware"""
    # Research interaction
    await conversation.process(
        models=models,
        binding_patterns={"tape": [("assistant", "web_search")]},
        user_input="research quantum computing",
        tools=tools
    )
    
    # Chat interaction
    await conversation.process(
        models=models,
        binding_patterns={"tape": [("assistant", "web_search")]},
        user_input="hello",
        tools=tools
    )
    
    # Check memory segments have context
    for segment in conversation.memory_manager.short_term.values():
        assert hasattr(segment, "context")
        content = segment.content
        if isinstance(content, dict):
            content_str = content.get("content", "")
        else:
            content_str = str(content)
            
        if "research" in content_str.lower():
            assert segment.context.interaction_type == InteractionType.RESEARCH
        if "hello" in content_str.lower():
            assert segment.context.interaction_type == InteractionType.CHAT
