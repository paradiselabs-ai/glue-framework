"""Tests for GLUE Magnetic Field System"""

import asyncio
from typing import Any
from src.glue.core.resource import Resource, ResourceState
from src.glue.core.state import StateManager
from src.glue.core.registry import ResourceRegistry
from src.glue.magnetic.field import (
    MagneticField,
    ResourceAddedEvent,
    AttractionEvent,
    RepulsionEvent
)
from src.glue.magnetic.rules import (
    AttractionRule,
    PolicyPriority,
    AttractionPolicy
)

# ==================== Field Tests ====================

import pytest

@pytest.mark.asyncio
async def test_field_basic():
    """Test basic field functionality"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field", registry)
    resource = Resource("test_resource")
    
    # Test field activation
    async with field:
        assert field._active
        
        # Test resource addition
        await field.add_resource(resource)
        assert field.get_resource("test_resource") == resource
        assert resource.field == field
        assert resource.state == ResourceState.IDLE
        
        # Test resource removal
        await field.remove_resource(resource)
        assert field.get_resource("test_resource") is None
        assert resource.field is None
    
    # Test field cleanup
    assert not field._active
    assert not field.list_resources()

@pytest.mark.asyncio
async def test_field_rules():
    """Test field rule system"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field", registry)
    
    # Add custom rule
    field._rules.add_rule(AttractionRule(
        name="test_rule",
        policy=AttractionPolicy.CUSTOM,
        priority=PolicyPriority.HIGH,
        custom_validator=lambda r1, r2: r1.state == ResourceState.IDLE,
        description="Only IDLE resources can attract"
    ))
    
    async with field:
        resource1 = Resource("resource1")
        resource2 = Resource("resource2")
        
        await field.add_resource(resource1)
        await field.add_resource(resource2)
        
        # Test attraction with rule validation
        assert await field.attract(resource1, resource2)  # Should work (IDLE)
        
        # Change state and test again
        resource1._state = ResourceState.ACTIVE
        assert not await field.attract(resource1, resource2)  # Should fail (not IDLE)

@pytest.mark.asyncio
async def test_field_events():
    """Test field event system"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field", registry)
    events = []
    
    def event_handler(event: Any) -> None:
        events.append(event)
    
    # Register handlers
    field.on_event(ResourceAddedEvent, event_handler)
    field.on_event(AttractionEvent, event_handler)
    field.on_event(RepulsionEvent, event_handler)
    
    async with field:
        resource1 = Resource("resource1")
        resource2 = Resource("resource2")
        
        # Test add events
        await field.add_resource(resource1)
        await field.add_resource(resource2)
        assert len(events) == 2
        assert isinstance(events[0], ResourceAddedEvent)
        
        # Test attraction events
        await field.attract(resource1, resource2)
        assert len(events) == 3
        assert isinstance(events[2], AttractionEvent)
        
        # Test repulsion events
        await field.repel(resource1, resource2)
        assert len(events) == 4
        assert isinstance(events[3], RepulsionEvent)

@pytest.mark.asyncio
async def test_field_hierarchy():
    """Test hierarchical fields"""
    # Setup
    registry = ResourceRegistry(StateManager())
    parent = MagneticField("parent", registry)
    
    async with parent:
        # Create child field
        child = parent.create_child_field("child")
        assert child.parent == parent
        assert child._active
        
        # Test rule inheritance
        parent._rules.add_rule(AttractionRule(
            name="parent_rule",
            policy=AttractionPolicy.CUSTOM,
            priority=PolicyPriority.HIGH,
            custom_validator=lambda r1, r2: True,
            description="Parent rule"
        ))
        assert len(child._rules.rules) == len(parent._rules.rules)
        
        # Test resource isolation
        resource1 = Resource("resource1")
        resource2 = Resource("resource2")
        
        await parent.add_resource(resource1)
        await child.add_resource(resource2)
        
        assert parent.get_resource("resource1") == resource1
        assert parent.get_resource("resource2") is None
        assert child.get_resource("resource1") is None
        assert child.get_resource("resource2") == resource2

@pytest.mark.asyncio
async def test_field_communication():
    """Test field communication modes"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field", registry)
    
    async with field:
        model1 = Resource("model1")
        model2 = Resource("model2")
        
        await field.add_resource(model1)
        await field.add_resource(model2)
        
        # Test chat mode
        success = await field.enable_chat(model1, model2)
        assert success
        assert model1.state == ResourceState.CHATTING
        assert model2.state == ResourceState.CHATTING
        assert model2 in model1._attracted_to
        assert model1 in model2._attracted_to
        
        # Test pull mode
        source = Resource("source")
        target = Resource("target")
        
        await field.add_resource(source)
        await field.add_resource(target)
        
        success = await field.enable_pull(target, source)
        assert success
        assert target.state == ResourceState.PULLING
        assert source in target._attracted_to

@pytest.mark.asyncio
async def test_field_cleanup():
    """Test field cleanup behavior"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field", registry)
    
    async with field:
        # Add resources and create attractions
        resource1 = Resource("resource1")
        resource2 = Resource("resource2")
        
        await field.add_resource(resource1)
        await field.add_resource(resource2)
        await field.attract(resource1, resource2)
        
        # Create child field with resources
        child = field.create_child_field("child")
        resource3 = Resource("resource3")
        await child.add_resource(resource3)
    
    # Verify cleanup
    assert not field._active
    assert not field.list_resources()
    assert resource1.state == ResourceState.IDLE
    assert not resource1._attracted_to
    assert not resource1._repelled_by
    assert resource1.field is None
    
    # Verify child cleanup
    assert not child._active
    assert not child.list_resources()
    assert resource3.field is None

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test concurrent field operations"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field", registry)
    
    async with field:
        resource1 = Resource("resource1")
        resource2 = Resource("resource2")
        resource3 = Resource("resource3")
        
        await field.add_resource(resource1)
        await field.add_resource(resource2)
        await field.add_resource(resource3)
        
        # Create concurrent attractions
        async def attract_task(source: Resource, target: Resource) -> bool:
            return await field.attract(source, target)
        
        tasks = [
            attract_task(resource1, resource2),
            attract_task(resource2, resource3),
            attract_task(resource3, resource1)
        ]
        
        # Run concurrently
        results = await asyncio.gather(*tasks)
        
        # Verify results maintain consistency
        assert sum(results) > 0  # At least one attraction should succeed
        
        # Verify no deadlocks
        for resource in [resource1, resource2, resource3]:
            assert resource.state in [ResourceState.IDLE, ResourceState.SHARED]
