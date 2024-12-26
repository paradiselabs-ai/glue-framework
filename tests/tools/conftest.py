# tests/tools/conftest.py

import pytest
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
    
    async def _execute(self, **kwargs) -> str:
        """Test execution that returns a string"""
        self.execute_called = True
        return "executed"

@pytest.fixture
def TestTool():
    """Fixture that provides the MockTool class"""
    return MockTool
