# GLUE (GenAI Linking & Unification Engine) DSL Concepts

## Core Binding Methods

### Standard Glue Methods
- `glue_models()` - Combines multiple LLMs into collaborative entities
- `glue_tools()` - Attaches capabilities and functionalities
- `glue_memory()` - Bonds persistence layers
- `glue_output()` - Formats response patterns
- `glue_app()` - Decorator for creating GLUE applications

### Super Glue Methods
- `super.glue_models()` - Creates immutable model combinations
- `super.glue_tools()` - Permanently binds tools
- `super.glue_memory()` - Establishes permanent persistence
- `super.glue_output()` - Locks response formats

### Utility Methods
- `unglue()` - Detaches components (not available for super.glue)
- `reglue()` - Reconfigures existing bonds
- `apply_glue()` - Deploys the application

## Terminology and Concepts

### Components
- **Glue Bond** - Connection between components
- **Glue Joint** - Integration point
- **Glue Layer** - Architectural level
- **Glue Interface** - Component interaction boundary

### Actions
- **Gluing** - Process of connecting components
- **Applying Glue** - Deploying applications
- **Super Gluing** - Creating immutable connections
- **Ungluing** - Disconnecting components (standard glue only)

### States
- **Glued** - Components successfully connected
- **Super Glued** - Immutably connected
- **Unglued** - Disconnected/available for new connections

## Example Usage
```python
@glue_app("research_assistant")
def create_assistant():
    # Standard flexible bonds
    glue_models({
        "researcher": "perplexity/sonar",
        "writer": "claude-3-sonnet"
    })
    
    # Immutable security components
    super.glue_tools([
        "input_validator",
        "output_sanitizer"
    ])
    
    # Flexible memory layer
    glue_memory("pinecone")
    
    # Apply deployment
    apply_glue()
```

## Benefits
- Intuitive naming convention
- Clear distinction between mutable and immutable bonds
- Consistent metaphor throughout the framework
- Natural vocabulary for documentation and discussion
