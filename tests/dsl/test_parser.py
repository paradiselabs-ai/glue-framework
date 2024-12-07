# tests/dsl/test_parser.py

import pytest
from pathlib import Path
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
    """Test parsing chain block"""
    test_content = """
    researcher {
        os.openrouter
        os.api_key
        double_side_tape = { web_search >> write_file }
    }
    """
    print(f"\nParsing chain content:\n{test_content}")
    
    parser = GlueParser()
    parser.parse(test_content)
    
    model = parser.models["researcher"]
    print(f"\nParsed model:\n{model}")
    
    # Check chain parsing
    assert model.chain is not None
    assert model.chain["tools"] == ["web_search", "write_file"]

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
