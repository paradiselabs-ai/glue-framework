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
from glue.core.logger import get_logger

# Configure logging
logger = init_logger(
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
        # Start research task
        logger.debug("Sending research prompt")
        result = await app.process_prompt(
            "Research quantum computing advancements in 2024"
        )
        logger.debug(f"Got prompt result: {result}")
        
        # Get teams and models
        logger.debug("Getting research team resources")
        researchers = app.get_field_resources("researchers")
        logger.debug(f"Research team members: {[r.name for r in researchers]}")
        
        researcher = next(r for r in researchers if r.name == "researcher")
        logger.debug(f"Lead researcher: {researcher}")
        
        assistant = next(r for r in researchers if r.name == "assistant")
        logger.debug(f"Assistant: {assistant}")
        
        logger.debug("Getting docs team resources")
        docs = app.get_field_resources("docs")
        logger.debug(f"Docs team members: {[d.name for d in docs]}")
        
        writer = next(r for r in docs if r.name == "writer")
        logger.debug(f"Writer: {writer}")
        
        # Test researcher team's web search results
        logger.debug("Getting research team's web search results")
        research_results = app.get_team_results("researchers", "web_search")
        logger.debug(f"Research results: {research_results}")
        assert research_results is not None, "Research results should not be None"
        assert "quantum computing" in str(research_results).lower(), "Research results should contain 'quantum computing'"
        
        # Test magnetic push: researchers -> docs
        logger.debug("Testing magnetic push from researchers to docs")
        docs_received = app.get_team_received("docs", "researchers")
        logger.debug(f"Docs received: {docs_received}")
        assert docs_received is not None, "Docs team should receive data"
        assert docs_received == research_results, "Docs team should receive research results"
        
        # Test file creation by docs team
        logger.debug("Testing file creation by docs team")
        assert any(Path("workspace").glob("*.md")), "Docs team should create markdown files"
        
        # Verify file content includes research data
        logger.debug("Verifying file content")
        md_files = list(Path("workspace").glob("*.md"))
        assert len(md_files) > 0, "At least one markdown file should be created"
        with open(md_files[0]) as f:
            content = f.read()
            logger.debug(f"File content: {content}")
            assert "quantum computing" in content.lower(), "File should contain research content"
        
        logger.info("Research workflow test completed successfully")
    except Exception as e:
        logger.error(f"Error in research workflow test: {str(e)}", exc_info=True)
        raise

@pytest.mark.asyncio
async def test_magnetic_pull(app):
    """Test docs team pulling data from researchers"""
    # Have researchers generate some data
    await app.process_prompt(
        "Research AI advancements briefly"
    )
    
    # Clear docs team received data
    app.clear_team_received("docs")
    
    # Simulate docs team pulling data
    pulled_data = await app.pull_team_data("docs", "researchers")
    
    # Verify pulled data
    assert pulled_data is not None
    assert "AI" in str(pulled_data).lower()

@pytest.mark.asyncio
async def test_team_data_flow(app):
    """Test complete team data flow with magnetic interactions"""
    # Initial research task
    await app.process_prompt(
        "Research neural networks briefly"
    )
    
    # Get initial research data
    research_data = app.get_team_results("researchers", "web_search")
    assert research_data is not None
    
    # Test automatic push to docs
    docs_data = app.get_team_received("docs", "researchers")
    assert docs_data is not None
    assert docs_data == research_data
    
    # Test docs team processing
    md_files = list(Path("workspace").glob("*.md"))
    assert len(md_files) > 0
    
    # Verify data flow through the system
    with open(md_files[0]) as f:
        content = f.read()
        assert "neural networks" in content.lower()

@pytest.mark.asyncio
async def test_persistence_cleanup(app):
    """Test cleanup with sticky config"""
    # Run some operations
    await app.process_prompt("Quick quantum computing research")
    
    # Get memory count
    memory_count = len(app.get_memory())
    
    # Cleanup
    await app.cleanup()
    
    # Verify sticky behavior
    assert len(app.get_memory()) == memory_count  # Memory persists with sticky=true

@pytest.mark.asyncio
async def test_team_persistence(app):
    """Test team-wide persistence and tool data handling"""
    # Initial research
    await app.process_prompt(
        "Research quantum computing basics"
    )
    
    # Get initial tool results
    initial_results = app.get_team_results("researchers", "web_search")
    
    # Run another research task
    await app.process_prompt(
        "Now research quantum entanglement"
    )
    
    # Verify previous results still accessible
    persisted_results = app.get_team_history("researchers", "web_search")
    assert len(persisted_results) >= 2
    assert "quantum computing" in str(persisted_results[0]).lower()
    assert "quantum entanglement" in str(persisted_results[1]).lower()

@pytest.mark.asyncio
async def test_conversation_memory(app):
    """Test multi-turn conversation memory"""
    # Initial research
    await app.process_prompt(
        "Research quantum computing"
    )
    
    # Follow-up questions
    await app.process_prompt(
        "What did we research in the previous prompt?"
    )
    memory = app.get_memory()
    assert "quantum computing" in str(memory[-2]).lower()
    
    # Test specific memory retrieval
    await app.process_prompt(
        "What did we research three prompts ago?"
    )
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
    # Initial setup
    await app.process_prompt("Research quantum computing")
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
        
        # Test continued operation
        await new_app.process_prompt("Continue the quantum computing research")
        assert len(new_app.get_memory()) > len(memory)
    finally:
        await new_app.cleanup()

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
