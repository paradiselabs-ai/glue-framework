# tests/tools/conftest.py

import pytest
from typing import Any
from src.glue.tools.magnetic import MagneticTool

class MockTool(MagneticTool):
    """Mock tool for testing"""
    def __init__(
        self,
        name: str = "test_tool",
        description: str = "Test tool for testing",
        magnetic: bool = True
    ):
        super().__init__(
            name=name,
            description=description,
            magnetic=magnetic
        )
        self.execute_called = False
    
    async def execute(self, **kwargs) -> str:
        """Test execution that returns a string"""
        await super().execute(**kwargs)
        self.execute_called = True
        return "executed"

@pytest.fixture
def TestTool():
    """Fixture that provides the MockTool class"""
    return MockTool
