# tests/magnetic/test_field.py

# ==================== Imports ====================
import pytest
import pytest_asyncio
from typing import List
from src.glue.magnetic.field import (
    MagneticField,
    FieldEvent,
    AttractionEvent,
    RepulsionEvent
)
from src.glue.core.types import ResourceState
from src.glue.core.resource import Resource
from src.glue.core.registry import ResourceRegistry
from src.glue.core.state import StateManager

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def registry():
    """Create a resource registry"""
    return ResourceRegistry(StateManager())

@pytest_asyncio.fixture
async def field(registry):
    """Create a magnetic field"""
    async with MagneticField("test_field", registry) as field:
        yield field

@pytest_asyncio.fixture
async def resources():
    """Create test resources"""
    return [
        Resource("resource1", category="test"),
        Resource("resource2", category="test"),
        Resource("resource3", category="test")
    ]

@pytest_asyncio.fixture
async def populated_field(field, resources):
    """Create a field with test resources"""
    for resource in resources:
        await field.add_resource(resource)
    return field

# ==================== Test Classes ====================
class EventCollector:
    """Helper class to collect field events"""
    def __init__(self):
        self.events: List[FieldEvent] = []

    def collect(self, event: FieldEvent):
        self.events.append(event)

# ==================== Tests ====================
def test_field_initialization(registry):
    """Test field initialization"""
    field = MagneticField("test", registry)
    assert field.name == "test"
    assert not field._active
    assert len(registry.get_resources_by_category("field:test")) == 0

@pytest.mark.asyncio
async def test_field_context_manager(registry):
    """Test field context manager"""
    async with MagneticField("test", registry) as field:
        assert field._active
    assert not field._active

@pytest.mark.asyncio
async def test_resource_addition(field, resources, registry):
    """Test adding resources to field"""
    await field.add_resource(resources[0])
    field_resources = registry.get_resources_by_category("field:" + field.name)
    assert resources[0] in field_resources

@pytest.mark.asyncio
async def test_resource_removal(populated_field, resources):
    """Test removing resources from field"""
    await populated_field.remove_resource(resources[0])
    field_resources = populated_field.registry.get_resources_by_category("field:" + populated_field.name)
    assert resources[0] not in field_resources

@pytest.mark.asyncio
async def test_resource_attraction(populated_field, resources):
    """Test resource attraction"""
    success = await populated_field.attract(resources[0], resources[1])
    assert success
    assert resources[1] in resources[0]._attracted_to
    assert resources[0] in resources[1]._attracted_to

@pytest.mark.asyncio
async def test_resource_repulsion(populated_field, resources):
    """Test resource repulsion"""
    await populated_field.attract(resources[0], resources[1])
    await populated_field.repel(resources[0], resources[1])
    assert resources[1] not in resources[0]._attracted_to
    assert resources[0] not in resources[1]._attracted_to
    assert resources[1] in resources[0]._repelled_by
    assert resources[0] in resources[1]._repelled_by

@pytest.mark.asyncio
async def test_resource_state_changes(populated_field, resources):
    """Test resource state transitions"""
    resource = resources[0]
    assert resource._state == ResourceState.IDLE
    
    await populated_field.attract(resource, resources[1])
    assert resource._state == ResourceState.SHARED
    
    await populated_field.lock_resource(resource, resources[2])
    assert resource._state == ResourceState.LOCKED
    
    await populated_field.unlock_resource(resource)
    assert resource._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_field_hierarchy(registry):
    """Test field parent/child relationships"""
    async with MagneticField("parent", registry) as parent:
        child = parent.create_child_field("child")
        assert child.parent == parent
        assert child in parent._child_fields
        
        resource = Resource("test", category="test")
        await child.add_resource(resource)
        field_resources = registry.get_resources_by_category("field:" + child.name)
        assert resource in field_resources
        
        # Cleanup should propagate
        await parent.cleanup()
        assert not child._active
        assert len(registry.get_resources_by_category("field:" + child.name)) == 0

@pytest.mark.asyncio
async def test_event_system(populated_field, resources):
    """Test field event system"""
    collector = EventCollector()
    populated_field.on_event(AttractionEvent, collector.collect)
    populated_field.on_event(RepulsionEvent, collector.collect)
    
    await populated_field.attract(resources[0], resources[1])
    assert len(collector.events) == 1
    assert isinstance(collector.events[0], AttractionEvent)
    
    await populated_field.repel(resources[0], resources[1])
    assert len(collector.events) == 2
    assert isinstance(collector.events[1], RepulsionEvent)

@pytest.mark.asyncio
async def test_resource_locking(populated_field, resources):
    """Test resource locking mechanism"""
    resource = resources[0]
    holder = resources[1]
    
    # Lock resource
    success = await populated_field.lock_resource(resource, holder)
    assert success
    assert resource._state == ResourceState.LOCKED
    assert resource._lock_holder == holder
    
    # Try to attract while locked
    other = resources[2]
    success = await populated_field.attract(other, resource)
    assert not success  # Should fail because resource is locked
    
    # Unlock and try again
    await populated_field.unlock_resource(resource)
    assert resource._state == ResourceState.IDLE
    success = await populated_field.attract(other, resource)
    assert success  # Should work now


@pytest.mark.asyncio
async def test_cleanup(populated_field, resources):
    """Test field cleanup"""
    await populated_field.cleanup()
    assert not populated_field._active
    field_resources = populated_field.registry.get_resources_by_category("field:" + populated_field.name)
    assert len(field_resources) == 0
    for resource in resources:
        assert resource._field is None
        assert len(resource._attracted_to) == 0
        assert len(resource._repelled_by) == 0
        assert resource._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_event_propagation(registry):
    """Test event propagation through field hierarchy"""
    collector = EventCollector()
    
    async with MagneticField("parent", registry) as parent:
        parent.on_event(AttractionEvent, collector.collect)
        child = parent.create_child_field("child")
        
        resource1 = Resource("r1", category="test")
        resource2 = Resource("r2", category="test")
        await child.add_resource(resource1)
        await child.add_resource(resource2)
        
        await child.attract(resource1, resource2)
        assert len(collector.events) == 1  # Event should propagate to parent

@pytest.mark.asyncio
async def test_invalid_operations(field, resources, registry):
    """Test invalid operations"""
    resource = resources[0]
    
    # Test operations on inactive field
    await field.cleanup()
    with pytest.raises(RuntimeError):
        await field.add_resource(resource)
    
    # Test duplicate resource addition
    async with MagneticField("test", registry) as new_field:
        await new_field.add_resource(resource)
        with pytest.raises(ValueError):
            await new_field.add_resource(resource)
        
        # Test invalid attraction
        other = resources[1]  # Not in field
        with pytest.raises(ValueError):
            await new_field.attract(resource, other)
