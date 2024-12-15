"""Tests for Test agent"""

import pytest
from glue.agents.Test import TestAgent

@pytest.fixture
def agent():
    return TestAgent()

def test_agent_initialization(agent):
    assert agent.name == "Test"

@pytest.mark.asyncio
async def test_agent_processing(agent):
    # Add test cases here
    pass
