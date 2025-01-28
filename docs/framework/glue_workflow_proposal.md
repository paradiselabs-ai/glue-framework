# GLUE Workflow Proposal: Natural Agent Interactions

## Core Concept
Agents should interact in a natural, intuitive way that follows how human teams collaborate.

## Proposed Workflow Syntax

```glue
workflow {
    // Define team structure
    team research_team {
        lead = researcher      // Team lead
        members = [assistant]  // Team members
        tools = [web_search, code_interpreter]  // Shared team tools
    }
    
    team writing_team {
        lead = writer
        tools = [file_handler]
    }
    
    // Define cross-team interactions
    flow {
        research_team -> writing_team  // Research team can push findings
        writing_team <- research_team  // Writing team can pull research
    }
}
```

## Key Benefits

1. Natural Team Structure
- Teams are a natural way to group collaborating agents
- Team members can always communicate (like real teams)
- Teams share resources naturally (like real teams share tools)

2. Clear Resource Boundaries
- Tools are explicitly assigned to teams
- Cross-team resource sharing follows clear patterns
- No counter-intuitive scenarios possible

3. Aligned with Agent Behavior
- Follows natural organizational patterns
- Communication within teams is implicit
- Resource sharing follows team boundaries

4. Simple Mental Model
- Teams = Full collaboration
- Cross-team flow = Controlled sharing
- No need to separately configure chat and resources

## Implementation Details

1. Team Mechanics:
- Team members have full chat capabilities
- Team members share all team tools
- Team lead can control resource allocation

2. Cross-team Flow:
- -> (push): Source team can send data/results
- <- (pull): Target team can request data
- No need for explicit chat config

3. Tool Binding:
- Team tools use velcro binding by default
- Cross-team shared tools use tape binding
- Can be overridden with tool config

## Example Use Cases

1. Research Project:
```glue
workflow {
    team researchers {
        lead = senior_researcher
        members = [assistant, analyst]
        tools = [web_search, code_interpreter]
    }
    
    team writers {
        lead = editor
        members = [writer, reviewer]
        tools = [file_handler]
    }
    
    flow {
        researchers -> writers  // Push findings
        writers <- researchers  // Pull details when needed
    }
}
```

2. Code Review:
```glue
workflow {
    team developers {
        lead = senior_dev
        members = [dev1, dev2]
        tools = [code_interpreter, git_tool]
    }
    
    team reviewers {
        lead = tech_lead
        members = [reviewer1, reviewer2]
        tools = [code_analyzer]
    }
    
    flow {
        developers -> reviewers  // Submit code
        reviewers <- developers  // Request clarification
    }
}
```

## Benefits Over Current System

1. More Intuitive
- Teams are a natural way to think about collaboration
- No need to understand magnetic fields for basic use
- Clear boundaries between groups

2. Better Defaults
- Communication within teams just works
- Resource sharing follows natural patterns
- No surprising edge cases

3. More Flexible
- Easy to add/remove team members
- Simple to adjust tool access
- Clear cross-team interaction patterns

4. Future-Proof
- Easy to add new team-level features
- Natural way to add role-based permissions
- Simple to extend with new interaction patterns
