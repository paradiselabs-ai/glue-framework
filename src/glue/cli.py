"""GLUE Command Line Interface
GenerativeAI Linking & Unification Engine (GLUE) CLI commands.
GLUE (https://github.com/paradiselabs-ai/glue-framework) is a lightweight, 
powerful framework for developing multi-agentic AI workflows and applications.

Built with SmolAgents (https://github.com/huggingface/smolagents) 
"""

import sys
import click
import asyncio
import re
import inspect
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from .dsl import parse_glue_file, execute_glue_app, load_env
from .providers.openrouter import OpenRouterProvider
from .tools import web_search, file_handler, code_interpreter
from .core.resource import Resource, ResourceState
from .core.state import StateManager
from .core.registry import ResourceRegistry
from .tools.base import BaseTool, ToolConfig, ToolPermission

registry = None

def get_registry():
    """Get or create global registry"""
    global registry
    if not registry:
        registry = ResourceRegistry(StateManager())
    return registry

def print_version(ctx, param, value):
    if not value or ctx.resilient_parsing:
        return
    click.echo('GLUE Framework v0.1.0')
    click.echo('Built with SmolAgents - https://github.com/huggingface/smolagents')
    ctx.exit()

def format_component_name(name: str) -> Tuple[str, str, str]:
    """Format component name into directory, module, and class names.
    
    Args:
        name: Original component name
        
    Returns:
        Tuple of (directory_name, module_name, class_name)
        
    Example:
        "my test tool" -> ("my-test-tool", "my_test_tool", "MyTestTool")
    """
    # Convert to lowercase and remove any special characters
    clean_name = re.sub(r'[^\w\s-]', '', name.lower())
    
    # Create directory name (kebab-case)
    directory_name = re.sub(r'[\s_]+', '-', clean_name)
    
    # Create module name (snake_case)
    module_name = re.sub(r'[\s-]+', '_', clean_name)
    
    # Create class name (PascalCase)
    class_name = ''.join(word.capitalize() for word in clean_name.split())
    
    return directory_name, module_name, class_name

def create_project_structure(project_dir: Path) -> None:
    """Create GLUE project directory structure with necessary __init__.py files"""
    # Create main project directories
    (project_dir / 'agents').mkdir(parents=True)
    (project_dir / 'tools').mkdir(parents=True)
    (project_dir / 'tests/agents').mkdir(parents=True)
    (project_dir / 'tests/tools').mkdir(parents=True)
    (project_dir / 'workspace/logs').mkdir(parents=True)
    
    # Create __init__.py files
    (project_dir / 'agents' / '__init__.py').write_text('')
    (project_dir / 'tools' / '__init__.py').write_text('')
    (project_dir / 'tests' / '__init__.py').write_text('')
    (project_dir / 'tests/agents' / '__init__.py').write_text('')
    (project_dir / 'tests/tools' / '__init__.py').write_text('')

@click.group()
@click.option('--version', is_flag=True, callback=print_version,
              expose_value=False, is_eager=True, help='Show version information.')
@click.option('--debug', is_flag=True, help='Enable debug mode.')
def cli(debug):
    """GLUE Framework - GenAI Linking & Unification Engine

    Built with SmolAgents (https://github.com/huggingface/smolagents)
    Run GLUE applications and manage GLUE projects.
    """
    if debug:
        click.echo('Debug mode enabled')

def get_model_category(model: Dict[str, Any]) -> List[str]:
    """Determine model categories based on model metadata"""
    categories = []
    name = model.get("name", "").lower()
    description = model.get("description", "").lower()
    context_length = model.get("context_length", 0)
    
    # Chat models - most models support chat
    categories.append("chat")
    
    # Code models - based on name and description
    if (
        "code" in name or
        any(kw in description for kw in [
            "code", "coding", "programming", "developer", 
            "python", "javascript", "technical", "json"
        ])
    ):
        categories.append("code")
    
    # Research models - based on context length and capabilities
    if (
        context_length >= 16000 or  # Long context usually indicates research capability
        "research" in name or
        any(kw in description for kw in [
            "research", "analysis", "analytical", "academic",
            "reasoning", "document", "long context"
        ])
    ):
        categories.append("research")
    
    # Creative models - based on name and description
    if (
        "creative" in name or
        any(kw in description for kw in [
            "creative", "story", "writing", "artistic",
            "roleplay", "content generation"
        ])
    ):
        categories.append("creative")
    
    # Vision models - based on capabilities
    if (
        "vision" in name or
        any(kw in description for kw in [
            "vision", "image", "visual", "multimodal",
            "picture", "photo"
        ])
    ):
        categories.append("vision")
    
    return categories

