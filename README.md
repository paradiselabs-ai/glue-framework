# GLUE Framework & Expression Language

## Overview

GLUE consists of two powerful components:

1. **GLUE Framework** ((G)enerativeAI (L)inking & (U)nification (E)ngine):
   - Advanced multi-model orchestration 
   - Magnetic field-based resource management
   - Intelligent tool sharing and binding
   - Built-in conversation and memory management

2. **GLUE Expression Language** ((G)enerativeAI (L)anguage (U)sing (E)xpressions):
   - Intuitive, declarative syntax for AI app development
   - Reduces boilerplate through magnetic bindings
   - Natural workflow definitions
   - Powerful chain operations

## Quick Start

1. Install GLUE:
```bash
pip install glue-framework
```

2. Set up your environment (.env):
```env
OPENROUTER_API_KEY=your_key_here
SERP_API_KEY=your_key_here  # For web search capabilities
```

## Simple Examples

### Basic Chatbot (simple.glue)
```glue
glue app {
    name = "Simple Chat"
    config {
        development = true
    }
}

model assistant {
    provider = openrouter
    role = "You are a helpful AI assistant"
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.7
    }
}

// No tools or complex bindings needed for basic chat
apply glue
```

### Research Assistant (research.glue)
```glue
glue app {
    name = "Research Assistant"
    config {
        development = true
        sticky = false
    }
}

// Magnetic tools with shared capabilities
tool web_search {
    provider = serp
    os.serp_api_key
    config {
        magnetic = true  // Enable tool sharing
    }
}

tool code_interpreter {
    config {
        magnetic = true
    }
}

// Models with tool bindings
model researcher {
    provider = openrouter
    role = "Primary researcher who coordinates research efforts"
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.7
    }
    tools {
        web_search = glue      // Permanent binding
        code_interpreter = velcro  // Flexible binding
    }
}

model assistant {
    provider = openrouter
    role = "Helper who processes research and generates code"
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.5
    }
    tools {
        web_search = velcro
        code_interpreter = velcro
    }
}

model writer {
    provider = openrouter
    role = "Documentation writer who organizes findings"
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.3
    }
    tools {
        web_search = tape  // Temporary binding
    }
}

// Define model interactions
workflow {
    // Two-way collaboration
    researcher >< assistant  // Bidirectional binding
    
    // One-way information flow
    assistant -> writer     // Push data
    researcher -> writer    // Push data
    
    // Pull access
    writer <- assistant     // Pull data
    
    // Prevent direct interaction
    writer <> researcher    // Repulsion
}

apply glue
```

## CLI Usage

GLUE provides a powerful CLI for managing your AI applications:

```bash
# Run a GLUE application
glue run app.glue

# Create a new GLUE project
glue new myproject

# List available models
glue list-models

# List available tools
glue list-tools

# Create a new component
glue create --type tool mytool
glue create --type agent myagent
```

## Key Features

### Adhesive Binding System
- `glue`: Permanent bindings with full context sharing
- `velcro`: Flexible bindings that can be reconnected
- `tape`: Temporary bindings for one-time operations
- `magnetic`: Dynamic bindings with resource sharing

### Magnetic Field System
- Resource organization through magnetic fields
- Dynamic tool sharing and access
- Context-aware resource management
- Intelligent cleanup and state management

### Expression Language
- Intuitive model-tool bindings
- Natural workflow definitions
- Resource sharing patterns
- Chain operations

## Upcoming Features

Currently in development:
1. Advanced Pattern Recognition
   - Intelligent workflow optimization
   - Dynamic binding strength adjustment
   - Context-aware resource allocation

2. Enhanced Tool System
   - Expanded tool ecosystem
   - Custom tool development framework
   - Advanced permission management

3. Memory Management
   - Sophisticated context preservation
   - Cross-model memory sharing
   - Enhanced conversation history

4. Advanced Expression Language Features
   - Complex binding patterns
   - Dynamic workflow adaptation
   - Enhanced error handling

## Contributing

Contributions are welcome! See our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Documentation

For full documentation, visit our [docs](https://docs.glue-framework.ai).
