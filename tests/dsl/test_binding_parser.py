"""Tests for GLUE binding parser"""

from glue.core.binding import AdhesiveType
from glue.dsl.parser import GlueParser

def test_parse_model_tool_bindings():
    """Test parsing model tool bindings"""
    content = """
    model researcher {
        provider = openrouter
        config {
            model = "anthropic/claude-3"
            temperature = 0.7
        }
        tools {
            web_search = glue
            code_interpreter = velcro
        }
    }
    """
    
    parser = GlueParser()
    parser.parse(content)
    
    # Verify model config
    model = parser.models["researcher"]
    assert model.provider == "openrouter"
    assert model.tools["web_search"] == AdhesiveType.GLUE
    assert model.tools["code_interpreter"] == AdhesiveType.VELCRO

def test_parse_workflow_bindings():
    """Test parsing workflow bindings with binding strengths"""
    content = """
    glue app {
        name = "Test App"
    }

    workflow {
        researcher >< assistant | glue
        assistant >< code_gen | velcro
        fact_checker >< web_search | tape
        
        // Default to VELCRO if no binding specified
        assistant >< web_search
        
        repel {
            fact_checker <> code_gen
        }
    }
    """
    
    parser = GlueParser()
    parser.parse(content)
    
    # Verify workflow config
    workflow = parser.workflow
    attractions = workflow.attractions
    
    # Check explicit bindings
    assert ("researcher", "assistant", AdhesiveType.GLUE) in attractions
    assert ("assistant", "code_gen", AdhesiveType.VELCRO) in attractions
    assert ("fact_checker", "web_search", AdhesiveType.TAPE) in attractions
    
    # Check default binding
    assert ("assistant", "web_search", AdhesiveType.VELCRO) in attractions
    
    # Check repulsions
    assert ("fact_checker", "code_gen") in workflow.repulsions

def test_parse_research_assistant():
    """Test parsing complete research assistant example"""
    content = """
    glue app {
        name = "Research Assistant"
        config {
            development = true
            sticky = false
        }
    }

    model researcher {
        provider = openrouter
        role = "Primary researcher who coordinates research efforts"
        config {
            model = "anthropic/claude-3"
            temperature = 0.7
        }
        tools {
            web_search = glue
            code_interpreter = velcro
        }
    }

    model assistant {
        provider = openrouter
        role = "Helper who processes research and generates code"
        config {
            model = "openai/gpt-4"
            temperature = 0.5
        }
        tools {
            web_search = velcro
            code_interpreter = velcro
        }
    }

    model writer {
        provider = openrouter
        role = "Documentation writer who organizes findings"
        config {
            model = "anthropic/claude-3-sonnet"
            temperature = 0.3
        }
        tools {
            web_search = tape
        }
    }

    workflow {
        researcher >< assistant | glue
        
        assistant -> writer
        researcher -> writer
        
        writer <- assistant
        
        writer <> researcher
    }
    """
    
    parser = GlueParser()
    app = parser.parse(content)
    
    # Verify app config
    assert app.name == "Research Assistant"
    assert app.config["development"] is True
    assert app.config["sticky"] is False
    
    # Verify model configs
    researcher = app.model_configs["researcher"]
    assert researcher.tools["web_search"] == AdhesiveType.GLUE
    assert researcher.tools["code_interpreter"] == AdhesiveType.VELCRO
    
    assistant = app.model_configs["assistant"]
    assert assistant.tools["web_search"] == AdhesiveType.VELCRO
    assert assistant.tools["code_interpreter"] == AdhesiveType.VELCRO
    
    writer = app.model_configs["writer"]
    assert writer.tools["web_search"] == AdhesiveType.TAPE
    
    # Verify workflow
    workflow = app.workflow
    assert ("researcher", "assistant", AdhesiveType.GLUE) in workflow.attractions
    assert ("assistant", "writer") in workflow.pulls
    assert ("writer", "researcher") in workflow.repulsions
