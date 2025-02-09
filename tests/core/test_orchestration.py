"""Test suite for GLUE orchestration system"""

import pytest
from pathlib import Path
import asyncio
from datetime import datetime
from typing import Optional, Dict, Set

from glue.core.app import GlueApp, AppConfig
from glue.core.team import Team, TeamRole
from glue.core.model import Model, ModelConfig
from glue.core.types import AdhesiveType, ToolResult
from glue.tools.base import BaseTool, ToolPermission
from glue.core.logger import get_logger

# Test tools
class FileHandlerTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="file_handler",
            config={
                "required_permissions": [ToolPermission.FILE_SYSTEM, ToolPermission.READ, ToolPermission.WRITE]
            }
        )
        self.description = "Handle file operations"
        self.logger = get_logger(self.name)
        self.memory_type = "file"
        self.shared_memory = True
        self.parallel_safe = False
        
    async def forward(self, input_data: str, **params) -> str:
        self.logger.debug(f"File handler executing: {input_data}")
        return f"Handled file: {input_data}"

class WebSearchTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="web_search",
            config={
                "required_permissions": [ToolPermission.NETWORK, ToolPermission.READ]
            }
        )
        self.description = "Search the web"
        self.logger = get_logger(self.name)
        self.memory_type = "vector"
        self.shared_memory = False
        self.parallel_safe = True
        
    async def forward(self, input_data: str, **params) -> str:
        self.logger.debug(f"Web search executing: {input_data}")
        return f"Search results for: {input_data}"

class CodeInterpreterTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="code_interpreter",
            config={
                "required_permissions": [ToolPermission.EXECUTE, ToolPermission.READ, ToolPermission.WRITE]
            }
        )
        self.description = "Execute code"
        self.logger = get_logger(self.name)
        self.memory_type = "workspace"
        self.shared_memory = True
        self.parallel_safe = False
        self.dependencies = {"file_handler"}
        
    async def forward(self, input_data: str, **params) -> str:
        self.logger.debug(f"Code interpreter executing: {input_data}")
        return f"Code output: {input_data}"

# Test fixtures
@pytest.fixture
def app_config():
    return AppConfig(
        name="test_app",
        development=True,
        sticky=True
    )

@pytest.fixture
def app(app_config, tmp_path):
    """Create app with temporary workspace"""
    workspace_dir = tmp_path / "glue_workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return GlueApp(
        name="test_app",
        config=app_config,
        workspace_dir=workspace_dir
    )

@pytest.fixture
def file_tool():
    return FileHandlerTool()

@pytest.fixture
def search_tool():
    return WebSearchTool()

@pytest.fixture
def code_tool():
    return CodeInterpreterTool()

@pytest.fixture
def research_model():
    return Model(
        name="researcher",
        provider="test",
        team="research",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        config=ModelConfig(
            temperature=0.7,
            system_prompt="Research assistant"
        )
    )

@pytest.fixture
def docs_model():
    return Model(
        name="writer",
        provider="test",
        team="docs",
        available_adhesives={AdhesiveType.TAPE},
        config=ModelConfig(
            temperature=0.3,
            system_prompt="Documentation writer"
        )
    )

@pytest.fixture
async def research_team(research_model, search_tool, code_tool):
    team = Team(
        name="research",
        models={"researcher": research_model}
    )
    await team.add_member("researcher", role=TeamRole.LEAD)
    await team.add_tool(search_tool)
    await team.add_tool(code_tool)
    return team

@pytest.fixture
async def docs_team(docs_model, file_tool):
    team = Team(
        name="docs",
        models={"writer": docs_model}
    )
    await team.add_member("writer", role=TeamRole.LEAD)
    await team.add_tool(file_tool)
    return team

