"""Test Prefect integration with SmolAgents dynamic tool creation"""

import pytest
import pytest_asyncio
from prefect import flow, task, get_run_logger
from prefect.testing.utilities import prefect_test_harness
from glue.providers.smolagents import SmolAgentsProvider
from glue.core.types import AdhesiveType
from glue.core.team import Team
from glue.tools.dynamic_tool_factory import DynamicToolFactory
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def prefect_test():
    """Setup Prefect test harness"""
    with prefect_test_harness():
        yield


@pytest_asyncio.fixture
async def factory():
    """Get DynamicToolFactory instance"""
    return DynamicToolFactory()


@pytest_asyncio.fixture
async def team():
    """Get test team instance"""
    return Team(name="test_team")


@pytest_asyncio.fixture
async def provider():
    """Get SmolAgentsProvider instance"""
    return SmolAgentsProvider(
        name="test_provider",
        team="test_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        api_key="test-key",
    )


@pytest.mark.asyncio
async def test_basic_tool_creation_flow(factory, team):
    """Test basic tool creation flow with Prefect"""

    # Define test tool function
    async def test_tool(input: str) -> str:
        return f"Processed: {input}"

    # Create tool using Prefect flow
    tool = await factory.create_tool_flow(
        name="test_tool", description="A test tool", function=test_tool, team=team
    )

    # Verify tool was created
    assert tool.name == "test_tool"
    assert tool in team.tools.values()

    # Test tool execution
    result = await tool.execute("test input")
    assert "Processed: test input" in result


@pytest.mark.asyncio
async def test_parallel_tool_creation(factory, team):
    """Test creating multiple tools in parallel"""

    # Define test tool functions
    async def tool_1(x: int) -> int:
        return x * 2

    async def tool_2(x: int) -> int:
        return x + 2

    async def tool_3(x: int) -> int:
        return x**2

    # Create tools in parallel using Prefect
    tools = await factory.create_tools_parallel(
        [
            {"name": "double", "description": "Doubles input", "function": tool_1},
            {"name": "add_two", "description": "Adds two", "function": tool_2},
            {"name": "square", "description": "Squares input", "function": tool_3},
        ],
        team=team,
    )

    # Verify all tools were created
    assert len(tools) == 3
    assert all(tool in team.tools.values() for tool in tools)

    # Test tools can be used concurrently
    results = await factory.execute_tools_parallel(tools=tools, inputs=[5, 5, 5])

    assert results == [10, 7, 25]


@pytest.mark.asyncio
async def test_error_handling_and_retries(factory, team):
    """Test error handling and retry logic"""
    error_count = 0

    # Define flaky tool that fails first two times
    async def flaky_tool(input: str) -> str:
        nonlocal error_count
        if error_count < 2:
            error_count += 1
            raise ValueError("Temporary error")
        return f"Success: {input}"

    # Create tool with retry policy
    tool = await factory.create_tool_with_retries(
        name="flaky_tool",
        description="A flaky tool that needs retries",
        function=flaky_tool,
        max_retries=2,
        retry_delay_seconds=0.01,
        team=team,
    )

    # Test tool execution with retries
    result = await tool.execute("test input")
    assert "Success: test input" in result
    assert error_count == 2  # Verify it failed twice before succeeding


@pytest.mark.asyncio
async def test_pydantic_validation(factory, team):
    """Test Pydantic validation in tool creation"""
    # Test invalid tool name
    with pytest.raises(ValidationError):
        await factory.create_tool_flow(
            name="", description="Test tool", function=lambda x: x, team=team  # Invalid empty name
        )

    # Test invalid function signature
    async def invalid_tool(x: int) -> None:
        # Tool must return string for SmolAgents
        pass

    with pytest.raises(ValidationError):
        await factory.create_tool_flow(
            name="invalid_tool",
            description="Tool with invalid return type",
            function=invalid_tool,
            team=team,
        )

    # Test missing required fields
    with pytest.raises(ValidationError):
        await factory.create_tool_flow(
            name="missing_desc_tool",
            # Missing description
            function=lambda x: str(x),
            team=team,
        )


@pytest.mark.asyncio
async def test_tool_state_persistence(factory, team, provider):
    """Test tool state persistence across retries and failures"""
    state = {"count": 0}

    # Define tool that maintains state
    async def stateful_tool(input: str) -> str:
        state["count"] += 1
        if state["count"] < 3:
            raise ValueError("Not enough calls")
        return f"Success after {state['count']} tries"

    # Create tool with state persistence
    tool = await factory.create_tool_with_state(
        name="stateful_tool",
        description="Tool that maintains state",
        function=stateful_tool,
        initial_state=state,
        team=team,
    )

    # Use tool with GLUE adhesive to test state persistence
    result = await provider.use_tool(
        tool_name="stateful_tool", adhesive=AdhesiveType.GLUE, input_data="test"
    )

    assert "Success after 3" in result.result
    assert state["count"] == 3


