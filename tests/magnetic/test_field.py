# tests/magnetic/test_field.py

# ==================== Imports ====================
import pytest
import pytest_asyncio
from typing import List, Set
from src.glue.magnetic.field import (
    MagneticField,
    MagneticResource,
    AttractionStrength,
    ResourceState,
    FieldEvent,
    ResourceAddedEvent,
    ResourceRemovedEvent,
    AttractionEvent,
    RepulsionEvent
)

# ==================== Fixtures ====================
@pytest_asyncio.fixture
async def field():
    """Create a magnetic field"""
    async with MagneticField("test_field") as field:
        yield field

@pytest_asyncio.fixture
async def resources():
    """Create test resources"""
    return [
        MagneticResource("resource1", AttractionStrength.MEDIUM),
        MagneticResource("resource2", AttractionStrength.MEDIUM),
        MagneticResource("resource3", AttractionStrength.STRONG)
    ]

@pytest_asyncio.fixture
async def populated_field(field, resources):
    """Create a field with test resources"""
    for resource in resources:
        field.add_resource(resource)
    return field

# ==================== Test Classes ====================
class EventCollector:
    """Helper class to collect field events"""
    def __init__(self):
        self.events: List[FieldEvent] = []

    def collect(self, event: FieldEvent):
        self.events.append(event)

# ==================== Tests ====================
def test_field_initialization():
    """Test field initialization"""
    field = MagneticField("test")
    assert field.name == "test"
    assert field.strength == AttractionStrength.MEDIUM
    assert not field._active
    assert len(field._resources) == 0

@pytest.mark.asyncio
async def test_field_context_manager():
    """Test field context manager"""
    async with MagneticField("test") as field:
        assert field._active
    assert not field._active

@pytest.mark.asyncio
async def test_resource_addition(field, resources):
    """Test adding resources to field"""
    field.add_resource(resources[0])
    assert resources[0].name in field._resources
    assert field._resources[resources[0].name] == resources[0]

@pytest.mark.asyncio
async def test_resource_removal(populated_field, resources):
    """Test removing resources from field"""
    populated_field.remove_resource(resources[0])
    assert resources[0].name not in populated_field._resources

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
async def test_field_hierarchy():
    """Test field parent/child relationships"""
    async with MagneticField("parent") as parent:
        child = parent.create_child_field("child")
        assert child.parent == parent
        assert child in parent._child_fields
        
        resource = MagneticResource("test")
        child.add_resource(resource)
        assert resource.name in child._resources
        
        # Cleanup should propagate
        await parent.cleanup()
        assert not child._active
        assert len(child._resources) == 0

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
async def test_strength_compatibility():
    """Test strength-based attraction rules"""
    weak_resource = MagneticResource("weak", AttractionStrength.WEAK)
    strong_resource = MagneticResource("strong", AttractionStrength.STRONG)
    
    # Create strong field
    async with MagneticField("strong", AttractionStrength.STRONG) as strong_field:
        # Add resources to field
        strong_field.add_resource(weak_resource)
        strong_field.add_resource(strong_resource)
        
        # Attempt attraction
        success = await strong_field.attract(weak_resource, strong_resource)
        assert not success  # Should fail due to weak resource in strong field

@pytest.mark.asyncio
async def test_cleanup(populated_field, resources):
    """Test field cleanup"""
    await populated_field.cleanup()
    assert not populated_field._active
    assert len(populated_field._resources) == 0
    for resource in resources:
        assert resource._current_field is None
        assert len(resource._attracted_to) == 0
        assert len(resource._repelled_by) == 0
        assert resource._state == ResourceState.IDLE

@pytest.mark.asyncio
async def test_event_propagation():
    """Test event propagation through field hierarchy"""
    collector = EventCollector()
    
    async with MagneticField("parent") as parent:
        parent.on_event(AttractionEvent, collector.collect)
        child = parent.create_child_field("child")
        
        resource1 = MagneticResource("r1")
        resource2 = MagneticResource("r2")
        child.add_resource(resource1)
        child.add_resource(resource2)
        
        await child.attract(resource1, resource2)
        assert len(collector.events) == 1  # Event should propagate to parent

@pytest.mark.asyncio
async def test_invalid_operations(field, resources):
    """Test invalid operations"""
    resource = resources[0]
    
    # Test operations on inactive field
    await field.cleanup()
    with pytest.raises(RuntimeError):
        field.add_resource(resource)
    
    # Test duplicate resource addition
    async with MagneticField("test") as new_field:
        new_field.add_resource(resource)
        with pytest.raises(ValueError):
            new_field.add_resource(resource)
        
        # Test invalid attraction
        other = resources[1]  # Not in field
        with pytest.raises(ValueError):
            await new_field.attract(resource, other)
