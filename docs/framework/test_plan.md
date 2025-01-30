# GLUE Framework Test Plan

## Core Components to Test

### 1. Team System
- Team creation and configuration
- Member management
- Tool distribution to teams
- Team communication
- Magnetic field interactions

### 2. Tool System
- Basic tool functionality
- Tool binding with adhesives
- Tool result sharing
- Tool persistence levels

### 3. Expression Language
- Parser functionality
- Keyword handling
- Model configuration
- Tool configuration
- Team/magnetic configuration

### 4. Provider System
- OpenRouter integration
- SmolAgents integration
- Provider-agnostic interfaces
- Model configuration

## Test Structure

### 1. Unit Tests
```python
# tests/core/test_team.py
def test_team_creation():
    """Test basic team creation"""
    team = Team(name="test_team")
    assert team.name == "test_team"
    assert len(team.members) == 0
    assert len(team.tools) == 0

def test_team_tool_distribution():
    """Test tool distribution to team members"""
    team = Team(name="test_team")
    tool = WebSearchTool()
    
    # Add tool to team
    team.add_tool("web_search", tool)
    assert "web_search" in team.tools
    
    # Add member
    model = OpenRouterModel(...)
    team.add_member(model)
    assert tool.name in model.available_tools

def test_adhesive_binding():
    """Test adhesive tool binding"""
    team = Team(name="test_team")
    tool = WebSearchTool()
    
    # Test GLUE binding
    result = team.use_tool("web_search", AdhesiveType.GLUE, "test")
    assert result in team.shared_results
    
    # Test VELCRO binding
    result = team.use_tool("web_search", AdhesiveType.VELCRO, "test")
    assert result in team._session_results
```

### 2. Integration Tests
```python
# tests/integration/test_research_flow.py
def test_research_assistant():
    """Test complete research assistant flow"""
    # Create app from GLUE file
    app = parse_glue_file("examples/research_assistant.glue")
    
    # Test team setup
    assert "researchers" in app.teams
    assert "docs" in app.teams
    
    # Test tool distribution
    research_team = app.teams["researchers"]
    assert "web_search" in research_team.tools
    
    # Test magnetic flow
    docs_team = app.teams["docs"]
    assert docs_team in research_team.attracted_to
    
    # Test complete flow
    result = app.process("Research quantum computing")
    assert result is not None
```

### 3. System Tests
```python
# tests/system/test_complete_app.py
def test_complete_app():
    """Test complete application lifecycle"""
    # Create app
    app = GlueApp(
        name="test_app",
        config=AppConfig(sticky=True)
    )
    
    # Add teams
    app.add_team("research", lead="researcher", tools=["web_search"])
    app.add_team("docs", lead="writer", tools=["file_handler"])
    
    # Configure magnetic field
    app.set_attraction("research", "docs")
    
    # Run complete workflow
    result = app.run("Research and document quantum computing")
    assert "research_results.md" in os.listdir("workspace")
```

## Test Categories

### 1. Core Functionality
- [x] Team creation and management
- [x] Tool binding and execution
- [x] Model configuration
- [x] Adhesive persistence

### 2. Integration Points
- [x] Provider integration
- [x] Tool system integration
- [x] Expression language parsing
- [x] Magnetic field rules

### 3. Edge Cases
- [x] Error handling
- [x] Resource cleanup
- [x] Invalid configurations
- [x] Missing dependencies

## Implementation Steps

1. Create Test Structure
```bash
tests/
├── core/
│   ├── test_team.py
│   ├── test_tool.py
│   └── test_model.py
├── integration/
│   ├── test_research_flow.py
│   └── test_provider_flow.py
└── system/
    └── test_complete_app.py
```

2. Implement Core Tests
- [ ] Team functionality
- [ ] Tool system
- [ ] Model integration
- [ ] Adhesive binding

3. Implement Integration Tests
- [ ] Complete research flow
- [ ] Provider integration
- [ ] Expression parsing
- [ ] Magnetic field rules

4. Implement System Tests
- [ ] Complete application
- [ ] Resource management
- [ ] Error scenarios
- [ ] Performance metrics

## Usage

```bash
# Run all tests
pytest tests/

# Run specific category
pytest tests/core/

# Run with coverage
pytest --cov=glue tests/
```

## Next Steps

1. Create test directory structure
2. Implement core tests first
3. Run tests to identify issues
4. Fix any broken functionality
5. Add integration tests
6. Add system tests
7. Create CI pipeline

This will give us a solid foundation to:
- Find missing imports
- Identify unused files
- Verify core functionality
- Support future development
