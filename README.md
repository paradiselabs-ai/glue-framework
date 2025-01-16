
# GLUE Framework & Expression Language

## Overview

GLUE consists of two powerful components:

1. **GLUE Framework** ((G)enerativeAI (L)inking & (U)nification (E)ngine):
   - Advanced multi-model orchestration 
   - Magnetic field-based resource management
   - Intelligent tool sharing and binding
   - Built-in conversation and memory management

2. **GLUE Expression Language** ((G)enerativeAI (L)anguage (U)sing (E)xpressions):
   - Intuitive, declarative syntax for AI app development
   - Reduces boilerplate through magnetic bindings
   - Natural workflow definitions
   - Powerful chain operations

## Quick Start

1. Install GLUE:

> NOTE: CURRENTLY UNRELEASED. V1.0.0 WILL BE RELEASED VERY SOON THROUGH PYPI AND INSTALLED WITH PIP OR YOUR PREFERRED INSTALLER

2. Set up your environment (.env):

```env
OPENROUTER_API_KEY=your_key_here 
SERP_API_KEY=your_key_here  # For web search capabilities
```

## Simple Examples Using (G)enerativeAI (L)anguage (U)sing (E)xpressions (Or just, GLUE. You write GLUE apps in the GLUE Framework, using GLUE):

### Basic Chatbot (simple.glue)

```glue
// GLUE APPS ARE WRITTEN BY STACKING SIMPLE CODE BLOCKS AND THEN GLUE THEM TOGETHER WITH 'apply glue'
glue app {   // FIRST CODE BLOCK DEFINES THE APPLICATION NAME AND CONFIGURATIONS
    name = "Simple Chat"
    config {
        development = true
    }
}

// NEXT WOULD BE TOOL CONFIGURATION BLOCKS (NOT NEEDED HERE)

model chatbot { // NEXT CODE BLOCK DEFINES THE MODELS (ALSO CALLED ASSISTANTS) BY NAME (model <name>)
    provider = openrouter // MODELS (ASSISTANTS) DO NOT NEED TO DEFINE THE API KEY USING THE EXPRESSION LANGUAGE, ONLY THE PROVIDER
    role = "You are a helpful AI assistant" // SYSTEM PROMPT FOR THIS MODEL (ASSISTANT)
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.7
    }
}

// LAST CODE BLOCK DEFINES THE WORKFLOW AND CONFIGURES THE MAGNETIC FIELD (NOT NEEDED HERE)

// No tools or complex bindings needed for basic chat, thus no workflow needed

apply glue // TELLS THE CLI TO EXECUTE THE .glue APPLICATION
```

### Research Assistant (research.glue)

