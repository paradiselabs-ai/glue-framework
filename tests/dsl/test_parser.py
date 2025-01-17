# tests/dsl/test_parser.py

from src.glue.dsl.parser import parse_glue_file, GlueParser

# Test GLUE file content
TEST_GLUE = """
glue app {
    app_name = "Test App"
    tools = web_search, write_file
    model = researcher
}

researcher {
    os.openrouter
    os.api_key
    double_side_tape = { web_search >> write_file }
}

write_file: "test_results.json"

researcher_role = "You are a test researcher."

apply glue
"""

def test_parse_app_block():
    """Test parsing app block"""
    parser = GlueParser()
    app = parser.parse(TEST_GLUE)
    
    assert app.name == "Test App"
    assert app.tools == ["web_search", "write_file"]
    assert app.model == "researcher"

def test_parse_model_block():
    """Test parsing model block"""
    parser = GlueParser()
    app = parser.parse(TEST_GLUE)
    
    model = parser.models["researcher"]
    assert model.provider == "openrouter"
    assert model.api_key == "env:OPENROUTER_API_KEY"
    assert model.role == "You are a test researcher."

def test_parse_chain():
    test_content = """
    glue app {
        name = "Test App"
    }
    
    researcher {
        os.openrouter
        os.api_key
        double_side_tape = { web_search >> write_file }
    }
    
    tool web_search {
        // tool config
    }
    
    tool write_file {
        // tool config
    }
    """
    
    parser = GlueParser()
    app = parser.parse(test_content)
    
    assert "researcher" in app.model_configs
    model = app.model_configs["researcher"]
    assert model.chain is not None
    assert model.chain["type"] == "sequential"
    assert model.chain["tools"] == ["web_search", "write_file"]
    
  
def test_parse_chain_with_empty_tools():
    """Test parsing chain with empty tool list"""
    test_content = """
    glue app {
        name = "Test App"
    }
    
    researcher {
        os.openrouter
        os.api_key
        double_side_tape = { }
    }
    """
    
    parser = GlueParser()
    app = parser.parse(test_content)
    
    assert "researcher" in app.model_configs
    model = app.model_configs["researcher"]
    assert model.chain is None  # Empty chain should result in None

def test_parse_chain_with_single_tool():
    """Test parsing chain with a single tool"""
    test_content = """
    glue app {
        name = "Test App"
    }
    
    researcher {
        os.openrouter
        os.api_key
        double_side_tape = { web_search }
    }
    
    tool web_search {
        provider = openai
    }
    """
    
    parser = GlueParser()
    app = parser.parse(test_content)
    
    assert "researcher" in app.model_configs
    model = app.model_configs["researcher"]
    assert model.chain is not None
    assert model.chain["type"] == "sequential"
    assert model.chain["tools"] == ["web_search"]

def test_parse_chain_with_multiple_tools():
    """Test parsing chain with multiple tools"""
    test_content = """
    glue app {
        name = "Test App"
    }
    
    researcher {
        os.openrouter
        os.api_key
        double_side_tape = { web_search >> code_gen >> write_file }
    }
    """
    
    parser = GlueParser()
    app = parser.parse(test_content)
    
    assert "researcher" in app.model_configs
    model = app.model_configs["researcher"]
    assert model.chain is not None
    assert model.chain["type"] == "sequential"
    assert model.chain["tools"] == ["web_search", "code_gen", "write_file"]

def test_parse_tool():
    """Test parsing tool block"""
    parser = GlueParser()
    app = parser.parse(TEST_GLUE)
    
    tool = parser.tools["write_file"]
    assert tool.path == "test_results.json"

def test_parse_file(tmp_path):
    """Test parsing GLUE file"""
    # Create test file
    test_file = tmp_path / "test.glue"
    test_file.write_text(TEST_GLUE)
    
    # Parse file
    app = parse_glue_file(str(test_file))
    
    assert app.name == "Test App"
    assert app.tools == ["web_search", "write_file"]
    assert app.model == "researcher"

def test_invalid_syntax():
    """Test handling invalid syntax"""
    invalid_glue = """
    glue app {
        invalid syntax here
    }
    """
    
    parser = GlueParser()
    app = parser.parse(invalid_glue)
    
    # Should still create app with defaults
    assert app.name == "glue_app"
    assert app.tools == []
    assert app.model is None
    
def test_parse_workflow():
    """Test parsing workflow configuration"""
    test_content = """
    glue app {
        name = "Test App"
    }
    
    workflow {
        researcher >< web_search
        writer <- web_search
    }
    """
    
    parser = GlueParser()
    result = parser.parse(test_content)
    
    assert result.workflow is not None
    assert len(result.workflow.attractions) > 0
    assert ("researcher", "web_search") in result.workflow.attractions
    
def test_parse_complex_workflow():
    """Test parsing complex workflow configuration"""
    test_content = """
    glue app {
        name = "Test App"
    }
    
    workflow {
        researcher >< web_search
        writer <- web_search
        researcher <> file_handler
    }
    """
    
    parser = GlueParser()
    result = parser.parse(test_content)
    
    assert result.workflow is not None
    assert ("researcher", "web_search") in result.workflow.attractions
    assert ("researcher", "file_handler") in result.workflow.repulsions