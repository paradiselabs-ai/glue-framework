# tests/dsl/test_keywords.py

from src.glue.dsl.keywords import get_keyword_type
from src.glue.dsl.parser import GlueParser

# Test GLUE file with various keyword forms
TEST_GLUE = """
glue app {
    name = "Test App"
    tools = search, file
    agent = researcher
}

researcher {
    openrouter
    api
    chain = { search >> file }
}

file: "output.json"

researcher_prompt = "You are a test researcher."

apply glue
"""

# Alternative syntax test
ALT_SYNTAX_GLUE = """
application {
    title = "Test App"
    components = web, write
    model = assistant
}

assistant {
    openrouter
    key
    sequence = { web >> write }
}

write: "output.json"

assistant_system = "You are a test assistant."

apply glue
"""

def test_keyword_resolution():
    """Test keyword type resolution"""
    # Test app keywords
    assert get_keyword_type('app')[0] == 'app'
    assert get_keyword_type('application')[0] == 'app'
    assert get_keyword_type('agent')[0] == 'app'
    
    # Test provider keywords
    assert get_keyword_type('openrouter')[0] == 'provider'
    
    # Test config keywords
    assert get_keyword_type('api')[0] == 'config'
    assert get_keyword_type('key')[0] == 'config'
    assert get_keyword_type('token')[0] == 'config'
    
    # Test operation keywords
    assert get_keyword_type('chain')[0] == 'config'
    assert get_keyword_type('sequence')[0] == 'config'
    assert get_keyword_type('pipeline')[0] == 'config'
    
    # Test role keywords
    assert get_keyword_type('role')[0] == 'role'
    assert get_keyword_type('system')[0] == 'role'
    assert get_keyword_type('prompt')[0] == 'role'
    assert get_keyword_type('instruction')[0] == 'role'

def test_standard_syntax():
    """Test parsing standard syntax"""
    parser = GlueParser()
    app = parser.parse(TEST_GLUE)
    
    # Check app parsing
    assert app.name == "Test App"
    assert app.tools == ["search", "file"]
    assert app.model == "researcher"
    
    # Check model parsing
    model = parser.models["researcher"]
    assert model.provider == "openrouter"
    assert model.api_key == "env:OPENROUTER_API_KEY"
    # Updated assertion to expect type field
    assert model.chain == {"type": "sequential", "tools": ["search", "file"]}
    assert model.role == "You are a test researcher."
    
    # Check tool parsing
    assert parser.tools["file"].path == "output.json"

def test_alternative_syntax():
    """Test parsing alternative syntax"""
    parser = GlueParser()
    app = parser.parse(ALT_SYNTAX_GLUE)
    
    # Check app parsing with alternative keywords
    assert app.name == "Test App"
    assert app.tools == ["web", "write"]
    assert app.model == "assistant"
    
    # Check model parsing with alternative keywords
    model = parser.models["assistant"]
    assert model.provider == "openrouter"
    assert model.api_key == "env:OPENROUTER_API_KEY"
    # Updated assertion to expect type field
    assert model.chain == {"type": "sequential", "tools": ["web", "write"]}
    assert model.role == "You are a test assistant."
    
    # Check tool parsing
    assert parser.tools["write"].path == "output.json"

def test_role_variations():
    """Test different role definition styles"""
    variations = [
        ('agent_role', 'role'),
        ('agent_system', 'role'),
        ('agent_prompt', 'role'),
        ('agent_instruction', 'role'),
        ('agent_behavior', 'role'),
        ('agent_personality', 'role')
    ]
    
    for keyword, expected_type in variations:
        keyword_type, _ = get_keyword_type(keyword)
        assert keyword_type == expected_type

def test_invalid_keywords():
    """Test handling of invalid keywords"""
    invalid_keywords = [
        'invalid',
        'unknown',
        'not_a_keyword',
        '123'
    ]
    
    for keyword in invalid_keywords:
        keyword_type, value = get_keyword_type(keyword)
        assert keyword_type == 'unknown'
        assert value == keyword
