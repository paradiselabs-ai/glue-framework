# GLUE Framework

GLUE (GenAI Linking & Unification Engine) is a powerful framework for building AI applications with an intuitive expression language.

## Features

- **Intuitive Expression Language**: Build AI applications using a simple, declarative syntax
- **Multi-Model Collaboration**: Seamlessly combine different AI models
- **Built-in Tool System**: Easily integrate and use tools like web search, file operations, etc.
- **Provider Support**: Currently, GLUE only works with OpenRouter, however we are in active development and other providers will be added ASAP.
- **Magnetic Field System**: Unique approach to managing AI resources and interactions

## Installation

```bash
# Clone the repository
git clone https://github.com/paradiseLabs/glue.git
cd glue

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

1. Create a `.env` file with your API keys:
```env
OPENROUTER_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
```

2. Create a GLUE file (e.g., `app.glue`):
```glue
glue app {
    name = "Research Assistant"
    tools = web_search
    model = researcher
}

researcher {
    openrouter
    os.api_key
    model = "liquid/lfm-40b:free"
    temperature = 0.7
    double_side_tape = { web_search }
}

web_search {
    tavily
    os.tavily_api_key
}

researcher_role = "You are a research assistant..."

apply glue
```

3. Run your app:
```bash
python -m glue.cli app.glue
```

## Key Concepts

### Models

Models are the core AI components that can:
- Process user input
- Generate responses
- Use tools
- Chain operations

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
- Custom tools

```glue
web_search {
    tavily
    os.tavily_api_key
}
```

### Magnetic Fields

The magnetic field system manages:
- Resource allocation
- Tool interactions
- State management
- Error handling

### Double-Side Tape

Chain operations between models and tools:

```glue
researcher {
    openrouter
    double_side_tape = { web_search >> analyzer }
}
```

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

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- OpenRouter for providing access to various AI models
- The AI/ML community for inspiration and support
