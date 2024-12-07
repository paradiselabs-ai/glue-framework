# tests/core/test_conversation.py

# ==================== Imports ====================
import pytest
from datetime import datetime
from src.glue.core.conversation import ConversationManager
from src.glue.core.model import Model

# ==================== Fixtures ====================
@pytest.fixture
def conversation_manager():
    return ConversationManager()

@pytest.fixture
def sample_models():
    model1 = Model("model1", "openrouter", "test-key1")
    model2 = Model("model2", "anthropic", "test-key2")
    return {
        "model1": model1,
        "model2": model2
    }

@pytest.fixture
def sample_bindings():
    return {
        "glue": [("model1", "model2")],
        "velcro": [],
        "tape": [],
        "magnet": []
    }

# ==================== Initialization Tests ====================
def test_conversation_initialization(conversation_manager):
    """Test basic initialization"""
    assert isinstance(conversation_manager.history, list)
    assert conversation_manager.active_conversation is None
    assert isinstance(conversation_manager.model_states, dict)
    # NEW: Test memory manager initialization
    assert hasattr(conversation_manager, 'memory_manager')

# ==================== Processing Tests ====================
@pytest.mark.asyncio
async def test_process_input(conversation_manager, sample_models, sample_bindings):
    """Test processing user input"""
    user_input = "Test input"
    with pytest.raises(NotImplementedError):
        # Will raise until we implement Model.generate
        await conversation_manager.process(sample_models, sample_bindings, user_input)
    
    # NEW: Verify input was stored in memory
    stored_inputs = [
        m for m in conversation_manager.memory_manager.short_term.values()
        if isinstance(m.content, dict) and m.content.get("role") == "user"
    ]
    assert len(stored_inputs) == 1
    assert stored_inputs[0].content["content"] == user_input

# ==================== Flow Management Tests ====================
def test_determine_flow(conversation_manager, sample_bindings):
    """Test conversation flow determination"""
    flow = conversation_manager._determine_flow(sample_bindings)
    assert len(flow) == 2
    assert flow[0] == "model1"
    assert flow[1] == "model2"

# ==================== Memory Context Tests (NEW) ====================
def test_get_model_context(conversation_manager):
    """Test retrieving model context from memory"""
    # Store some test data in memory
    conversation_manager.memory_manager.store(
        key="test_message",
        content={
            "role": "user",
            "content": "test content",
            "timestamp": datetime.now()
        },
        memory_type="short_term"
    )
    
    # Test context retrieval
    context = conversation_manager._get_model_context("model1")
    assert "recent_history" in context
    assert "shared_memory" in context
    assert "model_state" in context
    assert len(context["recent_history"]) == 1

def test_enhance_input_with_context(conversation_manager):
    """Test input enhancement with context"""
    context = {
        "recent_history": [
            {"role": "user", "content": "previous message"},
            {"role": "assistant", "content": "previous response"}
        ],
        "shared_memory": {},
        "model_state": {}
    }
    
    enhanced_input = conversation_manager._enhance_input_with_context(
        "current input",
        context
    )
    
    assert "Context:" in enhanced_input
    assert "previous message" in enhanced_input
    assert "previous response" in enhanced_input
    assert "Current Input:" in enhanced_input
    assert "current input" in enhanced_input

# ==================== History Management Tests ====================
def test_conversation_history(conversation_manager):
    """Test history management"""
    # Add some history
    conversation_manager.history.append({
        "role": "user",
        "content": "test message",
        "timestamp": datetime.now()
    })
    
    # Test get_history
    history = conversation_manager.get_history()
    assert len(history) == 1
    assert history[0]["role"] == "user"
    
    # Test clear_history
    conversation_manager.clear_history()
    assert len(conversation_manager.get_history()) == 0
    # NEW: Verify short-term memory was also cleared
    assert len(conversation_manager.memory_manager.short_term) == 0

# ==================== State Management Tests ====================
def test_state_management(conversation_manager):
    """Test saving and loading state"""
    # Set up some state
    conversation_manager.history.append({
        "role": "user",
        "content": "test message",
        "timestamp": datetime.now()
    })
    conversation_manager.active_conversation = "test_convo"
    
    # Save state
    state = conversation_manager.save_state()
    
    # Clear everything
    conversation_manager.clear_history()
    conversation_manager.active_conversation = None
    
    # Load state
    conversation_manager.load_state(state)
    
    # Verify
    assert len(conversation_manager.history) == 1
    assert conversation_manager.active_conversation == "test_convo"

# ==================== Error Handling Tests ====================
@pytest.mark.asyncio
async def test_process_error_handling(conversation_manager):
    """Test error handling in process method"""
    # Test with invalid binding pattern
    invalid_bindings = {
        "glue": [("invalid", "pattern")]  # This should cause an error
    }
    
    with pytest.raises(Exception) as exc_info:
        await conversation_manager.process(
            sample_models={},  # Empty models dict
            binding_patterns=invalid_bindings,
            user_input="test"
        )
    
    # Verify error was recorded in history
    if len(conversation_manager.history) > 0:
        last_entry = conversation_manager.history[-1]
        assert last_entry["role"] == "error"
        assert "Error processing conversation" in last_entry["content"]