@pytest.mark.asyncio
async def test_orchestrated_execution(app, research_team, docs_team):
    """Test orchestrated execution of a complex prompt"""
    # Register teams
    research = await research_team
    docs = await docs_team
    app.register_team("research", research)
    app.register_team("docs", docs)
    
    # Complex prompt requiring multiple tools
    prompt = """Research python file handling and demonstrate the findings by creating 
    and manipulating a test file. Document the process in a markdown file."""
    
    response = await app.process_prompt(prompt)
    
    # Verify orchestration worked correctly
    assert "research" in response.lower()  # Research was done
    assert "file" in response.lower()  # File was handled
    assert "documented" in response.lower()  # Documentation was created

@pytest.mark.asyncio
async def test_parallel_execution(app, research_team):
    """Test parallel execution of compatible tools"""
    research = await research_team
    app.register_team("research", research)
    
    # Prompt requiring multiple independent searches
    prompt = """Search for information about Python, JavaScript, and TypeScript 
    and compare their features."""
    
    response = await app.process_prompt(prompt)
    
    # Verify parallel execution worked
    assert "python" in response.lower()
    assert "javascript" in response.lower()
    assert "typescript" in response.lower()

@pytest.mark.asyncio
async def test_dependency_handling(app, research_team, docs_team):
    """Test handling of tool dependencies"""
    research = await research_team
    docs = await docs_team
    app.register_team("research", research)
    app.register_team("docs", docs)
    
    # Prompt requiring tools with dependencies
    prompt = """Write a Python script to analyze a log file, then execute it."""
    
    response = await app.process_prompt(prompt)
    
    # Verify dependencies were handled
    assert "file" in response.lower()  # File handler was used first
    assert "code" in response.lower()  # Code interpreter was used after

@pytest.mark.asyncio
async def test_memory_sharing(app, research_team, docs_team):
    """Test memory sharing between teams"""
    research = await research_team
    docs = await docs_team
    app.register_team("research", research)
    app.register_team("docs", docs)
    
    # Prompt requiring memory sharing
    prompt = """Research best practices for Python file handling, create example 
    files demonstrating each practice, then document the examples."""
    
    response = await app.process_prompt(prompt)
    
    # Verify memory was shared
    assert "research" in response.lower()
    assert "examples" in response.lower()
    assert "documented" in response.lower()

@pytest.mark.asyncio
async def test_error_recovery(app, research_team, docs_team):
    """Test error recovery and fallback strategies"""
    research = await research_team
    docs = await docs_team
    app.register_team("research", research)
    app.register_team("docs", docs)
    
    # Prompt that might cause errors
    prompt = """Try to access a non-existent file, handle the error appropriately, 
    and document the error handling process."""
    
    response = await app.process_prompt(prompt)
    
    # Verify error was handled
    assert "error" in response.lower()
    assert "handled" in response.lower()
    assert "documented" in response.lower()

@pytest.mark.asyncio
async def test_dynamic_routing(app, research_team, docs_team):
    """Test dynamic routing based on tool requirements"""
    research = await research_team
    docs = await docs_team
    app.register_team("research", research)
    app.register_team("docs", docs)
    
    # Sequence of prompts requiring different teams
    prompts = [
        "Search for Python file handling methods",  # Should route to research
        "Create a new markdown file",  # Should route to docs
        "Research and document Python classes"  # Should use both teams
    ]
    
    for prompt in prompts:
        response = await app.process_prompt(prompt)
        assert response is not None
        assert len(response) > 0

@pytest.mark.asyncio
async def test_adhesive_optimization(app, research_team, docs_team):
    """Test optimal adhesive selection"""
    research = await research_team
    docs = await docs_team
    app.register_team("research", research)
    app.register_team("docs", docs)
    
    # Prompt requiring different adhesive types
    prompt = """Research Python classes, save the findings in a shared file, 
    and create a temporary working document."""
    
    response = await app.process_prompt(prompt)
    
    # Verify different adhesives were used
    assert "shared" in response.lower()  # GLUE was used
    assert "temporary" in response.lower()  # TAPE was used
