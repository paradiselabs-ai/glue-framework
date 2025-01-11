# Example Research Session Using GLUE Strengths

# Example .GLUE application: research_assistant.glue
```
glue app {
    name = "Research Assistant"
    config {
        development = true
        sticky = false
    }
}

// Tools just need to be magnetic
tool web_search {
    provider = serp
    os.serp_api_key
    config {
        magnetic = true  // Can be shared between models
    }
}

tool code_interpreter {
    config {
        magnetic = true  // Can be shared between models
    }
}

// Models define their tool relationships
model researcher {
    provider = openrouter
    role = "Primary researcher who coordinates research efforts"
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.7
    }
    tools {
        web_search = glue
        code_interpreter = velcro
    }
    
}

model assistant {
    provider = openrouter
    role = "Helper who processes research and generates code"
    config {
        model = "meta-llama/llama-3.1-70b-instruct:free"
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
        model = "meta-llama/llama-3.1-70b-instruct:free"
        temperature = 0.3
    }
    tools {
        web_search = tape
    }
}

// Workflow only defines model interactions
workflow {
    // Two-way collaboration
    researcher >< assistant  // Full collaboration
    
    // One-way information flow
    assistant -> writer     // Can push findings to writer
    researcher -> writer    // Can push research to writer
    
    // Pull access
    writer <- assistant     // Writer can pull from assistant
    
    // Prevent direct interaction
    writer <> researcher    // No direct communication
}

// Optional agent for coordination
//agent coordinator {
//    role = "Coordinates information flow between models"
//    can_task = [researcher, assistant, writer]
//    monitors = ["tool_usage", "model_requests"]
//}

apply glue
```

## Initial Request
User: "Research quantum computing and create a tutorial with code examples"

## Session Flow

### 1. Researcher (with GLUE binding to web_search)
```
Researcher: "Let me search for quantum computing fundamentals..."
[Uses web_search - GLUE binding means:]
- Maintains search context between queries
- Can build on previous searches
- Search results persist in context

[Searches]:
- "quantum computing basics"
- "quantum gates explained"
- "quantum superposition examples"
```

### 2. Assistant (with VELCRO binding to web_search and code_interpreter)
```
[Researcher pushes findings to Assistant]
Assistant: "I'll process this research and generate code examples..."

[Uses web_search - VELCRO binding means:]
- Can search when needed
- Connection drops after each search
- Must reestablish context
- Good for ad-hoc searches

[Uses code_interpreter - VELCRO binding means:]
- Can disconnect/reconnect to try different approaches
- Maintains some context but can reset if needed
- Flexible for iterative development
```

### 3. Writer (with TAPE binding to web_search)
```
[Assistant pushes code examples to Writer]
Writer: "I'll verify some details before documenting..."

[Uses web_search - TAPE binding means:]
- Quick fact verification only
- No context between searches
- Connection breaks immediately after use
- Perfect for single lookups
```

## Example Interaction

```
User: "Create a tutorial about quantum gates"

Researcher: "Initiating comprehensive research..."
[GLUE binding allows multiple related searches while building context]
- Searches quantum gates
- Searches implementations
- Each search builds on previous context
- Creates thorough research base

[Researcher pushes research to Assistant]
Assistant: "Processing research and generating code examples..."
[VELCRO binding to code_interpreter]
- Tries implementing basic quantum gate
- Connection drops (error in code)
- Reconnects with new approach
- Iteratively improves code
[VELCRO binding to web_search]
- Quick search for specific implementation details
- Connection drops after each search
- Perfect for verifying specific details

[Assistant pushes to Writer]
Writer: "Documenting the tutorial..."
[TAPE binding to web_search]
- Quick fact check: "Verify quantum gate notation"
- Connection immediately breaks
- Another quick check: "Standard qubit representation"
- Connection breaks again
[Writer pulls from Assistant]
- Gets latest code examples
- Incorporates into documentation

## Key Benefits of Different Bindings

1. GLUE (Researcher + web_search):
   - Maintains deep context across multiple searches
   - Builds comprehensive understanding
   - Perfect for thorough research

2. VELCRO (Assistant + tools):
   - Flexible tool usage
   - Can retry/reset when needed
   - Good for iterative development
   - Maintains some context but can refresh

3. TAPE (Writer + web_search):
   - Quick, atomic operations
   - No context maintenance needed
   - Perfect for verification tasks
   - Clean breaks after each use

This shows how binding strengths naturally support different work patterns:
- GLUE for deep, contextual work
- VELCRO for flexible, iterative work
- TAPE for quick, atomic tasks
