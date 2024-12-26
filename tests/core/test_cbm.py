# tests/core/test_cbm.py

# ==================== Imports ====================
import pytest
from datetime import timedelta
from src.glue.core.model import Model
from src.glue.core.cbm import CBM
from src.glue.core.binding import BindingConfig

# ==================== Fixtures ====================
@pytest.fixture
def basic_cbm():
    return CBM(name="test-cbm")

@pytest.fixture
def sample_models():
    model1 = Model("model1", "openrouter", "test-key1")
    model2 = Model("model2", "anthropic", "test-key2")
    model3 = Model("model3", "perplexity", "test-key3")
    return [model1, model2, model3]

# ==================== Initialization Tests ====================
def test_cbm_initialization(basic_cbm):
    """Test basic CBM initialization"""
    assert basic_cbm.name == "test-cbm"
    assert hasattr(basic_cbm, 'orchestrator')
    assert hasattr(basic_cbm, 'memory_manager')

# ==================== Model Management Tests ====================
@pytest.mark.asyncio
async def test_add_model(basic_cbm, sample_models):
    """Test adding models to CBM"""
    model = sample_models[0]
    await basic_cbm.add_model(model)
    assert model.name in basic_cbm.orchestrator.state.models

# ==================== Binding Tests ====================
@pytest.mark.asyncio
async def test_bind_models(basic_cbm, sample_models):
    """Test binding models with different binding types"""
    model1, model2 = sample_models[0:2]
    await basic_cbm.add_model(model1)
    await basic_cbm.add_model(model2)
    
    # Test permanent binding
    config = BindingConfig(
        type="permanent",
        source=model1.name,
        target=model2.name,
        properties={
            "strength": 1.0,
            "bidirectional": True
        }
    )
    await basic_cbm.add_model(model1, [config])
    
    # Verify binding was created
    assert len(basic_cbm.orchestrator.state.bindings) == 1
    binding = basic_cbm.orchestrator.state.bindings[0]
    assert binding.config.source == model1.name
    assert binding.config.target == model2.name

# ==================== Temporary Binding Tests ====================
@pytest.mark.asyncio
async def test_temporary_binding(basic_cbm, sample_models):
    """Test temporary binding expiration"""
    model1, model2 = sample_models[0:2]
    await basic_cbm.add_model(model1)
    await basic_cbm.add_model(model2)
    
    # Create a temporary binding
    config = BindingConfig(
        type="temporary",
        source=model1.name,
        target=model2.name,
        properties={
            "duration_ms": 50
        }
    )
    await basic_cbm.add_model(model1, [config])
    
    # Give time for binding to expire
    import time
    time.sleep(0.1)
    
    # Verify binding was removed
    assert len(basic_cbm.orchestrator.state.bindings) == 0

# ==================== Error Handling Tests ====================
@pytest.mark.asyncio
async def test_invalid_binding_type(basic_cbm, sample_models):
    """Test that invalid binding types raise ValueError"""
    model1, model2 = sample_models[0:2]
    await basic_cbm.add_model(model1)
    await basic_cbm.add_model(model2)
    
    config = BindingConfig(
        type="invalid_type",
        source=model1.name,
        target=model2.name
    )
    
    with pytest.raises(ValueError):
        await basic_cbm.add_model(model1, [config])

@pytest.mark.asyncio
async def test_bind_nonexistent_model(basic_cbm, sample_models):
    """Test binding with nonexistent model raises ValueError"""
    model = sample_models[0]
    await basic_cbm.add_model(model)
    
    config = BindingConfig(
        type="permanent",
        source=model.name,
        target="nonexistent_model"
    )
    
    with pytest.raises(ValueError):
        await basic_cbm.add_model(model, [config])

# ==================== Input Processing Tests ====================
@pytest.mark.asyncio
async def test_process_input(basic_cbm, sample_models):
    """Test processing user input through the CBM"""
    model1, model2 = sample_models[0:2]
    await basic_cbm.add_model(model1)
    await basic_cbm.add_model(model2)
    
    # Add dependency
    basic_cbm.orchestrator.add_dependency(model2.name, model1.name)
    
    # Process input
    response = await basic_cbm.process_input("Test input")
    assert response is not None
    
    # Verify memory storage
    memory_key = f"{model1.name}_input_"
    stored_inputs = [k for k in basic_cbm.orchestrator.memory_manager.memory.keys() if k.startswith(memory_key)]
    assert len(stored_inputs) == 1

# ==================== Serialization Tests ====================
@pytest.mark.asyncio
async def test_cbm_serialization(basic_cbm, sample_models):
    """Test converting CBM to and from dictionary"""
    model1, model2 = sample_models[0:2]
    await basic_cbm.add_model(model1)
    await basic_cbm.add_model(model2)
    
    config = BindingConfig(
        type="permanent",
        source=model1.name,
        target=model2.name
    )
    await basic_cbm.add_model(model1, [config])
    
    # Test to_dict
    cbm_dict = basic_cbm.to_dict()
    assert cbm_dict['name'] == basic_cbm.name
    assert len(cbm_dict['models']) == 2
    assert len(cbm_dict['bindings']) == 1
    
    # Test from_dict
    new_cbm = CBM.from_dict(cbm_dict)
    assert new_cbm.name == basic_cbm.name
    assert len(new_cbm.orchestrator.state.models) == 2
