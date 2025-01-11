# Understanding Magnetic Fields in GLUE

## Core Concepts

### Conversation Memory vs Magnetic Tools

First, let's clarify two separate concepts:

1. **Conversation Memory** (Built into GLUE)
   - All models automatically maintain conversation context
   - Multi-turn conversations work out of the box
   - No configuration needed - it's a core feature

2. **Magnetic Tools** (Configured in app)
   - Models can pass tools between themselves
   - Tools can keep persistant data between models in the same run
   - Tools can persist data between runs if needed
   - Can be configured as needed

## The Whiteboard Analogy

Think of GLUE like a smart office with:
- A whiteboard (the workspace)
- Regular tools (non-magnetic tools)
- Magnetic tools that stick to the whiteboard

The workspace is always ready for magnetic tools - you don't need to declare it as magnetic. Just like a whiteboard is always ready for magnets, but you only use that feature when you have magnetic tools.

## Double-Side Tape vs Magnetic

GLUE has two ways tools can work together:

1. **Double-Side Tape**
   - Used to connect specific tools directly
   - Like taping two tools together
   - Example: `double_side_tape = { code_interpreter }` means "this model works directly with the code interpreter"

2. **Magnetic**
   - Used when models need to share tools that keep persistant data
   - Like tools sharing the same whiteboard space
   - Example: `magnetic = true` means "this tool can keep its data persistent when being used by other models"

## Simple Example: Code Interpreter

```glue
glue app {
    name = "Code Interpreter Test"
    tools = code_interpreter
    model = code_assistant
}

code_assistant {
    openrouter
    os.api_key
    model = "liquid/lfm-40b:free"
    temperature = 0.7
    double_side_tape = { code_interpreter }  // Direct connection to code interpreter
}

code_interpreter {
    magnetic = true   // Can share resources with other magnetic tools
    sticky = true     // Code persists between runs
    supported_languages = ["python", "javascript"]
}
```

In this example:
1. The model has conversation memory automatically (GLUE core feature)
2. Double-side tape connects the model to the code interpreter
3. The code interpreter is magnetic and sticky to persist code between runs

## When to Use What

1. **Conversation Memory**
   - Always on by default
   - Handles multi-turn conversations
   - No configuration needed

2. **Double-Side Tape**
   - When tools need to work together directly
   - For tool chains and workflows
   - Configured with `double_side_tape = { tool_name }`

3. **Magnetic Tools**
   - When tools need to share resources
   - When data needs to persist between runs
   - Configured with `magnetic = true` and optionally `sticky = true`

## Example: Research Assistant

```glue
glue app {
    name = "Research Assistant"
    tools = [web_search, file_handler, code_interpreter]
    model = research_assistant
}

research_assistant {
    openrouter
    model = "claude-3"
    // Connect to all tools directly
    double_side_tape = { web_search, file_handler, code_interpreter }
}

web_search {
    // No magnetic properties needed - doesn't share resources
}

file_handler {
    magnetic = true
    sticky = true   // Files persist between runs
}

code_interpreter {
    magnetic = true
    sticky = true   // Code persists between runs
}
```

This shows how all three concepts work together:
1. The model remembers conversation context automatically
2. Double-side tape connects the model to its tools
3. Magnetic tools share and persist resources as needed

## Summary

- Conversation memory is automatic - all models remember context
- Double-side tape connects tools that work together
- Magnetic tools share resources when needed
- The workspace is always ready for magnetic tools
- Only use `magnetic = true` when tools need to share resources
- Only use `sticky = true` when those resources should persist
