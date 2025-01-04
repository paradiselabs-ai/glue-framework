
# Magnetic Patterns in GLUE

## Directional Magnetic Fields

### Flow Operators

- `><` : Bidirectional attraction (can use and receive)
- `<-` : Unidirectional flow (can only receive from)
- `->` : Unidirectional flow (can only send to)
- `<>` : Repulsion (cannot interact)
- `<-->` : Double Direct (Exclusively used for Conversational interaction between models)

### Example Workflow

```glue
workflow {
    researcher <--> writer # researcher and the writer can (only) chat between each other, they cannot share tools unless defined in the attract and repel config below

    attract {
        researcher >< web_search  # researcher can recieve and send web_search  queries 
        writer <- web_search # Writer can receive from but not use web_search 
        writer >< file_handler # Writer can use and receive from file_handler
    }
    repel {
        researcher <> file_handler # Researcher cannot use file_handler
    }
}
```

## Context-Aware Behaviors

### Interaction States

1. Direct Chat (<-->)
   - No tool usage
   - Direct model responses
   - Conversational context

2. Research Mode
   - Researcher uses web_search
   - Results flow to writer
   - Writer creates/updates files

3. File Operations
   - Writer handles file operations
   - Based on conversation context
   - Maintains file history

4. Collaborative Mode (<-->)
   - Models work together
   - Share context and memory
   - Coordinate responses

### State Transitions

```mermaid
graph TD
    A[Chat] -->|Research Request| B[Research]
    B -->|Results Ready| C[File Operation]
    C -->|Complete| A
    A -->|File Request| C
    B -->|Direct Question| A
```

## Magnetic Resource Sharing

### Resource Types

1. Tool Results
   - Search results
   - File contents
   - Operation status

2. Conversation Context
   - Chat history
   - User preferences
   - Current topic

3. Shared Memory
   - File operations
   - Search history
   - Model interactions

### Flow Control

```glue
# Example resource flow configuration 1
resources {
    web_search {
        researcher -> web_search   # Researcher can only send queries
        writer <- web_search    # Writer can only receive results
    }
    
    file_handler {
        writer >< file_handler    # Writer has full access
        researcher <- file_handler # Researcher can see file status
    }
}

# Example resource flow config 2
resources {
    web_search {
        researcher >< web_search #researcher can send and recieve queries
        writer <- web_search # writer can only recieve results
    }

    file_handler {
        researcher <> file_handler # researcher cannot send or recieve from file handler
        writer >< file_handler # writer can send and recieve from file handler
    }
}
```

## Implementation Guidelines

### 1. Context Awareness

- Track conversation state
- Monitor tool usage patterns
- Maintain interaction history
- Adapt model behaviors

### 2. Workflow Management

- Implicit tool selection
- Natural state transitions
- Contextual role switching
- Resource flow control

### 3. Model Collaboration

- Share relevant context
- Coordinate responses
- Maintain conversation flow
- Handle state transitions

### 4. Memory Management

- Track file operations
- Store search history
- Remember user preferences
- Share relevant context

## Example Scenarios

### 1. Basic Research Flow

```glue
# User: "Look up the history of paperclips"
workflow {
    researcher >< web_search -> writer  # Research flow
    writer >< file_handler             # File creation
}
```

### 2. File Modification

```glue
# User: "Add sources to that file"
workflow {
    writer >< file_handler   # Direct file operation
    writer <--> researcher     # Context sharing
}
```

### 3. Mixed Interaction

```glue
# User: "Search but don't save, just tell me"
workflow {
    researcher >< web_search  # Direct research
    researcher <--> user        # Direct response
}
```

## Mode Management System (Added 2024-03-21)

### Mode Hierarchy and Transitions

The GLUE framework implements an intelligent mode management system that governs how resources interact and transition between different states:

1. **Bidirectional Mode (`><`)**
   - Strongest binding mode for stable connections
   - Protected against repel mode transitions
   - Can transition to push/receive for flexible workflows
   - Only overridable by chat mode

2. **Push/Receive Modes (`->`, `<-`)**
   - Dynamic directional flow control
   - Can be updated based on workflow needs
   - Supports flexible tool usage patterns
   - Allows mode changes in response to flow requirements

3. **Repel Mode (`<>`)**
   - Cannot override bidirectional mode
   - Used for explicit interaction blocking
   - Helps enforce workflow boundaries
   - Supports conflict prevention

4. **Chat Mode (`<-->`)**
   - Highest priority interaction mode
   - Can override any existing mode
   - Dedicated to model-to-model communication
   - Preserves direct conversation channels

### Resource Cleanup

The framework now includes enhanced resource cleanup:
- Automatic mode attribute cleanup during field exit
- Proper state reset during resource cleanup
- Improved magnetic property management
- Consistent cleanup across all binding types

### Implementation Example

```python
# Setting up a workflow with mode transitions
async with workspace_context("workflow") as ws:
    # Establish stable bidirectional connection
    await ws.setup_flow(flow(
        researcher.name, web_search.name, "><", 
        AdhesiveType.GLUE_ATTRACT
    ))
    
    # Add push flow (won't override bidirectional)
    await ws.setup_flow(flow(
        web_search.name, writer.name, "->", 
        AdhesiveType.VELCRO_PUSH
    ))
    
    # Try repel (won't affect bidirectional)
    await ws.setup_flow(flow(
        researcher.name, file_handler.name, "<>", 
        AdhesiveType.TAPE_REPEL
    ))
```

## Future Considerations

### 1. Autonomous Collaboration

- Models decide workflow
- Self-organizing chains
- Dynamic role adjustment
- Adaptive tool usage

### 2. Learning Patterns

- Track successful flows
- Adapt to user preferences
- Optimize tool chains
- Improve context awareness

### 3. Enhanced Context

- Multi-session memory
- Cross-model learning
- Workflow optimization
- Resource efficiency
