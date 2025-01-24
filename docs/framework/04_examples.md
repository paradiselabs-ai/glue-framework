# GLUE Example Applications

## Overview

This guide provides complete examples of GLUE applications, demonstrating different use cases and patterns. Each example shows how to combine models, tools, and teams effectively.

## 1. Research Assistant

A multi-model system for research, fact-checking, and documentation.

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

### How it Works
1. Research team collaborates on research:
   - Researcher leads with GLUE-bound web searches
   - Assistant helps analyze with VELCRO-bound tools
   - Results build up in shared knowledge

2. Documentation team creates content:
   - Writer uses TAPE for quick fact verification
   - Pulls research results when needed
   - Creates documentation files

## 2. Code Generation System

A system for generating, reviewing, and testing code.

```glue
glue app {
    name = "Code Generator"
    config {
        development = true
        sticky = true
    }
}

// Tools
tool code_interpreter {
    config {
        languages = ["python", "javascript", "typescript"]
        sandbox = true
    }
}

tool file_handler {}

// Models
model architect {
    provider = openrouter
    role = "Design software architecture and review code."
    adhesives = [glue]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.7
    }
}

model developer {
    provider = openrouter
    role = "Generate and refactor code."
    adhesives = [glue, velcro]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.5
    }
}

model tester {
    provider = openrouter
    role = "Write and run tests, verify code quality."
    adhesives = [velcro, tape]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.3
    }
}

magnetize {
    design {
        lead = architect
        tools = [file_handler]
    }

    development {
        lead = developer
        tools = [code_interpreter, file_handler]
    }

    testing {
        lead = tester
        tools = [code_interpreter]
    }

    flow {
        design -> development
        development -> testing
        testing <- pull  // Can pull for regression testing
    }
}

apply glue
```

### How it Works
1. Design phase:
   - Architect creates design with GLUE persistence
   - Design flows to development team

2. Development phase:
   - Developer generates code with GLUE/VELCRO tools
   - Code flows to testing team

3. Testing phase:
   - Tester runs tests with VELCRO persistence
   - Uses TAPE for quick checks
   - Can pull previous versions for regression testing

## 3. Content Creation Pipeline

A system for creating, editing, and publishing content.

```glue
glue app {
    name = "Content Pipeline"
    config {
        development = true
        sticky = true
    }
}

// Tools
tool web_search {
    provider = serp
}

tool file_handler {}

// Models
model researcher {
    provider = openrouter
    role = "Research topics and gather information."
    adhesives = [glue]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.7
    }
}

model writer {
    provider = openrouter
    role = "Create content from research."
    adhesives = [velcro]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.5
    }
}

model editor {
    provider = openrouter
    role = "Edit and improve content."
    adhesives = [velcro, tape]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.3
    }
}

model fact_checker {
    provider = openrouter
    role = "Verify facts and sources."
    adhesives = [tape]
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.2
    }
}

magnetize {
    research {
        lead = researcher
        tools = [web_search]
    }

    writing {
        lead = writer
        tools = [file_handler]
    }

    editing {
        lead = editor
        members = [fact_checker]
        tools = [web_search, file_handler]
    }

    flow {
        research -> writing
        writing -> editing
        editing <- pull  // Can pull research if needed
    }
}

apply glue
```

### How it Works
1. Research phase:
   - Researcher builds knowledge with GLUE
   - Research flows to writing team

2. Writing phase:
   - Writer creates content with VELCRO
   - Content flows to editing team

3. Editing phase:
   - Editor improves content with VELCRO
   - Fact checker verifies with TAPE
   - Can pull additional research if needed

## Best Practices

1. Team Organization:
   - Group related roles together
   - Use appropriate adhesive types
   - Enable natural information flow

2. Tool Usage:
   - Match adhesive to task needs
   - Share results appropriately
   - Clean up resources properly

3. Model Configuration:
   - Set appropriate temperatures
   - Define clear roles
   - Enable necessary adhesives

## Next Steps
- [Best Practices](05_best_practices.md)
- [API Reference](06_api_reference.md)
- [Deployment Guide](07_deployment.md)
