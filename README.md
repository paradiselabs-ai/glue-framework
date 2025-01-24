# GLUE Framework

GLUE (GenAI Linking & Unification Engine) is a powerful framework for building multi-model AI applications with natural communication patterns and intuitive tool usage.

Built with [SmolAgents](https://github.com/smol-ai/smolagents) - A lightweight framework for building AI agents with tool use and memory.

## Features

- **Natural Team Structure**: Organize AI models into teams with clear roles and responsibilities
- **Intuitive Tool Usage**: Use tools with different adhesive bindings (GLUE, VELCRO, TAPE) for flexible persistence
- **Magnetic Information Flow**: Control how information flows between teams with push and pull patterns
- **Simple Expression Language**: Write clear, declarative AI applications with the GLUE DSL
- **Built-in Tools**: Web search, file handling, and code interpretation out of the box
- **Extensible Design**: Create custom tools and add new model providers easily

## Quick Start

1. Install GLUE:
```bash
pip install glue-framework
```

2. Set up your API keys:
```bash
# Required
export OPENROUTER_API_KEY=your_key_here

# Optional (for web search)
export SERP_API_KEY=your_key_here
export TAVILY_API_KEY=your_key_here
```

3. Create a GLUE application (e.g., `app.glue`):
```glue
glue app {
    name = "My First App"
    config {
        development = true
    }
}

// Define tools
tool web_search {
    provider = serp  // Uses SERP_API_KEY from environment
}

// Define models
model researcher {
    provider = openrouter
    role = "Research topics online"
    adhesives = [glue, velcro]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.7
    }
}

// Define teams
magnetize {
    research {
        lead = researcher
        tools = [web_search]
    }
}

apply glue
```

4. Run your application:
```bash
glue run app.glue
```

## Core Concepts

### 1. Models and Adhesive Tool Usage

Models are AI agents that can use tools with different adhesive bindings:

- **GLUE**: Team-wide persistent results
- **VELCRO**: Session-based persistence
- **TAPE**: One-time use, no persistence

```glue
model researcher {
    adhesives = [glue, velcro]  // Available binding types
}
```

### 2. Teams and Communication

Teams organize models and their tools:

```glue
magnetize {
    research {
        lead = researcher
        members = [assistant]
        tools = [web_search]
    }
}
```

### 3. Information Flow

Control how teams share information:

```glue
magnetize {
    research {
        lead = researcher
    }
    
    docs {
        lead = writer
    }
    
    flow {
        research -> docs  // Push results
        docs <- pull     // Pull when needed
    }
}
```

## Example Applications

### 1. Research Assistant
- Multi-model research system
- Fact-checking and verification
- Documentation generation

### 2. Code Generator
- Architecture design
- Code generation and review
- Testing and validation

### 3. Content Pipeline
- Content research and creation
- Editing and improvement
- Fact verification

## Documentation

- [Core Concepts](docs/framework/01_core_concepts.md)
- [Expression Language](docs/framework/02_expression_language.md)
- [Tool System](docs/framework/03_tool_system.md)
- [Example Applications](docs/framework/04_examples.md)
- [Best Practices](docs/framework/05_best_practices.md)

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