```glue
glue app { // APP CONFIG BLOCK
    name = "Research Assistant"
    config {
        development = true
        sticky = true // THE STICKY FLAG CONFIGURES THE APP TO PERSIST CONTEXT AND MEMORY BETWEEN RUNS
    }
}

// TOOL CONFIG BLOCKS

tool web_search { // TOOL CONFIG BLOCK
    provider = serp 
    os.serp_api_key // WEB SEARCH TOOL DEFINES THE PROVIDER AND API KEY. THIS IS TEMPORARY AND WILL ONLY NEED THE PROVIDER IN THE FUTURE
    config {
        magnetic = true  // MAGNETIC TOOLS CAN BE SHARED BETWEEN MODELS WHILE RETAINING THEIR INTERNAL PERSISTENCE IF DESIRED
    }                    // TOOL PERSISTENCE IS CONFIGURED WITH THE MODEL'S (ASSISTANT'S) DECLARED ADHESIVE STRENGTH
}

tool code_interpreter { // SECOND TOOL
    config {
        magnetic = true 
    }
}

tool file_handler { // THIRD TOOL
    config {
        magnetic = true
    }
}

// MODEL CONFIG BLOCKS - MODEL CONFIGS DECLARE RULES FOR TOOL USE BASED ON ADHESIVE STRENGTH

model researcher { // FIRST MODEL BLOCK
    provider = openrouter
    role = "Primary researcher who conducts different code and programming and computer science research to help the user answer find ways to implement specific operations into their projects, and supports the coder by checking its code in the code_interpreter tool for accuracy and provides feedback. Researcher may be told that a fact check showed it's original results were inaccurate or out-of-date, and if so, the researcher begins the process again. Can ask coder1 for research assistance."
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.7
    }
    // TOOLS CAN BE SHARED MAGNETICALLY, BUT EACH ASSISTANT USES A TOOL ACCORDING TO ITS ADHESIVE STRENGTH
    tools {
        web_search = glue      // Permanent binding (CONTEXT REMAINS BETWEEN USES)
        code_interpreter = velcro  // Flexible binding (RECIEVES CONTEXT FROM PREVIOUS MODEL USE, BUT THOSE CHANGES DO NOT PERSIST AS A GLUE BINDING WOULD)
    }
}

model coder1 { // SECOND MODEL BLOCK
    provider = openrouter
    role = "Processes and assists researcher in researching, and generates code to test the found solutions. Collaborates with coder2 in generating effective and accurate code."
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.2
    }
    tools {
        web_search = velcro // CAN SEE RESEARCHERS SEARCH QUERIES, AND CAN SEARCH OTHER THINGS BUT THIS MODELS SEARCHES DONT PERSIST 
        code_interpreter = glue  // CODE INTERPRETER IS GLUED, ALL CHANGES PERSIST. THE RESEARCHER (velcro) CAN USE THE TOOL AND SEE THE PERSISTANCE FROM THIS MODEL, 
                                 // BUT RESEARCHER'S CHANGES WILL NOT PERSIST IF ASSISTANT
    }
}

model coder2 {
    provider = openrouter
    role = "Collaborates with coder1 by evaluating its code. Suggests improvements, bounces ideas back and forth with coder1, works iteratively to ensure final code is accurate and effective." 
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.1
    }
    tools {
        code_interpreter = glue
    }
}

model writer {
    provider = openrouter
    role = "Documentation writer receives data from the researcher and the coder, organizes the findings, and performs a quick fact check. If the fact check fails, it informs the researcher. If it passes, it documents the data from the researcher and coder by creating a new file and saving it to the current directory. Files should be created in a new directory named 'Data/'. If Data/ does not exist first create it inside the current working directory. Files should always be written in a <pdf, txt, etc. - unspecified defaults to markdown>.
    config {
        model = "anthropic/claude-3-sonnet"
        temperature = 0.3
    }
    tools {
        web_search = tape  // Temporary binding - NO PERSISTENCE, RECEIVES THE TOOL IN A BLANK SLATE, RETURNS THE TOOL IN A BLANK SLATE
        file_handler = glue  // 
    }
}

// Define model interactions
workflow {
    // Two-way collaboration. "><" represents two objects being attracted magnetically 
    researcher >< coder1  // Bidirectional binding - THESE ASSISTANTS CAN INTERACT BACK AND FORTH AUTONOMOUSLY
    coder1 >< coder2
    
    // One-way information flow. "->" represents a magnetic push, or a one-way attraction. 
    coder1 -> writer     // Push data - THE ASSISTANT PUSHES DATA TO THE WRITER, THE WRITER CANNOT RESPOND
    writer -> researcher // (see writer "role" above) IF WRITERS FACT CHECK PROVES FALSE, IT PUSHES THAT DATA TO THE RESEARCHER TO TRY AGAIN
    // Pull access - WHEN THE MODEL CANNOT INTERACT DIRECTLY WITH A MODEL IT NEEDS DATA FROM FOR ITS TASK, PULL INITIATES A PUSH FROM THE  
    // OTHER MODEL. PULLING STILL DOES NOT ALLOW INTERACTION WITH THE OTHER MODEL, IT SIMPLY "POKES" THE MODEL TO PERFORM A PUSH OF THE DATA IT HAS. 
    writer <- coder1   // Pull data - IF THE WRITER HASNT RECIEVED DATA FROM THE OTHER MODELS, IT CAN REQUEST A PUSH BY PULLING THE APPROPRIATE MODEL.
    
    // Prevent direct interaction 
    writer <> coder2   // Repulsion - THESE ASSISTANTS CANNOT EVER INTERACT DIRECTLY WITH EACH OTHER
}

apply glue
```

## CLI Usage

GLUE provides a powerful CLI for managing your AI applications:

```bash
# Run a GLUE application
glue run app.glue

# Create a new GLUE project
glue new myproject

# List available models
glue list-models

# List available tools
glue list-tools

# Create a new component
glue create --type tool mytool
glue create --type agent myagent
```

## Key Features

### Adhesive Binding System

- `glue`: Permanent bindings with full context sharing
- `velcro`: Flexible bindings that can be reconnected
- `tape`: Temporary bindings for one-time operations
- `magnetic`: Dynamic bindings with resource sharing

### Magnetic Field System

- Resource organization through magnetic fields
- Dynamic tool sharing and access
- Context-aware resource management
- Intelligent cleanup and state management

### Expression Language

- Intuitive model-tool bindings
- Natural workflow definitions
- Resource sharing patterns
- Chain operations

## Upcoming Features

Currently in development:

1. Advanced Pattern Recognition
   - Intelligent workflow optimization
   - Dynamic binding strength adjustment
   - Context-aware resource allocation

2. Enhanced Tool System
   - Expanded tool ecosystem
   - Custom tool development framework
   - Advanced permission management
   - Full integration with Anthropic's [Model Context Protocol](https://github.com/modelcontextprotocol)

3. Memory Management
   - Sophisticated context preservation
   - Cross-model memory sharing
   - Enhanced conversation history

4. Advanced Expression Language Features
   - Complex binding patterns
   - Dynamic workflow adaptation
   - Enhanced error handling

## Contributing

Contributions will be welcome immediately after our first official release!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Documentation

[FULL DOCS COMING SOON]
