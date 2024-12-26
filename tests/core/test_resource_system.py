"""Tests for GLUE Resource Management System"""

import pytest
import asyncio
from datetime import datetime
from typing import Set, Any
from src.glue.core.resource import Resource, ResourceState, ResourceMetadata
from src.glue.core.state import StateManager, TransitionError
from src.glue.core.registry import ResourceRegistry
from src.glue.magnetic.field import MagneticField
from src.glue.magnetic.rules import (
    RuleSet,
    AttractionRule,
    PolicyPriority,
    AttractionPolicy
)

# ==================== Resource Tests ====================

async def test_resource_basic():
    """Test basic resource functionality"""
    resource = Resource("test_resource", category="test", tags={"tag1", "tag2"})
    
    # Basic properties
    assert resource.name == "test_resource"
    assert resource.state == ResourceState.IDLE
    assert resource.field is None
    assert resource.context is None
    
    # Metadata
    assert resource.metadata.category == "test"
    assert "tag1" in resource.metadata.tags
    assert "tag2" in resource.metadata.tags
    
    # Rule system
    assert resource._rules is not None
    assert len(resource._rules.rules) == 1  # Default state rule

async def test_resource_metadata():
    """Test resource metadata"""
    tags = {"tag1", "tag2"}
    resource = Resource("test_resource", category="test", tags=tags)
    
    assert resource.metadata.category == "test"
    assert resource.metadata.tags == tags
    assert isinstance(resource.metadata.created_at, datetime)

async def test_resource_attraction():
    """Test resource attraction mechanics"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field")
    resource1 = Resource("resource1")
    resource2 = Resource("resource2")
    
    # Enter field
    await resource1.enter_field(field, registry)
    await resource2.enter_field(field, registry)
    
    # Test attraction
    success = await resource1.attract_to(resource2)
    assert success
    assert resource2 in resource1._attracted_to
    assert resource1 in resource2._attracted_to
    assert resource1.state == ResourceState.SHARED
    assert resource2.state == ResourceState.SHARED
    
    # Test repulsion breaks attraction
    await resource1.repel_from(resource2)
    assert resource2 not in resource1._attracted_to
    assert resource1 not in resource2._attracted_to
    assert resource1.state == ResourceState.IDLE
    assert resource2.state == ResourceState.IDLE

async def test_resource_locking():
    """Test resource locking mechanics"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field")
    resource1 = Resource("resource1")
    resource2 = Resource("resource2")
    
    # Enter field
    await resource1.enter_field(field, registry)
    await resource2.enter_field(field, registry)
    
    # Test locking
    success = await resource1.lock(resource2)
    assert success
    assert resource1.state == ResourceState.LOCKED
    assert resource1._lock_holder == resource2
    
    # Test locked resource can't be attracted
    resource3 = Resource("resource3")
    await resource3.enter_field(field, registry)
    assert not await resource1.attract_to(resource3)
    
    # Test unlocking
    await resource1.unlock()
    assert resource1.state == ResourceState.IDLE
    assert resource1._lock_holder is None

# ==================== State Manager Tests ====================

async def test_state_manager_basic():
    """Test basic state manager functionality"""
    manager = StateManager()
    resource = Resource("test_resource")
    
    # Test valid transition
    success = await manager.transition(resource, ResourceState.ACTIVE)
    assert success
    assert resource.state == ResourceState.ACTIVE
    
    # Test invalid transition
    with pytest.raises(TransitionError):
        await manager.transition(resource, ResourceState.PULLING)

async def test_state_manager_rules():
    """Test state transition rules"""
    manager = StateManager()
    resource = Resource("test_resource")
    
    # Test IDLE -> any state
    states = [
        ResourceState.ACTIVE,
        ResourceState.LOCKED,
        ResourceState.SHARED,
        ResourceState.CHATTING,
        ResourceState.PULLING
    ]
    
    for state in states:
        success = await manager.transition(resource, state)
        assert success
        # Return to IDLE for next test
        await manager.transition(resource, ResourceState.IDLE)

async def test_state_manager_history():
    """Test state transition history"""
    manager = StateManager()
    resource = Resource("test_resource")
    
    # Perform some transitions
    await manager.transition(resource, ResourceState.ACTIVE)
    await manager.transition(resource, ResourceState.SHARED)
    await manager.transition(resource, ResourceState.IDLE)
    
    # Check history
    history = manager.get_history("test_resource")
    assert len(history) == 3
    assert all(log.success for log in history)

# ==================== Resource Registry Tests ====================

