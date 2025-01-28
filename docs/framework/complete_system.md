# Complete GLUE System

## Core Components Working Together

1. Magnetic Fields
```glue
magnetize {
    research {
        lead = researcher     // First model = field's chat handler
        members = [assistant] // Team members
        tools = [web_search]  // Field's tools
    }
    
    docs {
        lead = writer
        tools = [file_handler]
    }
    
    flow {
        research -> docs     // Resource flow
        docs <- pull        // Fallback pull
    }
}
```

2. Natural Routing
- First field's lead handles general chat
- Tools attract related prompts
- Direct addressing works naturally
- Memory provides context automatically

3. Simple Memory
- Every interaction leaves a trace
- Context flows naturally
- History accessible to all fields
- No special configuration needed

## How It All Works

1. User Input Flow:
```
User prompt
  |
  v
Store in memory
  |
  v
Find attracted field (routing)
  |
  v
Add context from memory
  |
  v
Process in field
  |
  v
Store response
```

2. Resource Sharing:
```
Field A generates result
  |
  v
Follows magnetic flow
  |
  v
Field B receives
  |
  v
(or uses pull fallback)
```

3. Memory Access:
```
Every prompt/response
  |
  v
Stored automatically
  |
  v
Available as context
  |
  v
Natural history access
```

## Example Interactions

1. Simple Chat
```
User: "Hello!"
-> First field handles it
-> Response stored in memory
```

2. Tool Use
```
User: "create a file"
-> Attracts to docs field
-> Gets relevant history
-> writer handles it
-> Operation stored in memory
```

3. History Access
```
User: "what did we do?"
-> Gets formatted history
-> Routes through default handler
-> Includes context
```

4. Resource Flow
```
User: "research quantum computing"
-> research field handles it
-> Results flow to docs
-> Everything stored in memory
```

## Benefits of Integration

1. Natural Behavior
- Everything just works
- No complex config
- Clear responsibilities
- Natural interactions

2. Simple Yet Powerful
- Clean implementation
- Natural metaphors
- Easy to understand
- Easy to extend

3. Complete System
- Chat handling
- Tool routing
- Resource sharing
- Memory/history

The system works like a real team:
- Natural communication
- Clear responsibilities
- Shared resources
- Common memory

Just configure the fields and everything else happens naturally.
