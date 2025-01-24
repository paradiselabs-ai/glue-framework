# GLUE Expression Language Guide

## Overview

The GLUE Expression Language is designed to be intuitive and declarative, making it easy to create complex AI applications. This guide covers the syntax and features of the language.

## Comments

Comments in GLUE use the double forward slash syntax (`//`). Each comment must be on its own line:

```glue
// This is a comment
glue app { // Adding a name for the application is optional (see next line)
    name = "MyApp"    // The app name should match the .glue file name, if included
    config {
        development = true  // Enable development mode
        // sticky = false   // Commented out configuration
    }
}
```

Note: There is no multi-line comment syntax. Each comment line must start with `//`.

## Application Structure

Every GLUE application has this basic structure:

```glue
glue app {
    name = "MyApp"
    config {
        development = true
        sticky = true  // Enable persistence
    }
}

// Define tools, models, and teams...

apply glue  // End of application
```

## 1. Tool Definitions

Tools are defined with the `tool` keyword:

```glue
// Basic tool with default settings
tool file_handler {}

// Tool with provider (uses environment variables for API keys)
tool web_search {
    provider = serp  // Will use SERP_API_KEY from environment
}

// Tool with configuration
tool code_interpreter {
    config {
        languages = ["python", "javascript"]
        sandbox = true
    }
}
```

### Supported Tool Providers
- `serp`: Uses SERP_API_KEY from environment
- `tavily`: Uses TAVILY_API_KEY from environment
- Custom providers can be added

## 2. Model Definitions

Models are defined with the `model` keyword:

```glue
model researcher {
    // Required fields
    provider = openrouter  // Uses OPENROUTER_API_KEY from environment
    role = "Research topics and analyze information"
    
    // Available adhesive types for tool usage
    adhesives = [glue, velcro]
    
    // Optional configuration
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.7
    }
}
```

### Adhesive Types
- `glue`: Team-wide persistent results
- `velcro`: Session-based persistence
- `tape`: No persistence, one-time use

### Supported Model Providers
- `openrouter`: OpenRouter API (multiple models)
- `anthropic`: Claude models
- Custom providers can be added

## 3. Team Structure

Teams are defined in the `magnetize` block:

```glue
magnetize {
    // Research team definition
    research {
        lead = researcher       // Team leader
        members = [assistant]   // Other team members
        tools = [              // Available tools
            web_search,
            code_interpreter
        ]
    }
    
    // Documentation team
    docs {
        lead = writer
        tools = [file_handler]
    }
    
    // Information flow
    flow {
        research -> docs     // Push results to docs
        docs <- pull        // Docs can pull from research
    }
}
```

### Flow Patterns

1. Push Flow:
```glue
team1 -> team2  // team1 pushes to team2
```

2. Pull Flow:
```glue
team1 <- pull   // team1 can pull from others
team2 <- team1  // team2 pulls from team1
```

3. Repulsion:
```glue
team1 <> team2  // teams cannot interact
```

## 4. Configuration Options

### Application Config
```glue
glue app {
    config {
        development = true    // Enable development mode
        sticky = true        // Enable persistence
        debug = true        // Enable debug logging
    }
}
```

### Model Config
```glue
model example {
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.7    // 0.0 to 1.0
        max_tokens = 1000
        presence_penalty = 0.0
        frequency_penalty = 0.0
    }
}
```

### Tool Config
```glue
tool example {
    config {
        timeout = 30        // Seconds
        retry_count = 3
        cache_results = true
    }
}
```

## 5. Complete Example

Here's a complete research assistant application:

```glue
glue app {
    name = "Research Assistant"
    config {
        development = true
        sticky = true
    }
}

// Define tools
tool web_search {
    provider = serp
}

tool file_handler {}

tool code_interpreter {}

// Define models
model researcher {
    provider = openrouter
    role = "Research different topics and subjects online."
    adhesives = [glue, velcro]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.7
    }
}

model assistant {
    provider = openrouter
    role = "Help with research and coding tasks."
    adhesives = [glue, velcro]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.5
    }
}

model writer {
    provider = openrouter
    role = "Write documentation summarizing findings."
    adhesives = [tape]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.3
    }
}

// Define workflow
magnetize {
    research {
        lead = researcher
        members = [assistant]
        tools = [web_search, code_interpreter]
    }

    docs {
        lead = writer
        tools = [web_search, file_handler]
    }

    flow {
        research -> docs
        docs <- pull
    }
}

apply glue
```

## Next Steps
- [Tool System](03_tool_system.md)
- [Example Applications](04_examples.md)
- [Best Practices](05_best_practices.md)
