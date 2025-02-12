"""Test research assistant application flow"""

import os
import pytest
import pytest_asyncio
from pathlib import Path

import logging

# Core imports
from glue.core.app import GlueApp
from glue.core.types import AdhesiveType
from glue.core.team import Team
from glue.core.model import Model
from glue.core.tool_binding import ToolBinding
from glue.core.context import ContextAnalyzer, ContextState
from glue.core.conversation import ConversationManager
from glue.core.memory import MemoryManager
from glue.core.workspace import WorkspaceManager
from glue.core.group_chat import GroupChatManager
from glue.core.state import StateManager, StateContext
from glue.core.logger import get_logger, setup_logging

# Configure logging
logger = setup_logging(
    name="test_research_assistant",
    log_dir=".",
    development=True
)

# Provider imports
from glue.providers.base import BaseProvider
from glue.providers.openrouter import OpenRouterProvider


# Magnetic imports
from glue.magnetic.field import MagneticField
from glue.magnetic.rules import InteractionPattern, AttractionPolicy, RuleSet

# DSL imports
from glue.cli import parse_glue_file
from glue.dsl.executor import execute_glue_app
from glue.dsl.parser import GlueAppConfig

# Tool imports
from glue.tools.base import BaseTool
from glue.tools.web_search import WebSearchTool
from glue.tools.code_interpreter import CodeInterpreterTool
from glue.tools.file_handler import FileHandlerTool
from glue.tools.search_providers.serp import SerpSearchProvider

# Adhesive imports
from glue.adhesive.tool import AdhesiveTool

@pytest.fixture
def app_config():
    """Load research assistant app config"""
    app_path = Path("examples/research_assistant.glue")
    return parse_glue_file(app_path)

@pytest_asyncio.fixture
async def app(app_config):
    """Get running app instance"""
    logger.info("Setting up app fixture")
    try:
        logger.debug("Executing GLUE app")
        app = await execute_glue_app(app_config)
        logger.info("App initialized successfully")
        yield app
        logger.debug("Cleaning up app")
        await app.cleanup()
        logger.info("App cleanup complete")
    except Exception as e:
        logger.error(f"Error in app fixture: {str(e)}", exc_info=True)
        raise

def test_app_config(app_config):
    """Test application configuration"""
    assert app_config.name == "Research Assistant"
    assert app_config.config.get("development") is True
    assert app_config.config.get("sticky") is True  # Persistence enabled

def test_tool_config(app_config):
    """Test tool configuration"""
    # Verify tool definitions
    tools = app_config.tool_configs
    assert "web_search" in tools
    assert tools["web_search"].provider == "serp"
    assert "file_handler" in tools
    assert "code_interpreter" in tools

def test_model_config(app_config):
    """Test model configuration"""
    models = app_config.model_configs
    
    # Test researcher model
    researcher = models["researcher"]
    assert researcher.provider == "openrouter"
    assert researcher.config["model"] == "meta-llama/llama-3.1-70b-instruct:free"
    assert researcher.config["temperature"] == 0.7
    assert AdhesiveType.GLUE in researcher.config["adhesives"]
    assert AdhesiveType.VELCRO in researcher.config["adhesives"]
    
    # Test assistant model
    assistant = models["assistant"]
    assert assistant.provider == "openrouter"
    assert assistant.config["model"] == "meta-llama/llama-3.1-70b-instruct:free"
    assert assistant.config["temperature"] == 0.5
    assert AdhesiveType.GLUE in assistant.config["adhesives"]
    assert AdhesiveType.VELCRO in assistant.config["adhesives"]
    
    # Test writer model
    writer = models["writer"]
    assert writer.provider == "openrouter"
    assert writer.config["model"] == "meta-llama/llama-3.1-70b-instruct:free"
    assert writer.config["temperature"] == 0.3
    assert AdhesiveType.TAPE in writer.config["adhesives"]

