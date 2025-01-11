# GLUE Resource System

The GLUE Resource system provides a unified foundation for managing all components in the framework. This document explains the core concepts, architecture, and usage patterns.

## Core Concepts

### Resources

A Resource is any component that can:
- Maintain state
- Participate in fields
- Track relationships
- Handle events
- Follow rules

```python
from glue.core.resource import Resource

# Create a basic resource
resource = Resource(
    name="example",
    category="custom",
    tags={"tag1", "tag2"}
)
```

### States

Resources can be in various states:
- IDLE: Not currently in use
- ACTIVE: Currently in use
- LOCKED: Cannot be used by others
- SHARED: Being shared between resources
- CHATTING: In direct model-to-model communication
- PULLING: Receiving data only
- PUSHING: Sending data only


```python
from glue.core.resource import ResourceState

# Check resource state
if resource.state == ResourceState.IDLE:
    # Resource is available
```

### Fields

Fields provide a context for resource interactions:
- Resource tracking
- State management
- Rule enforcement
- Event propagation

```python
from glue.magnetic.field import MagneticField

# Create a field
async with MagneticField("workspace", registry) as field:
    # Add resources
    await field.add_resource(resource1)
    await field.add_resource(resource2)
    
    # Create attraction
    await field.attract(resource1, resource2)
```

### Registry

The Registry manages resource lifecycle:
- Resource tracking
- Category management
- State transitions
- Event observation

```python
from glue.core.registry import ResourceRegistry

# Create registry
registry = ResourceRegistry()

# Register resource
registry.register(resource, "category")

# Find resources
tools = registry.get_resources_by_category("tool")
active = registry.get_resources_by_state(ResourceState.ACTIVE)
```

## Resource Types

### Tools

Tools are resources that perform specific operations:
- State-tracked execution
- Permission management
- Error handling
- Field awareness

```python
from glue.tools.base import BaseTool, ToolConfig

class CustomTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="custom_tool",
            description="Custom tool implementation",
            config=ToolConfig(required_permissions=[])
        )
    
    async def _execute(self, **kwargs):
        # Tool implementation
        pass
```

### Models

Models are resources that provide AI capabilities:
- Context awareness
- Tool usage
- Communication
- Memory management

```python
from glue.core.model import BaseModel

class CustomModel(BaseModel):
    async def process(self, input_data):
        # Model implementation
        pass
```

## Interaction Patterns

### Attraction/Repulsion

Resources can form relationships:
```python
# Create attraction
await resource1.attract_to(resource2)

# Create repulsion
await resource1.repel_from(resource2)
```

### State Transitions

Resources follow state rules:
```python
# Lock resource
await resource.lock(holder)

# Release resource
await resource.unlock()
```

### Field Operations

Fields manage resource interactions:
```python
# Enable chat between models
await field.enable_chat(model1, model2)

# Enable data pull
await field.enable_pull(target, source)
```

## Best Practices

### Resource Management

1. Always use context managers for fields:
```python
async with MagneticField("workspace", registry) as field:
    # Field operations
```

2. Clean up resources properly:
```python
try:
    await resource.enter_field(field)
    # Use resource
finally:
    await resource.exit_field()
```

### State Handling

1. Check state before operations:
```python
if resource.state != ResourceState.IDLE:
    raise RuntimeError("Resource busy")
```

2. Use state transitions carefully:
```python
async with resource._state_change_lock:
    # Perform state transition
```

### Event Handling

1. Register event handlers:
```python
def on_state_change(resource, data):
    print(f"State changed: {data}")

resource.on_event("state_change", on_state_change)
```

2. Emit events properly:
```python
await resource._emit_event("custom_event", event_data)
```

## Migration Guide

### From Old System

1. Update imports:
```python
# Old
from glue.magnetic import MagneticResource

# New
from glue.core.resource import Resource
```

2. Update class definitions:
```python
# Old
class CustomTool(MagneticResource):
    pass

# New
class CustomTool(Resource):
    def __init__(self):
        super().__init__(name="custom", category="tool")
```

3. Update field usage:
```python
# Old
field = MagneticField()

# New
field = MagneticField("name", registry)
```

## Common Patterns

### Tool Implementation
```python
class DataTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="data_tool",
            description="Process data",
            config=ToolConfig(
                required_permissions=[ToolPermission.READ]
            )
        )
    
    async def _execute(self, data: Any) -> Any:
        self._state = ResourceState.ACTIVE
        try:
            # Process data
            return result
        finally:
            self._state = ResourceState.IDLE
```

### Field Management
```python
# Create hierarchy
parent = MagneticField("parent", registry)
child = parent.create_child_field("child")

# Share rules
child._rules = parent._rules.copy()

# Manage resources
await parent.add_resource(resource1)
await child.add_resource(resource2)
```

### Resource Coordination
```python
# Create attraction
await field.attract(resource1, resource2)

# Execute with relationship
if resource2 in resource1._attracted_to:
    result = await resource1.execute()
```

## Error Handling

### Resource Errors
```python
try:
    await resource.enter_field(field)
except RuntimeError as e:
    # Handle field entry error
```

### Tool Errors
```python
tool.add_error_handler(ValueError, handle_error)
try:
    await tool.safe_execute()
except Exception as e:
    # Handle unhandled error
```

### Field Errors
```python
try:
    await field.attract(resource1, resource2)
except ValueError as e:
    # Handle attraction error
```

## Testing

### Resource Testing
```python
async def test_resource():
    resource = Resource("test")
    assert resource.state == ResourceState.IDLE
```

### Field Testing
```python
async def test_field():
    async with MagneticField("test", registry) as field:
        await field.add_resource(resource)
```

### Tool Testing
```python
async def test_tool():
    tool = TestTool()
    result = await tool.safe_execute()