def display_models(models: List[Dict[str, Any]], start_idx: int = 0, category_filter: Optional[str] = None,
                  sort_by: str = "rank") -> None:
    """Display models with pagination and filtering"""
    filtered_models = models
    
    # Apply category filter if specified
    if category_filter:
        filtered_models = [m for m in models if category_filter in get_model_category(m)]
    
    # Sort models
    if sort_by == "rank":
        filtered_models.sort(key=lambda x: float(x.get("pricing", {}).get("prompt", "0")), reverse=True)
    elif sort_by == "name":
        filtered_models.sort(key=lambda x: x.get("name", "").lower())
    elif sort_by == "provider":
        filtered_models.sort(key=lambda x: (x.get("provider", "").lower(), x.get("name", "").lower()))
    elif sort_by == "updated":
        filtered_models.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
    elif sort_by == "context":
        filtered_models.sort(key=lambda x: int(x.get("context_length", 0)), reverse=True)
    
    if not filtered_models:
        click.echo("\nNo models found matching the selected criteria.")
        return 0, 0
    
    # Display models (15 at a time)
    end_idx = min(start_idx + 15, len(filtered_models))
    current_page = filtered_models[start_idx:end_idx]
    
    click.echo("\nAvailable Models:")
    click.echo("-" * 100)
    
    for model in current_page:
        name = model.get("name", "Unknown")
        provider = model.get("provider", "Unknown")
        description = model.get("description", "No description available")
        pricing = model.get("pricing", {})
        prompt_price = pricing.get("prompt", "N/A")
        completion_price = pricing.get("completion", "N/A")
        context_length = model.get("context_length", "Unknown")
        categories = get_model_category(model)
        
        click.echo(f"\nModel: {name}")
        click.echo(f"Provider: {provider}")
        click.echo(f"Categories: {', '.join(categories)}")
        click.echo(f"Context Length: {context_length:,} tokens")
        click.echo(f"Description: {description}")
        click.echo(f"Pricing: {prompt_price}/1K prompt tokens, {completion_price}/1K completion tokens")
        click.echo("-" * 100)
    
    # Display navigation options
    click.echo("\nOptions:")
    if end_idx < len(filtered_models):
        click.echo("[m] More models")
    click.echo("[s] Sort models (rank/name/provider/updated/context)")
    click.echo("[f] Filter by category")
    click.echo("[x] Exit")
    
    return end_idx, len(filtered_models)

def get_sort_choice() -> str:
    """Get user's sorting preference"""
    click.echo("\nSort by:")
    click.echo("1. Rank/Price (highest first)")
    click.echo("2. Name (alphabetical)")
    click.echo("3. Provider")
    click.echo("4. Recently Updated")
    click.echo("5. Context Length (highest first)")
    
    choice = click.prompt("Choose sorting option (1-5)", type=int)
    sort_options = {
        1: "rank",
        2: "name",
        3: "provider",
        4: "updated",
        5: "context"
    }
    return sort_options.get(choice, "rank")

def get_category_filter() -> Optional[str]:
    """Get user's category filter preference"""
    click.echo("\nFilter by category:")
    click.echo("1. All models")
    click.echo("2. Chat models")
    click.echo("3. Code models")
    click.echo("4. Research models")
    click.echo("5. Creative models")
    click.echo("6. Vision models")
    
    choice = click.prompt("Choose category (1-6)", type=int)
    category_options = {
        1: None,
        2: "chat",
        3: "code",
        4: "research",
        5: "creative",
        6: "vision"
    }
    return category_options.get(choice)

