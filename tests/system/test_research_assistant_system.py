"""System test for research assistant workflow"""

import pytest
import os
from datetime import datetime

from glue.magnetic.field import MagneticField
from glue.core.team_pydantic import Team, TeamRole
from glue.core.model_pydantic import Model
from glue.core.pydantic_models import (
    ModelConfig, TeamContext, ToolResult, SmolAgentsTool,
    PrefectTaskConfig
)
from glue.core.types import AdhesiveType
from glue.tools.file_handler import FileHandlerTool
from glue.tools.web_search import WebSearchTool
from glue.tools.code_interpreter import CodeInterpreterTool

@pytest.fixture
def output_dir():
    """Create and clean output directory"""
    dir_path = "test_output"
    os.makedirs(dir_path, exist_ok=True)
    # Clean any existing files
    for file in os.listdir(dir_path):
        os.remove(os.path.join(dir_path, file))
    return dir_path

@pytest.fixture
def model_config():
    return ModelConfig(
        temperature=0.7,
        max_tokens=4000
    )

@pytest.fixture
def researcher(model_config):
    """Create researcher model"""
    model = Model(
        name="researcher",
        provider="openrouter",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        config=model_config
    )
    model.set_role("Research different topics and subjects online.")
    return model

@pytest.fixture
def assistant(model_config):
    """Create assistant model"""
    model = Model(
        name="assistant",
        provider="openrouter",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        config=ModelConfig(
            temperature=0.5,
            max_tokens=4000
        )
    )
    model.set_role("Help with research and coding tasks.")
    return model

@pytest.fixture
def writer(model_config):
    """Create writer model"""
    model = Model(
        name="writer",
        provider="openrouter",
        team="docs_team",
        available_adhesives={AdhesiveType.TAPE},
        config=ModelConfig(
            temperature=0.3,
            max_tokens=4000
        )
    )
    model.set_role("Write documentation files that summarize findings.")
    return model

@pytest.fixture
def research_team(researcher, assistant):
    """Create research team with models and tools"""
    team = Team(
        name="research_team",
        context=TeamContext()
    )
    team.add_model(researcher)
    team.add_model(assistant)
    team.add_tool(WebSearchTool())
    team.add_tool(CodeInterpreterTool())
    return team

@pytest.fixture
def docs_team(writer):
    """Create docs team with model and tools"""
    team = Team(
        name="docs_team",
        context=TeamContext()
    )
    team.add_model(writer)
    team.add_tool(FileHandlerTool())
    return team

@pytest.fixture
def magnetic_field():
    return MagneticField(name="research_field")

@pytest.mark.asyncio
async def test_research_workflow(magnetic_field, research_team, docs_team, output_dir):
    """Test complete research assistant workflow"""
    # Set up teams in magnetic field
    await magnetic_field.add_team(research_team)
    await magnetic_field.add_team(docs_team)
    
    # Establish push flow from research to docs
    await magnetic_field.establish_flow(
        source_team=research_team.name,
        target_team=docs_team.name,
        flow_type="push"
    )
    
    # Allow docs to pull when needed
    await magnetic_field.establish_flow(
        source_team=research_team.name,
        target_team=docs_team.name,
        flow_type="pull"
    )
    
    # Test complex research task
    research_prompt = """
    Create a blank file called new.txt and then research innovative ways of 
    manipulating files in Python and then demonstrate the findings in the code 
    interpreter by manipulating the blank new.txt file. Keep a log of the code 
    operations performed by the research team in a separate file called fileLog.md. 
    Prove the success of the python file manipulations by altering the file in 
    someway directly through the code interpreter without using the file handler tool.
    """
    
    # Research team searches for information
    search_result = await research_team.models["researcher"].use_tool(
        "web_search",
        AdhesiveType.GLUE,
        "Python file manipulation techniques best practices"
    )
    
    # Assistant helps analyze and prepare code
    code_result = await research_team.models["assistant"].use_tool(
        "code_interpreter",
        AdhesiveType.VELCRO,
        {
            "code": """
            # Create test file
            with open('new.txt', 'w') as f:
                f.write('Initial content')
                
            # Read and modify content
            with open('new.txt', 'r+') as f:
                content = f.read()
                f.seek(0)
                f.write(content.upper())
                f.truncate()
            """
        }
    )
    
    # Share results with docs team
    await magnetic_field.transfer_information(
        source_team=research_team.name,
        target_team=docs_team.name,
        content={
            "search_results": search_result.result,
            "code_example": code_result.result
        }
    )
    
    # Docs team creates log file
    log_result = await docs_team.models["writer"].use_tool(
        "file_handler",
        AdhesiveType.TAPE,
        {
            "action": "write",
            "path": os.path.join(output_dir, "fileLog.md"),
            "content": f"""
            # File Manipulation Operations Log
            
            ## Research Results
            {search_result.result}
            
            ## Code Operations
            ```python
            {code_result.result}
            ```
            
            ## Timestamp
            {datetime.now().isoformat()}
            """
        }
    )
    
    # Verify outputs
    assert os.path.exists(os.path.join(output_dir, "fileLog.md"))
    with open(os.path.join(output_dir, "fileLog.md")) as f:
        content = f.read()
        assert "File Manipulation Operations" in content
        assert "Research Results" in content
        assert "Code Operations" in content
    
    # Verify code execution worked
    with open('new.txt') as f:
        content = f.read()
        assert content.isupper()  # Content should be uppercase

@pytest.mark.asyncio
async def test_error_recovery(magnetic_field, research_team, docs_team):
    """Test workflow error recovery"""
    await magnetic_field.add_team(research_team)
    await magnetic_field.add_team(docs_team)
    
    # Configure Prefect for retries
    config = PrefectTaskConfig(
        max_retries=3,
        retry_delay_seconds=10
    )
    
    await magnetic_field.establish_flow(
        source_team=research_team.name,
        target_team=docs_team.name,
        flow_type="push",
        prefect_config=config
    )
    
    # Test with failing search that should retry
    try:
        search_result = await research_team.models["researcher"].use_tool(
            "web_search",
            AdhesiveType.GLUE,
            "This search should fail and retry"
        )
    except Exception as e:
        # Should have retried 3 times
        assert "after 3 retries" in str(e)
    
    # Verify team state is still valid
    assert research_team.name in magnetic_field.state.teams
    assert docs_team.name in magnetic_field.state.teams
    
    # Test successful operation after failure
    search_result = await research_team.models["researcher"].use_tool(
        "web_search",
        AdhesiveType.GLUE,
        "This search should work"
    )
    
    assert search_result.tool_name == "web_search"
    assert search_result.adhesive == AdhesiveType.GLUE
