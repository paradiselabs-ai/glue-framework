import pytest
from datetime import timedelta, datetime
import time
from glue.core.memory import MemoryManager, MemorySegment, ContextState, ComplexityLevel

def test_memory_persistence(tmp_path):
    """Test saving and loading of memory segments."""
    # Setup manager with temp dir
    manager = MemoryManager(persistence_dir=str(tmp_path))

    # Create sample data
    content1 = {"key": "value", "list": [1, 2, 3]}
    metadata1 = {"description": "Test data"}
    tags1 = {"test", "data"}
    context1 = ContextState(
        complexity=ComplexityLevel.SIMPLE,
        tools_required=set(),
        requires_persistence=False,
        requires_memory=False,
        confidence=0.5
    )

    content2 = "Just a string"
    metadata2 = {"source": "input"}

    # Store in long-term (should persist)
    manager.store(
        "item1", content1, "long_term", metadata=metadata1, tags=tags1, context=context1
    )
    manager.store("item2", content2, "long_term", metadata=metadata2)

    # Store in short-term (should NOT persist)
    manager.store("temp_item", "This won't be saved", "short_term")

    # Simulate program restart by creating a new manager
    new_manager = MemoryManager(persistence_dir=str(tmp_path))

    # Verify persistent data is loaded
    recalled_content1 = new_manager.recall("item1", "long_term")
    assert recalled_content1 == content1
    recalled_segment1 = new_manager.long_term["item1"]
    assert recalled_segment1.metadata == metadata1
    assert recalled_segment1.tags == tags1
    assert list(recalled_segment1.context.tools_required) == list(context1.tools_required)
    assert recalled_segment1.context.complexity == context1.complexity
    assert recalled_segment1.context.requires_persistence == context1.requires_persistence
    assert recalled_segment1.context.requires_memory == context1.requires_memory
    assert recalled_segment1.context.confidence == context1.confidence

    recalled_content2 = new_manager.recall("item2", "long_term")
    assert recalled_content2 == content2
    assert new_manager.long_term["item2"].metadata == metadata2

    # Verify short-term data is NOT loaded
    assert new_manager.recall("temp_item", "short_term") is None

    # Check file existence
    assert (tmp_path / "item1.json").exists()
    assert (tmp_path / "item2.json").exists()
    assert not (tmp_path / "temp_item.json").exists()  # Should not exist

def test_memory_expiry():
    """Test memory segment expiration."""
    manager = MemoryManager()

    # Store with expiration
    short_duration = timedelta(seconds=1)
    manager.store("expiring_item", "Will expire soon", "short_term", duration=short_duration)

    # Recall before expiration
    assert manager.recall("expiring_item") == "Will expire soon"

    # Wait for expiration
    time.sleep(1.1)

    # Recall after expiration
    assert manager.recall("expiring_item") is None

def test_memory_sharing():
    """Test sharing memory between models."""
    manager = MemoryManager()

    # Share content between models
    manager.share(
        from_model="modelA",
        to_model="modelB",
        key="shared_item",
        content="Shared data",
        metadata={"origin": "modelA"},
    )

    # Verify shared content is accessible by the target model
    recalled_content = manager.shared["modelB"]["from_modelA_shared_item"].content
    assert recalled_content == "Shared data"

    # Verify metadata is preserved
    segment = manager.shared["modelB"]["from_modelA_shared_item"]
    assert segment.metadata == {"origin": "modelA"}

    # Test sharing with expiry
    manager.share("modelC", "modelD", "expiring_shared", "Expires soon", duration=timedelta(seconds=1))
    
    # Wait for expiry
    time.sleep(1.1)
    
    # Cleanup expired memory
    manager.cleanup_expired()