@cli.command()
def list_models():
    """List available AI models with filtering and sorting options."""
    try:
        # Fetch models from OpenRouter
        models = asyncio.run(OpenRouterProvider.get_available_models())
        
        start_idx = 0
        category_filter = None
        sort_by = "rank"
        
        while True:
            end_idx, total = display_models(
                models,
                start_idx=start_idx,
                category_filter=category_filter,
                sort_by=sort_by
            )
            
            choice = click.prompt("\nEnter option", type=str).lower()
            
            if choice == 'x':
                break
            elif choice == 'm' and end_idx < total:
                start_idx = end_idx
            elif choice == 's':
                sort_by = get_sort_choice()
                start_idx = 0  # Reset to first page
            elif choice == 'f':
                category_filter = get_category_filter()
                start_idx = 0  # Reset to first page
            
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.argument('name')
@click.option('--type', type=click.Choice(['tool', 'agent']), required=True,
              help='Type of component to create.')
def create(name, type):
    """Create a new GLUE tool or agent.
    
    NAME is the name of the new component.
    """
    try:
        # Check if we're in a GLUE project directory
        if not (Path.cwd() / 'tools').exists() or not (Path.cwd() / 'agents').exists():
            click.echo("Error: Not in a GLUE project directory. Run 'glue new' first to create a project.")
            sys.exit(1)
            
        # Format component names
        dir_name, module_name, class_name = format_component_name(name)
        
        if type == 'tool':
            # Create tool template
            tool_dir = Path.cwd() / 'tools' / dir_name
            tool_dir.mkdir(parents=True, exist_ok=True)
            
            # Create tool implementation file
            tool_file = tool_dir / '__init__.py'
            tool_content = '''"""GLUE Tool Implementation"""

from typing import Any, Dict, Optional
from glue.tools.base import BaseTool, ToolConfig, ToolPermission

class {class_name}Tool(BaseTool):
    """Implementation of {name} tool"""
    
    def __init__(
        self,
        name: str = "{name}",
        description: str = "{name} tool",
        **config
    ):
        super().__init__(
            name=name,
            description=description,
            config=ToolConfig(
                required_permissions=[ToolPermission.READ],
                timeout=30.0
            )
        )
        self.config = config
    
    async def _execute(self, *args, **kwargs) -> Any:
        """Execute the tool
        
        Returns:
            Any: Tool execution results
        """
        # Implement tool logic here
        pass
'''.format(class_name=class_name, name=name)
            
            tool_file.write_text(tool_content)
            
            # Create test file
            test_dir = Path.cwd() / 'tests/tools'
            test_file = test_dir / f'test_{module_name}.py'
            test_content = '''"""Tests for {name} tool"""

import pytest
from tools.{dir_name} import {class_name}Tool

@pytest.fixture
def tool():
    return {class_name}Tool()

def test_tool_initialization(tool):
    assert tool.name == "{name}"

def test_tool_execution(tool):
    # Add test cases here
    pass
'''.format(name=name, dir_name=dir_name, class_name=class_name)
            
            test_file.write_text(test_content)
            
            click.echo(f"Created new tool: {name}")
            click.echo(f"Tool location: {tool_file}")
            click.echo(f"Test location: {test_file}")
            
        elif type == 'agent':
            # Create agent template
            agents_dir = Path.cwd() / 'agents'
            
            agent_file = agents_dir / f'{module_name}.py'
            agent_content = '''"""GLUE Agent Implementation"""

from typing import Any, Dict, Optional
from glue.core.role import Role

class {class_name}Agent(Resource):
    """Implementation of {name} agent"""
    
    def __init__(self, model: str = "gpt-4"):
        super().__init__(
            name="{name}",
            category="agent",
            tags={{"agent", "{name}"}}
        )
        self.model = model
        self.system_prompt = """
            You are a specialized agent for {name} tasks.
            Your primary responsibilities are:
            1. [Define primary responsibility]
            2. [Define secondary responsibility]
            3. [Define additional responsibilities]
            """
        )
    
    async def process(self, input: str) -> str:
        """Process input and generate response
        
        Args:
            input (str): User input to process
            
        Returns:
            str: Agent's response
        """
        return await self.generate(input)
'''.format(class_name=class_name, name=name)
            
            agent_file.write_text(agent_content)
            
            # Create test file
            test_dir = Path.cwd() / 'tests/agents'
            test_file = test_dir / f'test_{module_name}.py'
            test_content = '''"""Tests for {name} agent"""

import pytest
from agents.{module_name} import {class_name}Agent

@pytest.fixture
def agent():
    return {class_name}Agent()

def test_agent_initialization(agent):
    assert agent.name == "{name}"

@pytest.mark.asyncio
async def test_agent_processing(agent):
    # Add test cases here
    pass
'''.format(name=name, module_name=module_name, class_name=class_name)
            
            test_file.write_text(test_content)
            
            click.echo(f"Created new agent: {name}")
            click.echo(f"Agent location: {agent_file}")
            click.echo(f"Test location: {test_file}")
    
    except Exception as e:
        click.echo(f"Error creating {type}: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--env', type=click.Path(exists=True), help='Path to .env file')
def run(file, env):
    """Run a GLUE application file.

    FILE is the path to your .glue application file.
    """
    try:
        # Load environment
        load_env(env_file=env)
        
        # Parse GLUE file
        app = parse_glue_file(file)
        
        # Get or create registry
        registry = get_registry()
        
        # Execute application with registry
        asyncio.run(execute_glue_app(app, registry=registry))
        
    except Exception as e:
        import traceback
        click.echo(f"Error: {str(e)}", err=True)
        click.echo("\nFull traceback:", err=True)
        click.echo(traceback.format_exc(), err=True)
        sys.exit(1)

@cli.command()
@click.argument('name')
@click.option('--template', type=click.Choice(['basic', 'research', 'chat']), default='basic',
              help='Template to use for the new project.')
def new(name, template):
    """Create a new GLUE project.

    NAME is the name of your new project directory.
    """
    try:
        project_dir = Path(name)
        if project_dir.exists():
            click.echo(f"Error: Directory '{name}' already exists", err=True)
            sys.exit(1)

        # Create project directory structure
        create_project_structure(project_dir)
        

        # Create main application file
        app_file = project_dir / f"{name}.glue"
        if template == 'basic':
            app_content = '''# Basic GLUE Application
// A basic assistant that helps users with various tasks using tools

glue app {
    name = "Basic Assistant"
    config {
        development = true
    }
}

model assistant {
    provider = openrouter
    role = "You are a helpful AI assistant that uses tools to help users"
    adhesives = [glue, tape] // Define the adhesives the model can access tools with
    config {
        model = "openai/gpt-4"
        temperature = 0.7
    }
}

tool file_handler {
    // Tool persistence is determined by binding type in model config
}

tool code_interpreter {
    config {
        safe_mode = true  // Optional safety settings
    }
}

// Workflow defines model interactions and memory
magnetize {
    research {
        lead = assistant
        members = []  // Optional team members
        tools = [file_handler, code_interpreter]  // Tools available to the team
    }
}

apply glue
'''
        elif template == 'research':
            app_content = '''# Research Assistant GLUE Application
// A research assistant that helps with online research and analysis
// Uses multiple models to research topics and synthesize findings

glue app {
    name = "Research Assistant"
    config {
        development = true
        sticky = true  // Keep workspace between runs
    }
}

model researcher {
    provider = openrouter  // API key loaded from OPENROUTER_API_KEY environment variable
    role = "You are a research expert who finds and explains information"
    adhesives = [glue]  // Can use GLUE for persistent results
    config {
        model = "openai/gpt-4"
        temperature = 0.7
    }
}

model analyst {
    provider = openrouter  // API key loaded from OPENROUTER_API_KEY environment variable
    role = "You are a data analyst who synthesizes research findings"
    adhesives = [velcro]  // Can use VELCRO for session persistence
    config {
        model = "anthropic/claude-3.5-sonnet:beta"
        temperature = 0.2
    }
}

tool web_search {
    provider = serp  // API key loaded from SERP_API_KEY environment variable
}

tool file_handler {
    // Each model gets its own instance of the tool
}

// Workflow defines model interactions and memory
magnetize {
    research {
        lead = researcher
        members = []  // Optional team members
        tools = [web_search]  // Tools available to the team
    }
    
    analysis {
        lead = analyst
        members = []  // Optional team members
        tools = [file_handler]  // Tools available to the team
    }
    
    // Define information flow between teams
    research -> analysis  // Research team pushes to analysis
    analysis <- pull     // Analysis team can pull from research when needed
}

apply glue
'''
        elif template == 'chat':
            app_content = '''# Chat Application GLUE Application
// A conversational assistant with access to various tools
// Demonstrates using multiple adhesive types for different persistence needs

glue app {
    name = "Chat Assistant"
    config {
        development = true
        sticky = true
    }
}

model chat_assistant {
    provider = openrouter  // API key loaded from OPENROUTER_API_KEY environment variable
    role = "You are a conversational AI assistant with tool access"
    adhesives = [glue, velcro, tape]  // Can use all adhesive types
    config {
        model = "openai/gpt-4"
        temperature = 0.7
    }
}

tool web_search {
    provider = serp  // API key loaded from SERP_API_KEY environment variable
}

tool file_handler {
    // Tool state persistence is managed by model bindings
}

tool code_interpreter {
    config {
        safe_mode = true  // Optional safety settings
    }
}

// Workflow defines model interactions and memory
magnetize {
    chat {
        lead = chat_assistant
        members = []  // Optional team members
        tools = [web_search, file_handler, code_interpreter]  // Tools available to the team
    }
}

apply glue
'''
        app_file.write_text(app_content)
        
        # Create example tool usage file
        examples_dir = project_dir / 'examples'
        examples_dir.mkdir(exist_ok=True)
        
        example_file = examples_dir / 'tool_usage.glue'
        example_content = '''# Tool Usage Examples
// Demonstrates using different tools and adhesive types
// Shows how to configure tools and manage their persistence

glue app {
    name = "Tool Examples"
    config {
        development = true
        sticky = false  ### if your app is not sticky, this is actually not needed, I included it to make it more apparent that this example is not a sticky app, 
                        but you only need to declare this in apps that are sticky (sticky = true) ###
    }
}

model assistant {
    provider = openrouter  // API key loaded from OPENROUTER_API_KEY environment variable
    role = "You are a tool-using assistant that demonstrates GLUE capabilities"
    adhesives = [glue, velcro, tape]  // Define which adhesive types this model can use
    config {
        model = "openai/gpt-4"
        temperature = 0.7
    }
}

# Built-in tools with configuration
tool web_search {
    provider = serp  // API key loaded from SERP_API_KEY environment variable
}

tool file_handler {
    // Tool state persistence is managed by model bindings
}

tool code_interpreter {
    config {
        languages = ["python", "javascript"]  // Optional tool settings
    }
}

magnetize {
    research {
        lead = assistant
        tools = [web_search, file_handler, code_interpreter]
    }
}

apply glue

// Example prompts:
// - "Search for recent news about AI"
// - "Save the search results to ai_news.txt"
// - "Run this Python code: print('Hello from GLUE!')"
// - "Create a magnetic binding between two models"
'''

        example_file.write_text(example_content)
        
        # Create .env file
        env_file = project_dir / '.env'
        env_file.write_text('''# GLUE Environment Configuration
OPENROUTER_API_KEY=your_api_key_here
SERP_API_KEY=your_api_key_here  # For web search tool
''')
        
        click.echo(f"Created new GLUE project: {name}")
        click.echo(f"Project structure:")
        click.echo(f"  {name}/")
        click.echo(f"  ├── agents/")
        click.echo(f"  ├── tools/")
        click.echo(f"  ├── tests/")
        click.echo(f"  │   ├── agents/")
        click.echo(f"  │   └── tools/")
        click.echo(f"  ├── examples/")
        click.echo(f"  │   └── tool_usage.glue")
        click.echo(f"  ├── workspace/")
        click.echo(f"  │   └── logs/")
        click.echo(f"  ├── {name}.glue")
        click.echo(f"  └── .env")
        click.echo("\nTo get started:")
        click.echo(f"  cd {name}")
        click.echo(f"  # View available tools:")
        click.echo(f"  glue list-tools")
        click.echo(f"  # Run the example:")
        click.echo(f"  glue run examples/tool_usage.glue")
        click.echo(f"  # Run your app:")
        click.echo(f"  glue run {name}.glue")

        
    except Exception as e:
        click.echo(f"Error creating project: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
def status():
    """Show status of GLUE resources"""
    # Get registry
    registry = get_registry()
    
    # Show active resources
    active = registry.get_resources_by_state(ResourceState.ACTIVE)
    if active:
        click.echo("\nActive Resources:")
        click.echo("-" * 80)
        for resource in active:
            click.echo(f"Name: {resource.name}")
            click.echo(f"Category: {resource.metadata.category}")
            click.echo(f"Field: {resource.field.name if resource.field else 'None'}")
            click.echo("-" * 80)
    
    # Show resources by category
    categories = registry.get_categories()
    for category in categories:
        resources = registry.get_resources_by_category(category)
        if resources:
            click.echo(f"\n{category.title()} Resources:")
            click.echo("-" * 80)
            for resource in resources:
                click.echo(f"Name: {resource.name}")
                click.echo(f"State: {resource.state.name}")
                click.echo(f"Tags: {', '.join(resource.metadata.tags)}")
                click.echo("-" * 80)

@cli.command()
def list_tools():
    """List available GLUE tools."""
    # First show built-in tools
    # Built-in tools
    builtin_tools = [
        {
            "name": "web_search",
            "module": "glue.tools.web_search",
            "description": "Perform web searches and retrieve information",
            "example": 'tool web_search {\n    provider = serp  // API key loaded from SERP_API_KEY environment variable\n}'
        },
        {
            "name": "file_handler",
            "module": "glue.tools.file_handler",
            "description": "Read and write files",
            "example": 'tool file_handler {}'
        },
        {
            "name": "code_interpreter",
            "module": "glue.tools.code_interpreter",
            "description": "Execute and analyze code",
            "example": 'tool code_interpreter {\n    config {\n        languages = ["python", "javascript"]\n    }\n}'
        }
    ]
    
    # Check for custom tools in current project
    custom_tools = []
    if Path('tools').exists():
        for tool_dir in Path('tools').iterdir():
            if tool_dir.is_dir() and (tool_dir / '__init__.py').exists():
                custom_tools.append({
                    "name": tool_dir.name,
                    "module": f"tools.{tool_dir.name}",
                    "description": "Custom tool",
                    "example": f'tool {tool_dir.name} {{}}'
                })
    
    # Display built-in tools
    click.echo("\nBuilt-in Tools:")
    click.echo("-" * 100)
    for tool in builtin_tools:
        click.echo(f"\nTool: {tool['name']}")
        click.echo(f"Import: from {tool['module']} import {tool['name'].title()}Tool")
        click.echo(f"Description: {tool['description']}")
        click.echo("\nExample usage in .glue file:")
        click.echo(tool['example'])
        click.echo("-" * 100)
    
    # Display custom tools if any
    if custom_tools:
        click.echo("\nCustom Tools (in current project):")
        click.echo("-" * 100)
        for tool in custom_tools:
            click.echo(f"\nTool: {tool['name']}")
            click.echo(f"Import: from {tool['module']} import {tool['name'].title()}Tool")
            click.echo(f"Description: {tool['description']}")
            click.echo("\nExample usage in .glue file:")
            click.echo(tool['example'])
            click.echo("-" * 100)
            

if __name__ == '__main__':
    cli()

# For backward compatibility
def main():
    """Entry point for the GLUE CLI"""
    cli()
