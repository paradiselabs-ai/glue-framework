# tests/core/test_model.py
import pytest
from glue.core.model import Model, ModelConfig

@pytest.fixture
def basic_model():
    return Model(
        name="test-model",
        provider="openrouter",
        api_key="test-key"
    )

def test_model_initialization(basic_model):
    """Test basic model initialization"""
    assert basic_model.name == "test-model"
    assert basic_model.provider == "openrouter"
    assert basic_model.api_key == "test-key"
    assert isinstance(basic_model.config, ModelConfig)

def test_prompt_management(basic_model):
    """Test adding and retrieving prompts"""
    basic_model.add_prompt("system", "You are an AI assistant")
    assert basic_model.get_prompt("system") == "You are an AI assistant"
    assert basic_model.get_prompt("nonexistent") is None

def test_role_setting(basic_model):
    """Test setting model role"""
    basic_model.set_role("analyzer")
    assert basic_model.role == "analyzer"

def test_tool_management(basic_model):
    """Test adding tools"""
    tool = {"name": "calculator", "func": lambda x: x + 1}
    basic_model.add_tool("calculator", tool)
    assert "calculator" in basic_model._tools
    assert basic_model._tools["calculator"] == tool

def test_model_binding(basic_model):
    """Test binding to another model"""
    other_model = Model("other-model", "anthropic", "other-key")
    basic_model.bind_to(other_model, "glue")
    assert "other-model" in basic_model._bound_models
    assert basic_model._bound_models["other-model"] == other_model

def test_model_config():
    """Test model configuration"""
    config = ModelConfig(
        temperature=0.5,
        max_tokens=2000,
        top_p=0.9
    )
    model = Model("test", "openrouter", config=config)
    assert model.config.temperature == 0.5
    assert model.config.max_tokens == 2000
    assert model.config.top_p == 0.9

@pytest.mark.asyncio
async def test_generate_not_implemented(basic_model):
    """Test that generate raises NotImplementedError"""
    with pytest.raises(NotImplementedError):
        await basic_model.generate("test prompt")