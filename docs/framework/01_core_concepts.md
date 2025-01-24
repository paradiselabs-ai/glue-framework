# GLUE Framework Core Concepts

## Overview

GLUE (GenAI Linking & Unification Engine) is built around three core concepts that work together to create powerful AI applications:

1. Models with Adhesive Tool Usage
2. Teams with Natural Communication
3. Magnetic Information Flow

## 1. Models and Adhesive Tool Usage

### Models
Models are AI agents that can:
- Use tools with different adhesive bindings
- Communicate freely with team members
- Participate in information flows

### Adhesive Tool Bindings
Models can use tools with three types of adhesive bindings:

```glue
model researcher {
    adhesives = [glue, velcro]  // Available binding types
}
```

- **GLUE**: Permanent binding with team-wide persistence
  - Results automatically shared with team
  - Perfect for collaborative research
  - Example: Web search results that build team knowledge

- **VELCRO**: Session-based binding with model-level persistence
  - Results persist for current session
  - Private to the model
  - Example: Code interpreter during development

- **TAPE**: One-time binding with no persistence
  - Results used once and discarded
  - No context maintenance
  - Example: Quick fact verification

## 2. Teams and Communication

### Team Structure
```glue
magnetize {
    research {
        lead = researcher
        members = [assistant]
        tools = [web_search, code_interpreter]
    }
}
```

### Key Features
- Models in a team can chat freely
- No explicit communication configuration needed
- Natural collaboration patterns
- Tool results shared based on adhesive type

## 3. Magnetic Information Flow

### Flow Patterns
```glue
magnetize {
    research {
        lead = researcher
        tools = [web_search]
    }
    
    docs {
        lead = writer
        tools = [file_handler]
    }
    
    flow {
        research -> docs  // Push findings
        docs <- pull     // Pull when needed
    }
}
```

### Flow Types
1. **Push Flow** (`->`)
   - Team actively shares results
   - Used for regular information transfer
   - Example: Research team pushing findings

2. **Pull Flow** (`<- pull`)
   - Team can request information
   - On-demand access
   - Example: Docs team pulling research

3. **Repulsion** (`<>`)
   - Prevents unwanted interaction
   - Enforces separation of concerns
   - Example: Keeping teams isolated

## Example: Research Assistant

Here's how these concepts work together in a research assistant application:

```glue
// Models with adhesive capabilities
model researcher {
    provider = openrouter
    role = "Research different topics and subjects online."
    adhesives = [glue, velcro]  // Can use persistent and session tools
}

model writer {
    provider = openrouter
    role = "Write documentation files that summarize findings."
    adhesives = [tape]  // Only needs quick tool access
}

// Tools available to teams
tool web_search {
    provider = serp  // Uses SERP_API_KEY from environment
}

tool file_handler {}

// Team structure and flow
magnetize {
    research {
        lead = researcher
        tools = [web_search]
    }
    
    docs {
        lead = writer
        tools = [file_handler]
    }
    
    flow {
        research -> docs  // Research flows to documentation
    }
}

apply glue

```

How it works:
1. Researcher uses web_search with GLUE
   - Results shared within research team
   - Knowledge builds up over time

2. Writer uses tools with TAPE
   - Quick access to verify facts
   - No need to maintain context

3. Information flows naturally:
   - Research team pushes findings
   - Docs team creates documentation
   - Clean separation of concerns

4. Finally, apply glue so the cli knows where the end of the application is.

## Benefits

1. **Natural Interaction**
   - Models communicate freely within teams
   - Tools used with appropriate persistence
   - Information flows logically

2. **Clean Architecture**
   - Clear separation of concerns
   - Intuitive binding patterns
   - Flexible team structures

3. **Scalable Design**
   - Easy to add new models
   - Simple to extend with new tools
   - Natural to grow team structures

## Next Steps
- [Expression Language Guide](02_expression_language.md)
- [Tool System](03_tool_system.md)
- [Example Applications](04_examples.md)
