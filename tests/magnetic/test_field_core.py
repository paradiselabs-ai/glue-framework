import pytest
import asyncio
from typing import Set, Optional
from src.glue.magnetic.field import MagneticField, MagneticResource, ResourceState

class TestResource(MagneticResource):
    """Test resource implementation"""
    __test__ = False  # This tells pytest not to collect this class as a test

    def __init__(self, name: str):
        super().__init__(name)
        self.cleanup_called: bool = False
        self.initialized: bool = False
        self.error_on_cleanup: bool = False
        self.error_on_init: bool = False
        self.shared_data: dict = {}

    async def initialize(self) -> None:
        if self.error_on_init:
            raise RuntimeError("Test initialization error")
        self.initialized = True
    
    async def cleanup(self) -> None:
        if self.error_on_cleanup:
            raise RuntimeError("Test cleanup error")
        self.cleanup_called = True

def create_test_resource(name: str) -> TestResource:
    """Factory function for creating TestResource instances"""
    resource = TestResource(name)
    resource.cleanup_called = False
    resource.initialized = False
    resource.error_on_cleanup = False
    resource.error_on_init = False
    resource.shared_data = {}
    return resource

@pytest.fixture
async def field():
    """Create a test field"""
    async with MagneticField("test_field") as f:
        yield f

@pytest.fixture
def resource():
    """Create a test resource"""
    return TestResource("test_resource")

@pytest.fixture
def test_resource_factory():
    """Factory fixture for creating TestResource instances"""
    return create_test_resource

@pytest.mark.asyncio
async def test_resource_lifecycle(field, resource):
    """Test basic resource lifecycle"""
    # Add resource
    await field.add_resource(resource)
    assert resource.name in field._resources
    assert resource._current_field == field
    assert resource._state == ResourceState.IDLE
    
    # Remove resource
    await field.remove_resource(resource)
    assert resource.name not in field._resources
    assert resource._current_field is None
    assert resource.cleanup_called

@pytest.mark.asyncio
async def test_attraction_mechanics(field, test_resource_factory):
    """Test resource attraction behavior"""
    resource1 = test_resource_factory("resource1")
    resource2 = test_resource_factory("resource2")
    
    # Add resources
    await asyncio.gather(
        field.add_resource(resource1),
        field.add_resource(resource2)
    )
    
    # Test attraction
    assert await field.attract(resource1, resource2)
    assert resource2 in resource1._attracted_to
    assert resource1 in resource2._attracted_to
    assert resource1._state == ResourceState.SHARED
    assert resource2._state == ResourceState.SHARED
    
    # Test repulsion
    await field.repel(resource1, resource2)
    assert resource2 not in resource1._attracted_to
    assert resource1 not in resource2._attracted_to
    assert resource1._state == ResourceState.IDLE
    assert resource2._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_error_handling(field, test_resource_factory):
    """Test error handling in field operations"""
    resource = test_resource_factory("error_resource")
    resource.error_on_cleanup = True
    
    # Add resource
    await field.add_resource(resource)
    
    # Test cleanup error handling
    with pytest.raises(RuntimeError):
        await field.remove_resource(resource)
    
    # Resource should still be removed despite error
    assert resource.name not in field._resources

@pytest.mark.asyncio
async def test_state_transitions(field, test_resource_factory):
    """Test resource state transitions"""
    resource1 = test_resource_factory("resource1")
    resource2 = test_resource_factory("resource2")
    
    # Add resources
    await asyncio.gather(
        field.add_resource(resource1),
        field.add_resource(resource2)
    )
    
    # Test state transitions during attraction
    assert await field.attract(resource1, resource2)
    assert resource1._state == ResourceState.SHARED
    assert resource2._state == ResourceState.SHARED
    
    # Test locking
    assert await field.lock_resource(resource1, resource2)
    assert resource1._state == ResourceState.LOCKED
    assert resource1._lock_holder == resource2
    
    # Test unlocking
    await field.unlock_resource(resource1)
    assert resource1._state == ResourceState.IDLE
    assert resource1._lock_holder is None

@pytest.mark.asyncio
async def test_concurrent_operations(field, test_resource_factory):
    """Test concurrent field operations"""
    resources = [test_resource_factory(f"resource{i}") for i in range(5)]
    
    # Add resources concurrently
    await asyncio.gather(*(
        field.add_resource(resource)
        for resource in resources
    ))
    
    # Test concurrent attractions
    await asyncio.gather(*(
        field.attract(resources[i], resources[i+1])
        for i in range(len(resources)-1)
    ))
    
    # Verify attractions
    for i in range(len(resources)-1):
        assert resources[i+1] in resources[i]._attracted_to
        assert resources[i] in resources[i+1]._attracted_to

@pytest.mark.asyncio
async def test_resource_sharing(field, test_resource_factory):
    """Test resource data sharing"""
    resource1 = test_resource_factory("resource1")
    resource2 = test_resource_factory("resource2")
    
    # Add resources
    await asyncio.gather(
        field.add_resource(resource1),
        field.add_resource(resource2)
    )
    
    # Enable sharing
    assert await field.attract(resource1, resource2)
    
    # Test data sharing
    resource1.shared_data["test"] = "data"
    assert "test" in resource1.shared_data
    assert resource1.shared_data["test"] == "data"

@pytest.mark.asyncio
async def test_field_context(test_resource_factory):
    """Test field context management"""
    async with MagneticField("context_test") as test_field:
        resource = test_resource_factory("test_resource")
        await test_field.add_resource(resource)
        assert resource.name in test_field._resources
    
    # Verify cleanup after context exit
    assert resource.cleanup_called
    assert resource._current_field is None

@pytest.mark.asyncio
async def test_resource_dependencies(field, test_resource_factory):
    """Test resource dependency handling"""
    parent = test_resource_factory("parent")
    child1 = test_resource_factory("child1")
    child2 = test_resource_factory("child2")
    
    # Add resources
    await asyncio.gather(
        field.add_resource(parent),
        field.add_resource(child1),
        field.add_resource(child2)
    )
    
    # Create dependencies
    assert await field.attract(parent, child1)
    assert await field.attract(parent, child2)
    
    # Test dependency cleanup
    await field.remove_resource(parent)
    assert child1._state == ResourceState.IDLE
    assert child2._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_field_isolation(test_resource_factory):
    """Test field isolation"""
    async with MagneticField("field1") as field1, MagneticField("field2") as field2:
        resource = test_resource_factory("shared_resource")
        
        # Add to first field
        await field1.add_resource(resource)
        assert resource._current_field == field1
        
        # Attempt to add to second field should fail
        with pytest.raises(ValueError):
            await field2.add_resource(resource)
