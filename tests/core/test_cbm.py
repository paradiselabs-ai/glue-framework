# tests/core/test_cbm.py

# ==================== Imports ====================
import pytest
from datetime import datetime, timedelta
from src.glue.core.model import Model, ModelConfig
from src.glue.core.cbm import CBM
from src.glue.core.adhesive import AdhesiveProperties

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
    assert isinstance(basic_cbm.models, dict)
    assert isinstance(basic_cbm.bindings, dict)
    assert all(pattern in basic_cbm.bindings 
              for pattern in ['glue', 'velcro', 'tape', 'magnet'])
    # NEW: Test memory manager initialization
    assert hasattr(basic_cbm, 'memory_manager')

# ==================== Model Management Tests ====================
def test_add_model(basic_cbm, sample_models):
    """Test adding models to CBM"""
    model = sample_models[0]
    basic_cbm.add_model(model)
    assert model.name in basic_cbm.models
    assert basic_cbm.models[model.name] == model

# ==================== Binding Tests ====================
def test_bind_models(basic_cbm, sample_models):
    """Test binding models with different binding types"""
    model1, model2 = sample_models[0:2]
    basic_cbm.add_model(model1)
    basic_cbm.add_model(model2)
    
    # Test glue binding
    basic_cbm.bind_models(model1.name, model2.name, 'glue')
    active_bindings = basic_cbm.get_active_bindings()
    assert len(active_bindings['glue']) == 1
    assert active_bindings['glue'][0][0:2] == (model1.name, model2.name)
    
    # NEW: Test binding memory storage
    binding_memory = basic_cbm.memory_manager.shared[model1.name].get("binding_glue")
    assert binding_memory is not None
    assert binding_memory.content["type"] == "glue"
    
    # Test velcro binding
    model3 = sample_models[2]
    basic_cbm.add_model(model3)
    properties = AdhesiveProperties(
        strength=0.5,
        durability=0.5,
        flexibility=0.5,
        is_reusable=True
    )
    basic_cbm.bind_models(model2.name, model3.name, 'velcro', properties)
    active_bindings = basic_cbm.get_active_bindings()
    assert len(active_bindings['velcro']) == 1
    binding = active_bindings['velcro'][0]
    assert binding[0:2] == (model2.name, model3.name)
    assert binding[2] == 0.5 # check custom strength

# ==================== Temporary Binding Tests ====================
def test_temporary_binding(basic_cbm, sample_models):
    """Test temporary binding expiration"""
    model1, model2 = sample_models[0:2]
    basic_cbm.add_model(model1)
    basic_cbm.add_model(model2)
    
    # Create a binding that expires quickly
    properties = AdhesiveProperties(
        strength=1.0,
        durability=1.0,
        flexibility=1.0,
        duration=timedelta(milliseconds=50),
        is_reusable=False
    )
    
    basic_cbm.bind_models(model1.name, model2.name, 'tape', properties)
    
    # Give time for binding to expire
    import time
    time.sleep(0.1)
    
    active_bindings = basic_cbm.get_active_bindings()
    assert len(active_bindings['tape']) == 0

# ==================== Error Handling Tests ====================
def test_invalid_binding_type(basic_cbm, sample_models):
    """Test that invalid binding types raise ValueError"""
    model1, model2 = sample_models[0:2]
    basic_cbm.add_model(model1)
    basic_cbm.add_model(model2)
    
    with pytest.raises(ValueError):
        basic_cbm.bind_models(model1.name, model2.name, 'invalid_type')

def test_bind_nonexistent_model(basic_cbm, sample_models):
    """Test binding with nonexistent model raises KeyError"""
    model = sample_models[0]
    basic_cbm.add_model(model)
    
    with pytest.raises(KeyError):
        basic_cbm.bind_models(model.name, "nonexistent_model", 'glue')

# ==================== Input Processing Tests ====================
@pytest.mark.asyncio
async def test_process_input(basic_cbm, sample_models):
    """Test processing user input through the CBM"""
    model1, model2 = sample_models[0:2]
    basic_cbm.add_model(model1)
    basic_cbm.add_model(model2)
    basic_cbm.bind_models(model1.name, model2.name, 'glue')
    
    # This will raise NotImplementedError until we implement conversation manager
    with pytest.raises(NotImplementedError):
        await basic_cbm.process_input("Test input")
    
    # NEW: Test input storage in memory
    working_memories = [m for m in basic_cbm.memory_manager.working.values()]
    assert len(working_memories) == 1
    assert working_memories[0].content == "Test input"

# ==================== Serialization Tests ====================
def test_cbm_serialization(basic_cbm, sample_models):
    """Test converting CBM to and from dictionary"""
    model1, model2 = sample_models[0:2]
    basic_cbm.add_model(model1)
    basic_cbm.add_model(model2)
    basic_cbm.bind_models(model1.name, model2.name, 'glue')
    
    # Test to_dict
    cbm_dict = basic_cbm.to_dict()
    assert cbm_dict['name'] == basic_cbm.name
    assert len(cbm_dict['models']) == 2
    assert len(cbm_dict['bindings']['glue']) == 1
    
    # Test from_dict
    new_cbm = CBM.from_dict(cbm_dict)
    assert new_cbm.name == basic_cbm.name
    assert len(new_cbm.models) == len(basic_cbm.models)