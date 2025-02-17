"""Tests for Mem0 integration"""

import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any

from glue.core.memory import MemoryManager
from glue.core.mem0_manager import Mem0Config
from glue.core.context import ContextState, ComplexityLevel
from glue.core.types import AdhesiveType

@pytest.fixture
def mem0_config():
    """Test configuration for Mem0"""
    return Mem0Config(
        collection_name="test_glue_memory",
        host="localhost",
        port=6333
    )

@pytest.fixture
async def memory_manager(mem0_config):
    """Initialize memory manager with Mem0"""
    manager = MemoryManager(mem0_config=mem0_config)
    yield manager
    await manager.cleanup()

@pytest.mark.asyncio
async def test_basic_store_retrieve(memory_manager):
    """Test basic store and retrieve operations with Mem0"""
    content = {"test": "data"}
    user_id = "test_user"
    
    # Store content
    memory_id = await memory_manager.store(
        key="test_key",
        content=content,
        memory_type="long_term",
        user_id=user_id,
        metadata={"test": True}
    )
    
    assert memory_id is not None
    
    # Retrieve content
    retrieved = await memory_manager.recall(
        key="test_key",
        memory_type="long_term",
        user_id=user_id
    )
    
    assert retrieved is not None
    assert retrieved["test"] == "data"

@pytest.mark.asyncio
async def test_semantic_search(memory_manager):
    """Test semantic search functionality"""
    user_id = "test_user"
    
    # Store some test data
    await memory_manager.store(
        key="python",
        content="Python is a high-level programming language",
        memory_type="long_term",
        user_id=user_id
    )
    
    await memory_manager.store(
        key="javascript",
        content="JavaScript is a web programming language",
        memory_type="long_term",
        user_id=user_id
    )
    
    # Search with semantic query
    result = await memory_manager.recall(
        key="programming",  # Key doesn't matter for semantic search
        memory_type="long_term",
        user_id=user_id,
        semantic_query="What programming languages are mentioned?"
    )
    
    assert result is not None
    assert "programming" in result.lower()
    assert "language" in result.lower()

@pytest.mark.asyncio
async def test_shared_memory(memory_manager):
    """Test shared memory functionality with Mem0"""
    content = "Shared test data"
    
    # Share memory between models
    await memory_manager.share(
        from_model="model1",
        to_model="model2",
        key="shared_key",
        content=content,
        metadata={"shared": True}
    )
    
    # Retrieve as recipient
    result = await memory_manager.recall(
        key="shared_key",
        memory_type="shared",
        user_id="model2",
        semantic_query="What was shared?"
    )
    
    assert result is not None
    assert "test data" in result.lower()

@pytest.mark.asyncio
async def test_memory_expiration(memory_manager):
    """Test memory expiration handling"""
    user_id = "test_user"
    
    # Store with short duration
    await memory_manager.store(
        key="expiring",
        content="This will expire",
        memory_type="short_term",
        duration=timedelta(seconds=1),
        user_id=user_id
    )
    
    # Verify content exists
    result = await memory_manager.recall(
        key="expiring",
        memory_type="short_term",
        user_id=user_id
    )
    assert result is not None
    
    # Wait for expiration
    await asyncio.sleep(1.1)
    
    # Verify content is gone
    result = await memory_manager.recall(
        key="expiring",
        memory_type="short_term",
        user_id=user_id
    )
    assert result is None

@pytest.mark.asyncio
async def test_memory_with_context(memory_manager):
    """Test memory storage with context"""
    user_id = "test_user"
    context = ContextState(
        complexity=ComplexityLevel.MEDIUM,
        tools_required={"web_search"},
        requires_persistence=True,
        requires_memory=True
    )
    
    # Store with context
    memory_id = await memory_manager.store(
        key="context_test",
        content="Test with context",
        memory_type="long_term",
        user_id=user_id,
        context=context,
        metadata={"has_context": True}
    )
    
    assert memory_id is not None
    
    # Retrieve and verify context is preserved
    result = await memory_manager.recall(
        key="context_test",
        memory_type="long_term",
        user_id=user_id
    )
    
    assert result is not None
    assert "test with context" in result.lower()

@pytest.mark.asyncio
async def test_memory_cleanup(memory_manager):
    """Test memory cleanup operations"""
    user_id = "test_user"
    
    # Store some test data
    await memory_manager.store(
        key="test1",
        content="Test content 1",
        memory_type="short_term",
        user_id=user_id
    )
    
    await memory_manager.store(
        key="test2",
        content="Test content 2",
        memory_type="long_term",
        user_id=user_id
    )
    
    # Clear specific memory type
    await memory_manager.clear(
        memory_type="short_term",
        user_id=user_id
    )
    
    # Verify short-term is cleared but long-term remains
    short_result = await memory_manager.recall(
        key="test1",
        memory_type="short_term",
        user_id=user_id
    )
    assert short_result is None
    
    long_result = await memory_manager.recall(
        key="test2",
        memory_type="long_term",
        user_id=user_id
    )
    assert long_result is not None
    
    # Clear all memory
    await memory_manager.clear(user_id=user_id)
    
    # Verify everything is cleared
    long_result = await memory_manager.recall(
        key="test2",
        memory_type="long_term",
        user_id=user_id
    )
    assert long_result is None