async def test_registry_basic():
    """Test basic registry functionality"""
    registry = ResourceRegistry()
    resource = Resource("test_resource", category="test")
    
    # Test registration
    registry.register(resource, "test")
    assert registry.get_resource("test_resource") == resource
    
    # Test unregistration
    registry.unregister("test_resource")
    assert registry.get_resource("test_resource") is None

async def test_registry_categories():
    """Test registry category management"""
    registry = ResourceRegistry()
    
    # Create resources in different categories
    resources = [
        Resource("resource1", category="cat1"),
        Resource("resource2", category="cat1"),
        Resource("resource3", category="cat2")
    ]
    
    for resource in resources:
        registry.register(resource, resource.metadata.category)
    
    # Test category filtering
    cat1_resources = registry.get_resources_by_category("cat1")
    assert len(cat1_resources) == 2
    assert all(r.metadata.category == "cat1" for r in cat1_resources)

async def test_registry_tags():
    """Test registry tag management"""
    registry = ResourceRegistry()
    
    # Create resources with tags
    resource1 = Resource("resource1", tags={"tag1", "tag2"})
    resource2 = Resource("resource2", tags={"tag2", "tag3"})
    
    registry.register(resource1, "test")
    registry.register(resource2, "test")
    
    # Test tag filtering
    tag2_resources = registry.get_resources_by_tag("tag2")
    assert len(tag2_resources) == 2
    
    tag1_resources = registry.get_resources_by_tag("tag1")
    assert len(tag1_resources) == 1
    assert tag1_resources[0].name == "resource1"

async def test_registry_integration():
    """Test registry integration"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field")
    resource1 = Resource("resource1")
    resource2 = Resource("resource2")
    
    # Track registry events
    events = []
    def observer(event_type: str, data: Any) -> None:
        events.append((event_type, data))
    
    registry.add_observer("field_enter", observer)
    registry.add_observer("attraction", observer)
    registry.add_observer("state_change", observer)
    
    # Enter field
    await resource1.enter_field(field, registry)
    await resource2.enter_field(field, registry)
    
    # Test attraction with registry notification
    await resource1.attract_to(resource2)
    
    # Verify events
    assert len(events) >= 3
    assert any(e[0] == "field_enter" for e in events)
    assert any(e[0] == "attraction" for e in events)
    assert any(e[0] == "state_change" for e in events)

async def test_rule_validation():
    """Test rule-based validation"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field")
    resource1 = Resource("resource1")
    resource2 = Resource("resource2")
    
    # Add custom rule
    resource1._rules.add_rule(AttractionRule(
        name="test_rule",
        policy=AttractionPolicy.CUSTOM,
        priority=PolicyPriority.HIGH,
        custom_validator=lambda r1, r2: r1.state == ResourceState.IDLE,
        description="Only IDLE resources can attract"
    ))
    
    # Enter field
    await resource1.enter_field(field, registry)
    await resource2.enter_field(field, registry)
    
    # Test attraction with rule validation
    assert await resource1.attract_to(resource2)  # Should work (IDLE)
    
    # Change state and test again
    resource1._state = ResourceState.ACTIVE
    assert not await resource1.attract_to(resource2)  # Should fail (not IDLE)

# ==================== Integration Tests ====================

async def test_full_resource_lifecycle():
    """Test complete resource lifecycle"""
    # Setup
    registry = ResourceRegistry(StateManager())
    field = MagneticField("test_field")
    
    # Create resources
    resource1 = Resource("resource1", category="test", tags={"tag1"})
    resource2 = Resource("resource2", category="test", tags={"tag2"})
    
    # Enter field and register
    await resource1.enter_field(field, registry)
    await resource2.enter_field(field, registry)
    
    # Test attraction with state changes
    await resource1.attract_to(resource2)
    assert resource2 in resource1._attracted_to
    assert resource1.state == ResourceState.SHARED
    
    # Test locking
    await resource1.lock(resource2)
    assert resource1.state == ResourceState.LOCKED
    
    # Test cleanup
    await resource1.exit_field()
    assert resource1.state == ResourceState.IDLE
    assert not resource1._attracted_to
    assert resource1._registry is None

async def test_concurrent_operations():
    """Test concurrent resource operations"""
    registry = ResourceRegistry()
    resource = Resource("test_resource")
    registry.register(resource, "test")
    
    async def transition_task(state: ResourceState) -> bool:
        return await registry.transition_resource("test_resource", state)
    
    # Create concurrent transitions
    tasks = [
        transition_task(ResourceState.ACTIVE),
        transition_task(ResourceState.SHARED),
        transition_task(ResourceState.IDLE)
    ]
    
    # Run concurrently
    results = await asyncio.gather(*tasks)
    
    # Verify only one succeeded (others should fail due to state rules)
    assert sum(results) == 1