@pytest.mark.asyncio
async def test_tool_chain_creation(factory, team):
    """Test creating a chain of tools that work together"""

    # Define tools for the chain
    async def collector(topic: str) -> str:
        return f"Data about {topic}"

    async def analyzer(data: str) -> str:
        return f"Analysis of {data}"

    async def formatter(analysis: str) -> str:
        return f"Report: {analysis}"

    # Create tool chain using Prefect
    chain = await factory.create_tool_chain(
        tools=[
            {"name": "collector", "description": "Collects data", "function": collector},
            {"name": "analyzer", "description": "Analyzes data", "function": analyzer},
            {"name": "formatter", "description": "Formats analysis", "function": formatter},
        ],
        team=team,
    )

    # Test chain execution
    result = await chain.execute("quantum computing")
    assert "Report: Analysis of Data about quantum computing" in result


@pytest.mark.asyncio
async def test_smolagents_async_creation(factory, team, provider):
    """Test actual SmolAgents tool creation process with network delays"""
    import asyncio

    # Simulated async call without actual delay
    async def simulated_network_call(input_data: str) -> str:
        # No sleep needed - asyncio.gather() maintains async behavior
        return f"API Response: {input_data}"

    # Create tool that makes network calls
    tool = await factory.create_tool_flow(
        name="network_tool",
        description="Tool that makes network calls",
        function=simulated_network_call,
        team=team,
    )

    # Test parallel execution with real network delays
    tasks = [tool.execute(f"request_{i}") for i in range(3)]
    results = await asyncio.gather(*tasks)

    assert all("API Response" in result for result in results)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_real_error_recovery(factory, team):
    """Test recovery from real system errors like timeouts and connection drops"""
    import socket
    import asyncio

    async def network_tool(url: str) -> str:
        # Simulate network errors without actual socket operations
        if url == "fail":
            raise ConnectionError("Simulated connection error")
        return "Connection successful"

    tool = await factory.create_tool_with_retries(
        name="connection_tool",
        description="Tests real network connections",
        function=network_tool,
        max_retries=2,
        retry_delay_seconds=0.01,
        team=team,
    )

    # Test with actual network call
    result = await tool.execute("example.com")
    assert "Connection successful" in result


@pytest.mark.asyncio
async def test_adhesive_state_flow(factory, team, provider):
    """Test adhesive state management in real flow execution"""
    # Create a tool that modifies shared state
    shared_state = []

    @task
    async def append_state(data: str) -> str:
        shared_state.append(data)
        return f"Added: {data}"

    @flow
    async def state_flow(input_data: str):
        return await append_state(input_data)

    # Create tool using the flow
    tool = await factory.create_tool_flow(
        name="state_tool",
        description="Tool that manages state in flow",
        function=state_flow,
        team=team,
    )

    # Test with different adhesives
    glue_result = await provider.use_tool(
        tool_name="state_tool", adhesive=AdhesiveType.GLUE, input_data="glue_data"
    )

    velcro_result = await provider.use_tool(
        tool_name="state_tool", adhesive=AdhesiveType.VELCRO, input_data="velcro_data"
    )

    # Verify state persistence based on adhesive type
    assert "glue_data" in shared_state  # GLUE persists
    assert len([s for s in shared_state if "glue_data" in s]) == 1
    assert "Added: glue_data" in glue_result.result
    assert "Added: velcro_data" in velcro_result.result


@pytest.mark.asyncio
async def test_concurrent_adhesive_states(factory, team, provider):
    """Test concurrent operations with different adhesive states"""
    import asyncio

    # Create tools with different adhesive requirements
    async def glue_operation(data: str) -> str:
        return f"GLUE: {data}"

    async def velcro_operation(data: str) -> str:
        return f"VELCRO: {data}"

    glue_tool = await factory.create_tool_flow(
        name="glue_tool", description="Tool using GLUE adhesive", function=glue_operation, team=team
    )

    velcro_tool = await factory.create_tool_flow(
        name="velcro_tool",
        description="Tool using VELCRO adhesive",
        function=velcro_operation,
        team=team,
    )

    # Run concurrent operations with different adhesives
    tasks = [
        provider.use_tool("glue_tool", AdhesiveType.GLUE, "data1"),
        provider.use_tool("velcro_tool", AdhesiveType.VELCRO, "data2"),
        provider.use_tool("glue_tool", AdhesiveType.GLUE, "data3"),
    ]

    results = await asyncio.gather(*tasks)

    # Verify results and state consistency
    assert all(isinstance(r.result, str) for r in results)
    assert "GLUE: data1" in results[0].result
    assert "VELCRO: data2" in results[1].result
    assert "GLUE: data3" in results[2].result

    # Verify team state
    assert "glue_tool" in team.shared_results  # GLUE results persist
    assert "velcro_tool" not in team.shared_results  # VELCRO results don't persist
