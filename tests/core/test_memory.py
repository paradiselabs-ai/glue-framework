# tests/core/test_memory.py
import pytest
from datetime import datetime, timedelta
from src.glue.core.memory import MemoryManager, MemorySegment

@pytest.fixture
def memory_manager():
    return MemoryManager()

def test_memory_initialization(memory_manager):
    """Test basic memory manager initialization"""
    assert isinstance(memory_manager.short_term, dict)
    assert isinstance(memory_manager.long_term, dict)
    assert isinstance(memory_manager.working, dict)
    assert isinstance(memory_manager.shared, dict)

def test_store_and_recall(memory_manager):
    """Test storing and recalling memory segments"""
    # Test short-term memory
    memory_manager.store("test_key", "test_content", "short_term")
    assert memory_manager.recall("test_key", "short_term") == "test_content"
    
    # Test long-term memory
    memory_manager.store("test_key", "test_content", "long_term")
    assert memory_manager.recall("test_key", "long_term") == "test_content"
    
    # Test working memory
    memory_manager.store("test_key", "test_content", "working")
    assert memory_manager.recall("test_key", "working") == "test_content"

def test_memory_expiration(memory_manager):
    """Test memory expiration"""
    # Store with short duration
    memory_manager.store(
        "temp_key",
        "temp_content",
        "short_term",
        duration=timedelta(milliseconds=50)
    )
    
    # Should be available immediately
    assert memory_manager.recall("temp_key", "short_term") == "temp_content"
    
    # Wait for expiration
    import time
    time.sleep(0.1)
    
    # Should be None after expiration
    assert memory_manager.recall("temp_key", "short_term") is None

def test_memory_sharing(memory_manager):
    """Test memory sharing between models"""
    memory_manager.share(
        from_model="model1",
        to_model="model2",
        key="shared_key",
        content="shared_content"
    )
    
    # Check shared memory exists in both models
    assert "shared_key" in memory_manager.shared["model1"]
    assert "from_model1_shared_key" in memory_manager.shared["model2"]
    
    # Check content is the same
    segment1 = memory_manager.shared["model1"]["shared_key"]
    segment2 = memory_manager.shared["model2"]["from_model1_shared_key"]
    assert segment1.content == "shared_content"
    assert segment2.content == "shared_content"

def test_memory_metadata(memory_manager):
    """Test memory metadata handling"""
    metadata = {"source": "test", "priority": 1}
    memory_manager.store(
        "meta_key",
        "meta_content",
        "short_term",
        metadata=metadata
    )
    
    segment = memory_manager.short_term["meta_key"]
    assert segment.metadata == metadata
    assert segment.access_count == 0
    
    # Test access counting
    memory_manager.recall("meta_key", "short_term")
    assert segment.access_count == 1
    assert segment.last_accessed is not None

def test_forget_memory(memory_manager):
    """Test removing specific memories"""
    memory_manager.store("forget_key", "forget_content", "short_term")
    assert memory_manager.recall("forget_key", "short_term") == "forget_content"
    
    memory_manager.forget("forget_key", "short_term")
    assert memory_manager.recall("forget_key", "short_term") is None

def test_clear_memory(memory_manager):
    """Test clearing memory stores"""
    # Add some memories
    memory_manager.store("key1", "content1", "short_term")
    memory_manager.store("key2", "content2", "long_term")
    memory_manager.store("key3", "content3", "working")
    
    # Clear specific type
    memory_manager.clear("short_term")
    assert len(memory_manager.short_term) == 0
    assert len(memory_manager.long_term) == 1
    assert len(memory_manager.working) == 1
    
    # Clear all
    memory_manager.clear()
    assert len(memory_manager.short_term) == 0
    assert len(memory_manager.long_term) == 0
    assert len(memory_manager.working) == 0
    assert len(memory_manager.shared) == 0

def test_cleanup_expired(memory_manager):
    """Test cleaning up expired memories"""
    # Add memories with different expirations
    memory_manager.store(
        "expire1",
        "content1",
        "short_term",
        duration=timedelta(milliseconds=50)
    )
    memory_manager.store(
        "expire2",
        "content2",
        "short_term",
        duration=timedelta(hours=1)
    )
    
    # Wait for first to expire
    import time
    time.sleep(0.1)
    
    memory_manager.cleanup_expired()
    
    # First should be gone, second should remain
    assert memory_manager.recall("expire1", "short_term") is None
    assert memory_manager.recall("expire2", "short_term") == "content2"

def test_invalid_memory_type(memory_manager):
    """Test handling of invalid memory types"""
    with pytest.raises(ValueError):
        memory_manager.store("key", "content", "invalid_type")
    
    with pytest.raises(ValueError):
        memory_manager.recall("key", "invalid_type")