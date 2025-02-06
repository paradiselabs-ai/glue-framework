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
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple, Set
from .dsl import parse_glue_file, execute_glue_app, load_env
from .providers.openrouter import OpenRouterProvider
from .tools.base import BaseTool, ToolConfig, ToolPermission
from .core.workspace import WorkspaceManager
from .core.logger import get_logger
from .core.app import GlueApp

# Constants for model display
MODELS_PER_PAGE = 15

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

class ModelInfo:
    """Model information with validation and categorization."""
    
    CATEGORIES = {
        "chat": ["chat", "conversation", "dialogue"],
        "code": ["code", "coding", "programming", "developer", "python", "javascript", "technical", "json"],
        "research": ["research", "analysis", "analytical", "academic", "reasoning", "document", "long context"],
        "creative": ["creative", "story", "writing", "artistic", "roleplay", "content generation"],
        "vision": ["vision", "image", "visual", "multimodal", "picture", "photo"]
    }
    
    def __init__(self, data: Dict[str, Any]):
        """Initialize model info with validation.
        
        Args:
            data: Raw model data
            
        Raises:
            ValueError: If required fields are missing or invalid
        """
        # Validate required fields
        self.name = data.get("name")
        if not self.name:
            raise ValueError("Model name is required")
            
        self.provider = data.get("provider", "Unknown")
        self.description = data.get("description", "No description available")
        
        # Validate numeric fields
        try:
            self.context_length = int(data.get("context_length", 0))
            if self.context_length < 0:
                raise ValueError("Context length must be non-negative")
        except (TypeError, ValueError):
            raise ValueError(f"Invalid context length for model {self.name}")
            
        # Validate pricing
        pricing = data.get("pricing", {})
        if not isinstance(pricing, dict):
            raise ValueError(f"Invalid pricing data for model {self.name}")
            
        try:
            self.prompt_price = float(pricing.get("prompt", 0))
            self.completion_price = float(pricing.get("completion", 0))
            if self.prompt_price < 0 or self.completion_price < 0:
                raise ValueError("Prices must be non-negative")
        except (TypeError, ValueError):
            raise ValueError(f"Invalid pricing values for model {self.name}")
            
        # Cache categories
        self._categories = self._determine_categories()
    
    def _determine_categories(self) -> Set[str]:
        """Determine model categories based on metadata."""
        categories = {"chat"}  # All models support chat
        text = f"{self.name} {self.description}".lower()
        
        # Check each category's keywords
        for category, keywords in self.CATEGORIES.items():
            if category == "chat":
                continue
            if any(kw in text for kw in keywords):
                categories.add(category)
            
        # Special case for research based on context length
        if self.context_length >= 16000:
            categories.add("research")
            
        return categories
    
    def matches_category(self, category: Optional[str]) -> bool:
        """Check if model matches category filter."""
        return category is None or category in self._categories
    
    def get_sort_key(self, sort_by: str) -> Any:
        """Get sort key based on sort criteria."""
        if sort_by == "rank":
            return -self.prompt_price  # Negative for reverse sort
        elif sort_by == "name":
            return self.name.lower()
        elif sort_by == "provider":
            return (self.provider.lower(), self.name.lower())
        elif sort_by == "context":
            return -self.context_length  # Negative for reverse sort
        return 0
    
    def display(self) -> None:
        """Display model information."""
        click.echo(f"\nModel: {self.name}")
        click.echo(f"Provider: {self.provider}")
        click.echo(f"Categories: {', '.join(sorted(self._categories))}")
        click.echo(f"Context Length: {self.context_length:,} tokens")
        click.echo(f"Description: {self.description}")
        click.echo(
            f"Pricing: {self.prompt_price}/1K prompt tokens, "
            f"{self.completion_price}/1K completion tokens"
        )
        click.echo("-" * 100)

