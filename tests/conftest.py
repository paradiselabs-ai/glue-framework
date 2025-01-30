"""Common test fixtures and configuration"""

import os
import pytest
import pytest_asyncio
from pathlib import Path

# Configure pytest-asyncio
pytest_asyncio.fixture_scope = "function"

# Add project root to Python path
project_root = Path(__file__).parent.parent
os.environ["PYTHONPATH"] = str(project_root)

@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment"""
    # Create test workspace
    os.makedirs("workspace/test", exist_ok=True)
    
    # Set test environment variables only if they don't exist
    if not os.getenv("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = "test_key"
    if not os.getenv("SERP_API_KEY"):
        os.environ["SERP_API_KEY"] = "test_key"
    
    yield
    
    # Cleanup test workspace
    if os.path.exists("workspace/test"):
        import shutil
        shutil.rmtree("workspace/test")

@pytest.fixture
def test_workspace():
    """Get test workspace path"""
    return "workspace/test"

@pytest.fixture
def test_config():
    """Test configuration"""
    return {
        "development": True,
        "sticky": False
    }

@pytest.fixture
def test_env():
    """Test environment variables"""
    return {
        "OPENROUTER_API_KEY": "test_key",
        "SERP_API_KEY": "test_key"
    }
