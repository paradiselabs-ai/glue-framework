# GLUE Framework

GLUE (GenAI Linking & Unification Engine) is a powerful, innovative framework for building AI applications with an intuitive expression language and advanced resource management.

## Features

- **Magnetic Field System**: Unique approach to managing AI resources and interactions
- **Intuitive Expression Language**: Build AI applications using a simple, declarative syntax
- **Multi-Model Collaboration**: Seamlessly combine different AI models
- **Context-Aware Processing**: Intelligent context management across models and tools
- **Built-in Tool System**: Easily integrate and use tools like web search, file operations, etc.
- **Provider Support**: Currently supports OpenRouter, with more providers planned

## Key Concepts

### Magnetic Field System

The core innovation of GLUE is its Magnetic Field System, which provides:
- Dynamic resource management
- Context-aware interactions
- Intelligent tool and model coordination
- Advanced state tracking and transitions

### Models

Models are the core AI components that can:
- Process user input
- Generate responses
- Use tools
- Chain operations
- Adapt to context dynamically

```glue
my_model {
    openrouter
    os.api_key
    model = "anthropic/claude-3-opus"
    temperature = 0.7
}
```

### Tools

Tools extend model capabilities:
- Web search
- File operations
- Code interpretation
- Custom tool development
- Intelligent permission management

```glue
web_search {
    tavily
    os.tavily_api_key
}
```

### Expression Language

GLUE's expression language allows for:
- Declarative workflow definitions
- Context-based model and tool interactions
- Dynamic resource binding
- Intuitive configuration of complex AI systems

Apps are written by stacking different blocks of code and then "applying glue". The file is saved as a .glue file. 

The CLI tool allows running GLUE apps from the terminal similar to python. Where with python you execute a file with "python file.py" you run a GLUE application with "glue file.glue".

The CLI tool also allows users to easily build Agents that can be configured beforehand and then modularly used in different GLUE applications without having to configure the Agent each time, as well as a streamlined process for tool creation and easily setting up a GLUE development environment to begin development in.

## Examples

### Research Assistant

```glue
glue app {
    name = "Research Assistant"
    tools = web_search
    model = researcher
}

researcher {
    openrouter
    os.api_key
    double_side_tape = { web_search }
}

web_search {
    tavily
    os.tavily_api_key
}
```

### Code Generator

```glue
glue app {
    name = "Code Generator"
    tools = code_interpreter, file_handler
    model = coder
}

coder {
    openrouter
    os.api_key
    double_side_tape = { 
        code_interpreter >> file_handler 
    }
}
```

## Current Development Status

GLUE is currently in active development. We are focusing on:
- Stabilizing core system integrations
- Enhancing context-aware processing
- Developing advanced rule-based optimizations
- Expanding provider support

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Roadmap

- [ ] Complete core framework integration
- [ ] Expand provider support
- [ ] Develop comprehensive documentation
- [ ] Create more advanced example applications
- [ ] Implement advanced context-aware features

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- OpenRouter for providing access to various AI models
- The AI/ML community for inspiration and support