class ModelCatalog:
    """Catalog of available models with caching."""
    
    def __init__(self):
        self._models: List[ModelInfo] = []
        self._filtered_models: List[ModelInfo] = []
        self._category_filter: Optional[str] = None
        self._sort_by: str = "rank"
    
    async def load_models(self) -> None:
        """Load and validate models from provider."""
        try:
            raw_models = await OpenRouterProvider.get_available_models()
            self._models = []
            
            for data in raw_models:
                try:
                    model = ModelInfo(data)
                    self._models.append(model)
                except ValueError as e:
                    click.echo(f"Warning: Skipping invalid model: {str(e)}", err=True)
                    
            self._apply_filters()
            
        except Exception as e:
            raise click.ClickException(f"Failed to load models: {str(e)}")
    
    def _apply_filters(self) -> None:
        """Apply current category filter and sorting."""
        # Filter models
        self._filtered_models = [
            model for model in self._models
            if model.matches_category(self._category_filter)
        ]
        
        # Sort filtered models
        self._filtered_models.sort(
            key=lambda m: m.get_sort_key(self._sort_by)
        )
    
    def display_page(self, page: int = 0) -> Tuple[int, int]:
        """Display a page of models."""
        if not self._filtered_models:
            click.echo("\nNo models found matching the selected criteria.")
            return 0, 0
            
        start_idx = page * MODELS_PER_PAGE
        end_idx = min(start_idx + MODELS_PER_PAGE, len(self._filtered_models))
        
        click.echo("\nAvailable Models:")
        click.echo("-" * 100)
        
        for model in self._filtered_models[start_idx:end_idx]:
            model.display()
            
        # Display navigation options
        click.echo("\nOptions:")
        if end_idx < len(self._filtered_models):
            click.echo("[m] More models")
        click.echo("[s] Sort models (rank/name/provider/context)")
        click.echo("[f] Filter by category")
        click.echo("[x] Exit")
        
        return end_idx, len(self._filtered_models)
    
    def set_category_filter(self, category: Optional[str]) -> None:
        """Set category filter and reapply filters."""
        self._category_filter = category
        self._apply_filters()
    
    def set_sort_by(self, sort_by: str) -> None:
        """Set sort criteria and reapply filters."""
        self._sort_by = sort_by
        self._apply_filters()