def test_team_config(app_config):
    """Test team structure configuration"""
    workflow = app_config.workflow
    
    # Test researchers team
    researchers = workflow.teams["researchers"]
    assert researchers.lead == "researcher"
    assert len(researchers.members) == 1
    assert researchers.members[0] == "assistant"
    assert "web_search" in researchers.tools
    assert "code_interpreter" in researchers.tools
    
    # Test docs team
    docs = workflow.teams["docs"]
    assert docs.lead == "writer"
    assert "web_search" in docs.tools
    assert "file_handler" in docs.tools

def test_magnetic_config(app_config):
    """Test magnetic field configuration"""
    workflow = app_config.workflow
    
    # Test push capability (researchers -> docs)
    assert ("researchers", "docs") in workflow.attractions
    
    # Test pull capability (docs <- pull)
    assert ("docs", "pull") in workflow.pulls

@pytest.mark.asyncio
async def test_research_workflow(app):
    """Test complete research workflow with magnetic interactions"""
    logger.info("Starting research workflow test")
    try:
        # Test the full research workflow
        result = await app.process_prompt(
            "Research quantum computing advancements in 2024 and create a summary"
        )
        
        # Verify the response contains relevant content
        assert result is not None
        assert "quantum" in result.lower() or "computing" in result.lower()
        
        # Verify a markdown file was created with the summary
        md_files = list(Path("workspace").glob("*.md"))
        assert len(md_files) > 0
        
        # Verify file content
        with open(md_files[0]) as f:
            content = f.read()
            assert "quantum" in content.lower() or "computing" in content.lower()
        
        logger.info("Research workflow test completed successfully")
    except Exception as e:
        logger.error(f"Error in research workflow test: {str(e)}", exc_info=True)
        raise

@pytest.mark.asyncio
async def test_magnetic_pull(app):
    """Test docs team pulling data from researchers"""
    # Test the full pull workflow
    result = await app.process_prompt(
        "Research AI advancements and have the docs team pull the information"
    )
    
    # Verify the response contains relevant content
    assert result is not None
    assert "AI" in result.lower() or "artificial intelligence" in result.lower()
    
    # Verify a markdown file was created
    md_files = list(Path("workspace").glob("*.md"))
    assert len(md_files) > 0
    
    # Verify file content shows the pulled data was used
    with open(md_files[0]) as f:
        content = f.read()
        assert "AI" in content.lower() or "artificial intelligence" in content.lower()

@pytest.mark.asyncio
async def test_team_data_flow(app):
    """Test complete team data flow with magnetic interactions"""
    # Test the full team data flow
    result = await app.process_prompt(
        "Research neural networks and have the teams collaborate on a summary"
    )
    
    # Verify the response contains relevant content
    assert result is not None
    assert "neural" in result.lower() or "networks" in result.lower()
    
    # Verify a markdown file was created
    md_files = list(Path("workspace").glob("*.md"))
    assert len(md_files) > 0
    
    # Verify file content shows team collaboration
    with open(md_files[0]) as f:
        content = f.read()
        assert "neural" in content.lower() or "networks" in content.lower()

@pytest.mark.asyncio
async def test_persistence_cleanup(app):
    """Test cleanup with sticky config"""
    # Add test data directly to memory
    app.add_to_memory("Test data 1")
    app.add_to_memory("Test data 2")
    
    # Get memory count
    memory_count = len(app.get_memory())
    
    # Cleanup
    await app.cleanup()
    
    # Verify sticky behavior
    assert len(app.get_memory()) == memory_count  # Memory persists with sticky=true

@pytest.mark.asyncio
async def test_team_persistence(app):
    """Test team-wide persistence and tool data handling"""
    # Add test data directly to team results
    app.add_team_result("researchers", "web_search", "Test quantum computing data")
    app.add_team_result("researchers", "web_search", "Test quantum entanglement data")
    
    # Verify results are persisted
    persisted_results = app.get_team_history("researchers", "web_search")
    assert len(persisted_results) >= 2
    assert "quantum computing" in str(persisted_results[0]).lower()
    assert "quantum entanglement" in str(persisted_results[1]).lower()

