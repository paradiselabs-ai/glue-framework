"""Test suite for enhanced tool system with validation and logging"""

import pytest
from pathlib import Path
import asyncio
from datetime import datetime
from typing import Optional

from loguru import logger
from glue.core.types import AdhesiveType, ToolResult
from glue.tools.base import BaseTool, ToolConfig, ToolData
from glue.tools.executor import SmolAgentsToolExecutor, ToolIntent

# Test tool implementation
class TestTool(BaseTool):
    def __init__(self, name: str = "test_tool", description: str = "Test tool"):
        super().__init__(name=name, description=description)
        
    async def forward(self, input_data: str, **params) -> str:
        logger.debug(f"[{self.name}] Executing with input: {input_data}, params: {params}")
        return f"Test result: {input_data}"

from glue.core.team import Team, TeamRole
from glue.core.model import Model, ModelConfig

@pytest.fixture
def test_tool():
    return TestTool()

@pytest.fixture
def test_model(test_team):
    """Create a test model with proper team reference"""
    model = Model(
        name="test_model",
        provider="test",
        team=test_team.name,  # Use actual team name
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO, AdhesiveType.TAPE},
        config=ModelConfig(
            temperature=0.7,
            max_tokens=1000,
            system_prompt="Test model for tool execution"
        )
    )
    model.set_role("Test model for tool execution")
    return model

@pytest.fixture
async def test_team():
    """Create test team first so model can reference it"""
    return Team(name="test_team")

@pytest.fixture
async def configured_team(test_team, test_tool, test_model):
    """Configure team with model and tool"""
    # Add model and tool
    test_team.models = {"test_model": test_model}
    await test_team.add_member("test_model", role=TeamRole.LEAD)
    await test_team.add_tool(test_tool)
    return test_team

@pytest.fixture
def executor(configured_team):
    return SmolAgentsToolExecutor(
        team=configured_team,
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO, AdhesiveType.TAPE}
    )

@pytest.mark.asyncio
async def test_tool_execution_with_validation(executor, test_tool):
    """Test tool execution with input validation"""
    # Valid input
    result = await executor.execute(
        'Use test_tool with input "test data" using GLUE binding'
    )
    assert isinstance(result, ToolResult)
    assert result.tool_name == "test_tool"
    assert "test data" in result.result
    assert result.adhesive == AdhesiveType.GLUE

    # Invalid input (missing tool name)
    result = await executor.execute(
        'Just some random text without tool intent'
    )
    assert isinstance(result, str)
    assert result == 'Just some random text without tool intent'

@pytest.mark.asyncio
async def test_tool_creation_validation(executor):
    """Test dynamic tool creation with validation"""
    # Valid tool creation
    intent = ToolIntent(
        tool_name="new_tool",
        input_data="test input",
        adhesive=AdhesiveType.TAPE,
        description="A test tool"
    )
    tool = await executor._get_or_create_tool(intent)
    assert tool is not None
    assert tool.name == "new_tool"

    # Invalid tool (no description)
    invalid_intent = ToolIntent(
        tool_name="invalid_tool",
        input_data="test input",
        adhesive=AdhesiveType.TAPE
    )
    tool = await executor._get_or_create_tool(invalid_intent)
    assert tool is None

@pytest.mark.asyncio
async def test_adhesive_binding_behavior(executor, configured_team):
    """Test different adhesive binding behaviors"""
    
    # GLUE binding should share results
    result = await executor.execute(
        'Use test_tool with input "shared data" using GLUE binding'
    )
    assert len(configured_team.shared_results) == 1
    assert configured_team.shared_results["test_tool"].result == result.result

    # TAPE binding should not share results
    result = await executor.execute(
        'Use test_tool with input "private data" using TAPE binding'
    )
    assert len(configured_team.shared_results) == 1  # Still 1 from before

@pytest.mark.asyncio
async def test_logging_functionality(executor, configured_team):
    """Test logging functionality"""
    from loguru import logger
    import io
    import sys
    
    # Capture loguru output
    string_io = io.StringIO()
    logger.remove()
    logger.add(string_io, format="{message}")
    
    # Execute tool and check logs
    await executor.execute(
        'Use test_tool with input "log test" using VELCRO binding'
    )
    
    # Verify log content
    log_output = string_io.getvalue()
    assert "test_tool" in log_output
    assert "log test" in log_output
    assert "VELCRO" in log_output
    
    # Verify debug info
    debug_info = configured_team.debug.get_tool_debug_info()
    assert "test_tool" in debug_info.get("executed_tools", {})
    assert debug_info["executed_tools"]["test_tool"].get("success_count", 0) > 0
    assert debug_info["executed_tools"]["test_tool"].get("last_adhesive") == "VELCRO"
    
    # Cleanup
    logger.remove()
    logger.add(sys.stderr, format="{message}")

@pytest.mark.asyncio
async def test_error_handling_and_logging(executor, configured_team):
    """Test error handling and error logging"""
    from loguru import logger
    import io
    import sys
    import traceback
    
    # Capture loguru output
    string_io = io.StringIO()
    logger.remove()
    logger.add(string_io, format="{message}")
    
    try:
        # Try to use non-existent tool
        result = await executor.execute(
            'Use nonexistent_tool with input "test" using TAPE binding'
        )
        
        # Verify error handling
        assert isinstance(result, str)
        assert "not available" in result
        
        # Verify debug info
        debug_info = configured_team.debug.get_tool_debug_info()
        assert "nonexistent_tool" in debug_info.get("failed_tools", {})
        assert debug_info["failed_tools"]["nonexistent_tool"].get("error_count", 0) > 0
        
        # Simulate error with stack trace
        try:
            raise ValueError("Test error for stack trace")
        except Exception as e:
            from glue.core.logger import log_error
            log_error(
                error_type="ToolExecutionError",
                message="Failed to execute tool",
                component="tool",
                metadata={
                    "tool_name": "nonexistent_tool",
                    "adhesive": "TAPE",
                    "team": configured_team.name
                },
                severity="error",
                stack_trace=traceback.format_exc(),
                error_code="TOOL_001"
            )
        
        # Verify enhanced error logging
        log_output = string_io.getvalue()
        assert "ToolExecutionError [TOOL_001]" in log_output
        assert "Failed to execute tool" in log_output
        assert "Stack trace" in log_output
        assert "ValueError: Test error" in log_output
        assert "nonexistent_tool" in log_output
        assert "TAPE" in log_output
        
    finally:
        # Cleanup
        logger.remove()
        logger.add(sys.stderr, format="{message}")

@pytest.mark.asyncio
async def test_tool_config_validation():
    """Test tool configuration validation"""
    # Valid config
    valid_config = ToolConfig(
        required_permissions=[],
        timeout=30.0,
        retry_count=3,
        cache_results=True
    )
    assert valid_config.timeout == 30.0

    # Invalid config should raise validation error
    with pytest.raises(Exception):
        invalid_config = ToolConfig(
            required_permissions=[],
            timeout="invalid",  # Should be float
            retry_count=3,
            cache_results=True
        )

@pytest.mark.asyncio
async def test_tool_data_validation():
    """Test tool data validation"""
    # Valid data
    valid_data = ToolData(
        input_data="test input",
        params={"option": "value"}
    )
    assert valid_data.input_data == "test input"
    assert valid_data.params["option"] == "value"

    # Invalid data should raise validation error
    with pytest.raises(Exception):
        invalid_data = ToolData(
            input_data=123,  # Should be string
            params={"option": "value"}
        )