def get_sort_choice() -> str:
    """Get user's sorting preference"""
    click.echo("\nSort by:")
    click.echo("1. Rank (by price, highest first)")
    click.echo("2. Name (alphabetical)")
    click.echo("3. Provider (then by name)")
    click.echo("4. Context Length (highest first)")
    
    choice = click.prompt("Choose sorting option (1-4)", type=int)
    sort_options = {
        1: "rank",
        2: "name",
        3: "provider",
        4: "context"
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
    logger = get_logger()
    try:
        # Create model catalog
        catalog = ModelCatalog()
        
        # Load models
        try:
            asyncio.run(catalog.load_models())
        except click.ClickException as e:
            logger.error(str(e), extra={"user_facing": True})
            return
        
        # Interactive model browsing
        current_page = 0
        while True:
            try:
                end_idx, total = catalog.display_page(current_page)
                
                if total == 0:
                    break
                    
                choice = click.prompt("\nEnter option", type=str).lower()
                
                if choice == 'x':
                    break
                elif choice == 'm' and end_idx < total:
                    current_page += 1
                elif choice == 's':
                    catalog.set_sort_by(get_sort_choice())
                    current_page = 0
                elif choice == 'f':
                    catalog.set_category_filter(get_category_filter())
                    current_page = 0
                    
            except click.Abort:
                break
            except Exception as e:
                logger.error(f"Error: {str(e)}", extra={"user_facing": True})
                logger.debug(f"Full error: {traceback.format_exc()}")
                break
                
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.debug(f"Full traceback:\n{traceback.format_exc()}")
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

def validate_env_vars(env_vars: Dict[str, str], app_name: str) -> None:
    """Validate required environment variables.
    
    Args:
        env_vars: Dictionary of environment variables
        app_name: Name of the application for error messages
        
    Raises:
        click.ClickException: If required variables are missing
    """
    required_vars = {
        "OPENROUTER_API_KEY": "OpenRouter API key is required",
        "SERP_API_KEY": "SERP API key is required for web search"
    }
    
    missing_vars = []
    for var, message in required_vars.items():
        if var not in env_vars:
            missing_vars.append(f"{var}: {message}")
            
    if missing_vars:
        raise click.ClickException(
            f"Missing required environment variables for {app_name}:\n" +
            "\n".join(f"- {msg}" for msg in missing_vars)
        )

async def handle_prompt(app: GlueApp, prompt: str) -> None:
    """Handle user prompt with proper error handling.
    
    Args:
        app: GLUE application instance
        prompt: User input prompt
    """
    logger = get_logger()
    try:
        result = await app.process_prompt(prompt)
        logger.info(result, extra={"user_facing": True})
    except KeyboardInterrupt:
        raise
    except Exception as e:
        logger.error(f"Error processing prompt: {str(e)}", extra={"user_facing": True})
        logger.debug(f"Full error: {traceback.format_exc()}")

@cli.command()
@click.argument('file', type=click.Path(exists=True))
@click.option('--env', type=click.Path(exists=True), help='Path to .env file')
def run(file, env):
    """Run a GLUE application file.

    FILE is the path to your .glue application file.
    """
    logger = get_logger()
    try:
        # Validate file extension
        if not file.endswith('.glue'):
            raise click.ClickException("Application file must have .glue extension")
            
        # Load and validate environment
        env_vars = load_env(env_file=env)
        
        # Log loaded environment variables (masked)
        masked_vars = {k: f"{v[:4]}...{v[-4:]}" if len(v) > 8 else "***" 
                      for k, v in env_vars.items()}
        logger.debug(f"Loaded environment variables: {masked_vars}")
        
        try:
            # Parse GLUE file
            app = parse_glue_file(file)
            validate_env_vars(env_vars, app.name)
            
        except Exception as e:
            raise click.ClickException(f"Failed to parse application file: {str(e)}")
        
        try:
            # Execute application
            app = asyncio.run(execute_glue_app(app))
            
            # Enter interactive mode
            while True:
                try:
                    prompt = click.prompt("\nPrompt", prompt_suffix="")
                    if prompt.lower() == 'exit':
                        break
                        
                    asyncio.run(handle_prompt(app, prompt))
                    
                except KeyboardInterrupt:
                    logger.info("\nExiting...", extra={"user_facing": True})
                    break
                    
            # Cleanup
            asyncio.run(app.cleanup())
            
        except Exception as e:
            raise click.ClickException(f"Application execution failed: {str(e)}")
            
    except click.ClickException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.debug(f"Full traceback:\n{traceback.format_exc()}")
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
    """Show status of GLUE application components"""
    workspace_manager = WorkspaceManager()
    workspaces = workspace_manager.list_workspaces()
    
    if not workspaces:
        click.echo("No active GLUE applications found")
        return
        
    for workspace in workspaces:
        click.echo(f"\nApplication: {workspace.name}")
        click.echo("-" * 80)
        
        # Show teams
        for team in workspace.teams.values():
            click.echo(f"\nTeam: {team.name}")
            
            # Show members and their tools
            click.echo("Members:")
            for member_name in team.members:
                member = workspace.models[member_name]
                click.echo(f"  - {member_name}:")
                for tool_name, binding in member._tool_bindings.items():
                    click.echo(f"    • {tool_name} ({binding.type.name})")
            
            # Show magnetic relationships
            if team.get_team_flows():
                click.echo("Magnetic Flows:")
                for target, flow_type in team.get_team_flows().items():
                    if flow_type == "><":
                        click.echo(f"  ↔ {target} (bidirectional)")
                    elif flow_type == "->":
                        click.echo(f"  → {target} (push)")
                    elif flow_type == "<-":
                        click.echo(f"  ← {target} (pull)")
                    elif flow_type == "<>":
                        click.echo(f"  ⊥ {target} (repelled)")
            
            click.echo("-" * 80)

@cli.command()
@click.argument('name')
@click.option('--description', '-d', help='Tool description')
@click.option('--api-url', help='API endpoint URL')
@click.option('--api-key-env', help='Environment variable name for API key')
@click.option('--method', type=click.Choice(['GET', 'POST', 'PUT', 'DELETE']), default='GET')
@click.option('--mcp', is_flag=True, help='Create as MCP tool')
def create_tool(name, description, api_url, api_key_env, method, mcp):
    """Create a new tool dynamically.
    
    If --mcp is specified, creates an MCP tool. Otherwise creates a regular GLUE tool.
    The tool will be immediately available for use in GLUE applications.
    """
    try:
        # Format names
        dir_name, module_name, class_name = format_component_name(name)
        
        if mcp:
            # Create MCP tool
            mcp_dir = Path.home() / "Documents/Cline/MCP"
            server_dir = mcp_dir / f"{module_name}-server"
            server_dir.mkdir(parents=True, exist_ok=True)
            
            # Create server implementation
            server_file = server_dir / "index.ts"
            server_content = f'''import {{ Server }} from '@modelcontextprotocol/sdk/server';
import {{ StdioServerTransport }} from '@modelcontextprotocol/sdk/server/stdio';

const server = new Server({{
    name: "{name}",
    version: "0.1.0"
}});

// Tool implementation
server.addTool("{name}", {{
    description: "{description or f'Tool for {name}'}",
    inputSchema: {{
        type: "object",
        properties: {{
            input: {{ type: "string" }}
        }},
        required: ["input"]
    }},
    handler: async (args) => {{
        try {{
            const response = await fetch("{api_url or ''}", {{
                method: "{method}",
                headers: {{
                    "Authorization": `Bearer ${{process.env.{api_key_env or 'API_KEY'}}}`
                }},
                body: method !== "GET" ? JSON.stringify(args) : undefined
            }});
            return await response.json();
        }} catch (error) {{
            console.error(error);
            throw error;
        }}
    }}
}});

// Start server
const transport = new StdioServerTransport();
server.connect(transport).catch(console.error);'''
            
            server_file.write_text(server_content)
            
            click.echo(f"Created new MCP tool: {name}")
            click.echo(f"Server location: {server_file}")
            click.echo("\nTo use this tool:")
            click.echo("1. Add to MCP settings in:")
            click.echo("   ~/Library/Application Support/Claude/claude_desktop_config.json")
            click.echo("2. Add the following configuration:")
            click.echo(f'''   "{module_name}": {{
        "command": "node",
        "args": ["{server_file}"],
        "env": {{
            "{api_key_env or 'API_KEY'}": "your-api-key-here"
        }}
    }}''')
            
        else:
            # Create regular GLUE tool
            tool_dir = Path.cwd() / 'tools' / dir_name
            tool_dir.mkdir(parents=True, exist_ok=True)
            
            # Create tool implementation
            tool_file = tool_dir / '__init__.py'
            tool_content = f'''"""GLUE Tool Implementation for {name}"""

import os
import aiohttp
from typing import Any, Dict, Optional
from glue.tools.base import BaseTool, ToolConfig, ToolPermission

class {class_name}Tool(BaseTool):
    """Implementation of {name} tool"""
    
    def __init__(
        self,
        name: str = "{name}",
        description: str = "{description or f'{name} tool'}",
        **config
    ):
        super().__init__(
            name=name,
            description=description,
            config=ToolConfig(
                required_permissions=[ToolPermission.NETWORK],
                timeout=30.0
            )
        )
        self.config = config
        self.api_key = os.getenv("{api_key_env or 'API_KEY'}")
        if not self.api_key:
            raise ValueError(f"No API key found in {api_key_env or 'API_KEY'}")
    
    async def _execute(self, input_data: Any) -> Any:
        """Execute the tool
        
        Args:
            input_data: Data to send to API
            
        Returns:
            API response
        """
        async with aiohttp.ClientSession() as session:
            headers = {{"Authorization": f"Bearer {{self.api_key}}"}}
            
            if "{method}" == "GET":
                async with session.get(
                    "{api_url or ''}",
                    headers=headers,
                    params={{"input": input_data}}
                ) as response:
                    return await response.json()
            else:
                async with session.{method.lower()}(
                    "{api_url or ''}",
                    headers=headers,
                    json={{"input": input_data}}
                ) as response:
                    return await response.json()
'''
            
            tool_file.write_text(tool_content)
            
            click.echo(f"Created new tool: {name}")
            click.echo(f"Tool location: {tool_file}")
            click.echo("\nTo use this tool, add to your .glue file:")
            click.echo(f'''tool {name} {{
    config {{
        api_key = "env:{api_key_env or 'API_KEY'}"  // Will load from environment
    }}
}}''')
    
    except Exception as e:
        click.echo(f"Error creating tool: {str(e)}", err=True)
        sys.exit(1)

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