@pytest.mark.asyncio
async def test_conversation_memory(app):
    """Test multi-turn conversation memory"""
    # Add test prompts directly to memory
    app.add_to_memory("Research quantum computing")
    app.add_to_memory("What did we research?")
    app.add_to_memory("Tell me more about quantum computing")
    
    memory = app.get_memory()
    assert "quantum computing" in str(memory[0]).lower()
    assert len(memory) >= 3
    assert app.can_recall_prompt(2)  # Can recall 3 prompts ago

@pytest.mark.asyncio
async def test_cli_tools(app):
    """Test GLUE CLI tool listing"""
    from glue.cli import list_tools
    from click.testing import CliRunner
    
    runner = CliRunner()
    
    # Test list-tools command
    result = runner.invoke(list_tools)
    assert result.exit_code == 0
    assert "web_search" in result.output
    assert "file_handler" in result.output
    assert "code_interpreter" in result.output

@pytest.mark.asyncio
async def test_sticky_persistence(app):
    """Test app-level persistence with sticky flag"""
    # Add test data directly
    app.add_to_memory("Test quantum computing research")
    app.add_team_result("researchers", "web_search", "Test research results")
    initial_state = app.get_state()
    
    # Save app state
    app.save_state()
    
    # Create new app instance
    new_app = await execute_glue_app(app_config)
    
    try:
        # Verify state restored
        restored_state = new_app.get_state()
        assert restored_state == initial_state
        
        # Verify teams restored
        researchers = new_app.get_field_resources("researchers")
        assert researchers is not None
        assert len(researchers) > 0
        
        # Verify memory restored
        memory = new_app.get_memory()
        assert "quantum computing" in str(memory[-1]).lower()
        
        # Verify tool results restored
        research_results = new_app.get_team_results("researchers", "web_search")
        assert research_results is not None
        assert "research results" in str(research_results).lower()
    finally:
        await new_app.cleanup()

@pytest.mark.asyncio
async def test_internal_team_sharing(app):
    """Test sharing tool results between team members"""
    # Test that researcher's GLUE results are shared with assistant
    result = await app.process_prompt(
        "Research quantum computing and have the researcher share findings with assistant"
    )
    
    # Get researcher's shared results
    researcher = app.models["researcher"]
    assistant = app.models["assistant"]
    
    # Verify assistant received the shared results
    assert len(assistant._team_context) > 0
    assert any("web_search" in key for key in assistant._team_context.keys())
    
    # Verify results were stored with GLUE adhesive
    team = app.teams["researchers"]
    assert len(team.shared_results) > 0
    assert any("web_search" in key for key in team.shared_results.keys())

@pytest.mark.asyncio
async def test_final_result_display(app):
    """Test that only final results are shown to user"""
    # Test file operation result
    result = await app.process_prompt(
        "Research quantum computing and save to a file"
    )
    
    # Verify only the file operation result is shown
    assert result.startswith("File saved at")
    assert "<think>" not in result
    assert "<tool>" not in result
    assert "<adhesive>" not in result
    assert "<input>" not in result
    
    # Test tool usage result
    result = await app.process_prompt(
        "What are the latest developments in AI?"
    )
    
    # Verify only the final summary is shown
    assert "<think>" not in result
    assert "<tool>" not in result
    assert "<adhesive>" not in result
    assert "<input>" not in result

@pytest.mark.asyncio
async def test_error_handling(app):
    """Test error handling"""
    # Test invalid field
    with pytest.raises(ValueError):
        app.get_field_resources("nonexistent_field")
    
    # Test invalid prompt
    with pytest.raises(ValueError):
        await app.process_prompt("")  # Empty prompt
    
    # Test invalid memory limit
    with pytest.raises(ValueError):
        app.get_memory(limit=0)  # Invalid limit
