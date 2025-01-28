"""GLUE DSL Executor"""

import os
import asyncio
from typing import Any, Dict, Set, List, Tuple, Optional, Type
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict

# Core imports
from .parser import GlueAppConfig, ModelConfig, ToolConfig
from ..core.types import AdhesiveType
from ..core.app import GlueApp
from ..core.team import Team
from ..core.workspace import WorkspaceManager
from ..core.conversation import ConversationManager
from ..core.tool_binding import ToolBinding
from ..core.group_chat import GroupChatManager
from ..core.logger import init_logger, get_logger
from ..magnetic.field import MagneticField

# Tool system imports
from ..tools.base import BaseTool, ToolConfig as BaseToolConfig
from ..tools.code_interpreter import CodeInterpreterTool, CodeInterpreterConfig
from ..tools.web_search import WebSearchTool
from ..tools.file_handler import FileHandlerTool

# Provider imports
from ..providers.base import BaseProvider
from ..providers.openrouter import OpenRouterProvider

class GlueExecutor:
    """
    Executor for GLUE Applications.
    
    Core Features:
    - Team Management
      * Creates and configures teams from workflow definitions
      * Sets up team relationships (attractions, repulsions, pulls)
      * Manages tool sharing and persistence through adhesive types
    
    - Tool Configuration
      * Handles specialized tool setups (code_interpreter, web_search, etc.)
      * Manages tool bindings and workspaces
      * Provides proper API key and environment handling
    
    - Model Integration
      * Configures models with appropriate system prompts
      * Sets up tool access with clear usage examples
      * Manages model-tool bindings through adhesive system
    
    - Workflow Execution
      * Processes user input through appropriate teams
      * Follows magnetic field rules for team communication
      * Maintains state persistence based on configuration
    
    This executor serves as the core runtime for GLUE applications,
    orchestrating the interaction between teams, tools, and models
    while respecting magnetic field rules and adhesive bindings.
    """
    
    def __init__(self, app: GlueApp):
        self.app = app
        self.tools = {}
        self.models = {}
        self.teams = {}  # Initialize teams dict
        # Initialize logger
        self._setup_logger()
        self.logger = get_logger()
        
        # Initialize workspace manager
        self.workspace_manager = WorkspaceManager()
        
        # Initialize managers
        sticky = app.config.get("sticky", False)
        
        # Determine app complexity based on team count
        is_complex = False
        if app.workflow:
            team_count = len(app.workflow.teams)
            if team_count > 1:
                self.logger.info(f"Complex app detected with {team_count} teams")
                is_complex = True
            else:
                self.logger.info("Simple app detected with single team")
        else:
            self.logger.info("Simple app detected with no workflow")
            
        # Initialize managers
        self.conversation = ConversationManager(sticky=sticky)
        self.group_chat = GroupChatManager(app.name)
        self.logger.debug("Initializing conversation and group chat managers")
        self._setup_environment()
    
    def _setup_logger(self):
        """Setup logging system"""
        # Get development mode from config
        development = self.app.config.get("development", False)
        
        # Create logs directory in workspace
        log_dir = os.path.join("workspace", "logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # Initialize logger
        init_logger(
            name=self.app.name,
            log_dir=log_dir,
            development=development
        )
    
    def _mask_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mask sensitive data like API keys in settings"""
        masked = deepcopy(data)
        sensitive_keys = ['api_key', 'secret', 'password', 'token']
        
        def mask_value(value: str) -> str:
            if not value:
                return value
            return value[:4] + '*' * (len(value) - 8) + value[-4:] if len(value) > 8 else '*' * len(value)
        
        def recursive_mask(d: Dict[str, Any]) -> None:
            for k, v in d.items():
                if isinstance(v, dict):
                    recursive_mask(v)
                elif isinstance(v, str) and any(key in k.lower() for key in sensitive_keys):
                    d[k] = mask_value(v)
        
        recursive_mask(masked)
        return masked
    
    def _setup_environment(self):
        """Setup environment from .env file"""
        # Load environment variables if not already set
        if not os.getenv("OPENROUTER_API_KEY"):
            from dotenv import load_dotenv
            load_dotenv()
    
    def _create_tool_config(self, tool_name: str, tool_config: ToolConfig) -> Dict[str, Any]:
        """Create tool configuration dictionary"""
        # Start with base configuration
        config = {
            "name": tool_name,
            **tool_config.config
        }
        
        # Add API key if specified
        if tool_config.api_key:
            if tool_config.api_key.startswith("env:"):
                env_var = tool_config.api_key.replace("env:", "")
                api_key = os.getenv(env_var)
                if not api_key:
                    raise ValueError(
                        f"No API key found in environment variable {env_var} "
                        f"for tool {tool_name}"
                    )
                config["api_key"] = api_key
            else:
                config["api_key"] = tool_config.api_key
        
        # Add provider if specified
        if tool_config.provider:
            config["provider"] = tool_config.provider
            
        return config
    
    async def _setup_tools(self, workspace_path: str):
        """
        Set up and configure tools with appropriate bindings and workspaces.
        
        This method:
        1. Creates tool instances with proper configurations
        2. Handles specialized tool setups (code_interpreter, web_search)
        3. Manages API keys and environment variables
        4. Sets up workspace directories for each tool
        
        Args:
            workspace_path: Base workspace directory for tools
            
        Tool Configuration:
        - CodeInterpreterTool: Gets dedicated workspace and language support
        - WebSearchTool: Configured with provider-specific API keys
        - FileHandlerTool: Gets workspace-specific configuration
        - Other tools: Configured with base settings
        """
        self.logger.info("\nSetting up tools...")
        self.logger.info(f"Available tools: {list(self.app.tool_configs.keys())}")
        
        # Print masked tool configs
        masked_configs = {
            name: self._mask_sensitive_data(asdict(config))
            for name, config in self.app.tool_configs.items()
        }
        self.logger.debug(f"Tool configs: {masked_configs}")
        
        # Create base tools
        for tool_name, tool_config in self.app.tool_configs.items():
            self.logger.info(f"\nSetting up tool: {tool_name}")
            
            try:
                # Get tool type and create configuration
                tool_type = _infer_tool_type(tool_name)
                if not tool_type:
                    raise ValueError(f"Unknown tool type: {tool_name}")
                
                # Create base configuration
                base_config = self._create_tool_config(tool_name, tool_config)
                base_config["workspace_dir"] = workspace_path
                
                # Handle special tool configurations
                if tool_type == CodeInterpreterTool:
                    # Create CodeInterpreterConfig
                    # Remove workspace_dir from base_config since we pass it explicitly
                    base_config_copy = base_config.copy()
                    base_config_copy.pop("workspace_dir", None)
                    tool_config = CodeInterpreterConfig(
                        workspace_dir=workspace_path,
                        supported_languages=base_config.get("languages"),
                        **{k: v for k, v in base_config_copy.items() 
                           if k in CodeInterpreterConfig.__annotations__}
                    )
                    base_tool = tool_type(config=tool_config)
                elif tool_name == 'web_search':
                    provider = tool_config.provider.upper()
                    api_key = os.getenv(f'{provider}_API_KEY')
                    if not api_key:
                        raise ValueError(f"No {provider}_API_KEY found in environment")
                    base_tool = tool_type(api_key=api_key, **base_config)
                else:
                    base_tool = tool_type(**base_config)
                
                self.tools[tool_name] = base_tool
                self.logger.info(f"Base tool {tool_name} setup complete")
                
            except Exception as e:
                self.logger.error(f"Error setting up tool {tool_name}: {str(e)}")
                raise
    
    async def _setup_models(self):
        """
        Set up and configure models with tools and system prompts.
        
        This method:
        1. Configures models with provider-specific settings
        2. Handles API key management and environment variables
        3. Builds comprehensive system prompts that include:
           - Base role definition
           - Available tools with persistence levels
           - Tool usage examples with proper syntax
           - Input/output patterns
        4. Sets up tool bindings with appropriate adhesive types
        
        Model Configuration:
        - OpenRouter models get provider-specific setup
        - Each model receives tool access based on config
        - Tool bindings respect adhesive types (GLUE/VELCRO/TAPE)
        - System prompts include natural tool usage examples
        
        Tool Integration:
        - Tools are bound with persistence information
        - GLUE: "(permanent access)"
        - VELCRO: "(flexible access)"
        - TAPE: "(temporary access)"
        
        The system prompt includes practical examples for:
        - Web search operations
        - File handling tasks
        - Code execution patterns
        """
        self.logger.info("\nSetting up models...")
        self.logger.info(f"Available models: {list(self.app.model_configs.keys())}")
        
        for model_name, config in self.app.model_configs.items():
            self.logger.info(f"\nSetting up model: {model_name}")
            
            # Print masked model config
            masked_config = self._mask_sensitive_data(config.__dict__)
            self.logger.debug(f"Model config: {masked_config}")
            
            if config.provider == "openrouter":
                # Get API key from environment if specified
                api_key = None
                if config.api_key and config.api_key.startswith("env:"):
                    env_var = config.api_key.replace("env:", "")
                    api_key = os.getenv(env_var)
                    if not api_key:
                        raise ValueError(
                            f"No API key found in environment variable {env_var} "
                            f"for model {model_name}"
                        )
                else:
                    # Try default OpenRouter API key
                    api_key = os.getenv("OPENROUTER_API_KEY")
                    if not api_key:
                        raise ValueError(
                            "No OpenRouter API key found. Please set OPENROUTER_API_KEY "
                            "in your environment or specify os.api_key in your GLUE file."
                        )
                
                # Build system prompt with tool info
                system_prompt = config.role + "\n\n"
                if config.tools:
                    system_prompt += "You have access to the following tools:\n"
                    for tool_name, adhesive in config.tools.items():
                        if tool_name in self.tools:
                            tool = self.tools[tool_name]
                            persistence = {
                                AdhesiveType.GLUE: "(permanent access)",
                                AdhesiveType.VELCRO: "(flexible access)", 
                                AdhesiveType.TAPE: "(temporary access)"
                            }
                            system_prompt += f"- {tool_name}: {tool.description} {persistence[adhesive]}\n"
                            
                    system_prompt += """
To use a tool:
<think>Explain why you need this tool</think>
<tool>tool_name</tool>
<input>what you want the tool to do</input>

Examples:

1. Web Search:
<think>I need to search for recent news about AI</think>
<tool>web_search</tool>
<input>latest developments in open source AI models</input>

2. File Handling:
<think>I need to save this information</think>
<tool>file_handler</tool>
<input>Title: AI News Summary
Latest developments in open source AI:
1. ...
2. ...</input>

3. Code Execution:
<think>I need to analyze some data with Python</think>
<tool>code_interpreter</tool>
<input>
import pandas as pd

# Create sample data
data = {'Model': ['GPT-4', 'Claude', 'Llama'],
        'Score': [95, 92, 88]}
df = pd.DataFrame(data)

# Calculate average
print(f"Average score: {df['Score'].mean()}")
</input>"""
                
                # Extract model configuration
                model_settings = {
                    "api_key": api_key,
                    "system_prompt": system_prompt,
                    "name": model_name,
                    "temperature": config.config.get("temperature", 0.7),
                    "model": config.config.get("model", "gpt-4")
                }
                
                # Print masked settings
                masked_settings = self._mask_sensitive_data(model_settings)
                self.logger.debug(f"Creating model with settings: {masked_settings}")
                
                # Create model with settings
                model = OpenRouterProvider(**model_settings)
                
                # Set role and tools
                model.role = config.role
                model._tools = {}
                model._tool_bindings = {}
                
                # Add tools with bindings
                for tool_name, adhesive in config.tools.items():
                    if tool_name in self.tools:
                        model._tools[tool_name] = self.tools[tool_name]
                        model._tool_bindings[tool_name] = adhesive
                
                self.models[model_name] = model
                self.logger.info(f"Model {model_name} setup complete")
    
    async def _setup_workflow(self):
        """
        Set up teams, their relationships, and tool bindings in the workflow.
        
        This method:
        1. Team Creation and Configuration
           - Creates teams with specified members
           - Assigns team leads and roles
           - Sets up team-specific workspaces
        
        2. Tool Distribution
           - Creates tool instances per team member
           - Configures tool bindings based on adhesive types
           - Manages workspace isolation between teams
        
        3. Team Relationships
           - Attractions: Enables bidirectional flow (><)
           - Repulsions: Prevents team interaction (<>)
           - Pulls: Sets up GLUE-based result sharing (<-)
        
        4. Resource Management
           - Tool instances are created per team member
           - Workspaces are isolated between teams
           - Resource sharing follows adhesive rules:
             * GLUE: Team-level persistence
             * VELCRO: Session-level sharing
             * TAPE: Temporary usage
        
        5. Adhesive Handling
           - Respects model's allowed adhesives
           - Prioritizes stronger bindings (GLUE > VELCRO > TAPE)
           - Configures appropriate resource sharing
        
        The workflow setup ensures proper isolation and communication
        between teams while respecting magnetic field rules and
        adhesive-based resource sharing patterns.
        """
        if not self.app.workflow:
            return
        
        self.logger.info("\nSetting up workflow...")
        
        # Create teams
        self.teams = {}
        for team_name, team_config in self.app.workflow.teams.items():
            self.logger.info(f"\nSetting up team: {team_name}")
            
            # Create team
            team = Team(
                name=team_name,
                members=set(),
                tools=set(),
                shared_results={},
                session_results={}
            )
            self.teams[team_name] = team
            
            # Add lead if specified
            if team_config.lead and team_config.lead in self.models:
                self.logger.info(f"Adding lead: {team_config.lead}")
                lead = self.models[team_config.lead]
                lead.team = team_name
                await team.add_member(team_config.lead)
            
            # Add members
            for member_name in team_config.members:
                if member_name in self.models:
                    self.logger.info(f"Adding member: {member_name}")
                    member = self.models[member_name]
                    member.team = team_name
                    await team.add_member(member_name)
            
            # Add tools - each model gets its own instance
            for tool_name in team_config.tools:
                if tool_name in self.tools:
                    self.logger.info(f"Adding tool: {tool_name}")
                    await team.add_tool(tool_name)
                    
                    # Create tool instance for each team member with proper adhesive binding
                    base_tool = self.tools[tool_name]
                    tool_config = self.app.tool_configs[tool_name]
                    base_config = self._create_tool_config(tool_name, tool_config)
                    
                    for member_name in team.members:
                        member = self.models[member_name]
                        # Get model's allowed adhesives
                        model_config = self.app.model_configs[member_name]
                        allowed_adhesives = model_config.config.get('adhesives', [])
                        
                        # Create tool instance with appropriate binding
                        workspace_dir = self.workspace_manager.get_workspace(
                            f"{self.app.name}-{member_name}",
                            sticky=self.app.config.get("sticky", False)
                        )
                        
                        # Create tool instance based on type
                        if tool_name == 'web_search':
                            provider = tool_config.provider.upper()
                            api_key = os.getenv(f'{provider}_API_KEY')
                            if not api_key:
                                raise ValueError(f"No {provider}_API_KEY found in environment")
                            tool = WebSearchTool(api_key=api_key, **base_config)
                        elif tool_name == 'code_interpreter':
                            instance_config = CodeInterpreterConfig(
                                workspace_dir=workspace_dir,
                                supported_languages=base_config.get("languages"),
                                **{k: v for k, v in base_config.items() 
                                   if k in CodeInterpreterConfig.__annotations__}
                            )
                            tool = CodeInterpreterTool(config=instance_config)
                        elif tool_name == 'file_handler':
                            tool = FileHandlerTool(
                                workspace_dir=workspace_dir,
                                **base_config
                            )
                        else:
                            tool = type(base_tool)(**base_config)
                        
                        # Set tool binding based on model's allowed adhesives
                        # Priority: GLUE > VELCRO > TAPE
                        binding_type = None
                        if AdhesiveType.GLUE in allowed_adhesives:
                            binding_type = AdhesiveType.GLUE
                        elif AdhesiveType.VELCRO in allowed_adhesives:
                            binding_type = AdhesiveType.VELCRO
                        elif AdhesiveType.TAPE in allowed_adhesives:
                            binding_type = AdhesiveType.TAPE
                        else:
                            # Default to VELCRO if no adhesives specified
                            binding_type = AdhesiveType.VELCRO
                        
                        # Create binding with appropriate type
                        tool.binding = ToolBinding(
                            type=binding_type,
                            shared_resources=["file_content", "file_path", "file_format"]
                            if binding_type != AdhesiveType.TAPE else None
                        )
                        
                        member._tools[tool_name] = tool
        
        # Setup flows between teams
        for source, target in self.app.workflow.attractions:
            self.logger.info(f"Setting up flow: {source} -> {target}")
            
            if source in self.teams and target in self.teams:
                source_team = self.teams[source]
                target_team = self.teams[target]
                # Enable bidirectional flow between teams
                source_team.set_relationship(target, None)  # None = adhesive-agnostic
                target_team.set_relationship(source, None)  # Let teams handle adhesives internally
            else:
                self.logger.warning(f"Could not find teams for flow: {source} -> {target}")
        
        # Setup repulsions between teams
        for source, target in self.app.workflow.repulsions:
            self.logger.info(f"Setting up repulsion: {source} <> {target}")
            
            if source in self.teams and target in self.teams:
                source_team = self.teams[source]
                target_team = self.teams[target]
                # Block all interaction between teams
                source_team.repel(target, bidirectional=True)
            else:
                self.logger.warning(f"Could not find teams for repulsion: {source} <> {target}")
                
        # Setup pull teams
        for target, source in self.app.workflow.pulls:
            self.logger.info(f"Setting up pull: {target} <- {source}")
            
            if target in self.teams:
                target_team = self.teams[target]
                
                # Handle special "pull" keyword
                if source.lower() == "pull":
                    # Can pull from any non-repelled team
                    for other_name, other_team in self.teams.items():
                        if other_name != target and other_name not in target_team._repelled_by:
                            # Enable pulling from non-repelled team with GLUE adhesive
                            # This ensures pulled results are permanently stored
                            target_team.set_relationship(other_name, AdhesiveType.GLUE)
                            # Also set up the source team to use GLUE for shared results
                            other_team.set_relationship(target, AdhesiveType.GLUE)
                elif source in self.teams:
                    # Regular pull from specific team
                    # Enable specific pull relationship with GLUE adhesive
                    target_team.set_relationship(source, AdhesiveType.GLUE)
                    # Also set up the source team to use GLUE for shared results
                    self.teams[source].set_relationship(target, AdhesiveType.GLUE)

    
    async def execute(self) -> Any:
        """Execute GLUE application"""
        try:
            # Get workspace path
            workspace_path = self.workspace_manager.get_workspace(
                self.app.name,
                sticky=self.app.config.get("sticky", False)
            )
            
            # Setup components
            await self._setup_tools(workspace_path)  # Tools first for SmolAgents integration
            await self._setup_models()  # Models can use tools during setup
            
            # Setup workflow if defined
            if self.app.workflow:
                await self._setup_workflow()
            
            # Initialize team chats
            team_chats = {}
            for team_name, team in self.teams.items():
                # Start chat between team members
                if len(team.members) > 1:
                    members = list(team.members)
                    lead = members[0]  # First member is lead
                    for member in members[1:]:
                        chat_id = await self.group_chat.start_chat(
                            lead,
                            member,
                            team_name=team_name,
                            target_teams=team.get_team_flows()
                        )
                        team_chats[f"{team_name}_{lead}_{member}"] = chat_id

            # Interactive prompt loop
            while True:
                print("\nprompt:", flush=True)
                # Read input with proper buffering
                loop = asyncio.get_event_loop()
                user_input = await loop.run_in_executor(
                    None,
                    lambda: input().strip()  # Strip whitespace
                )
                
                if user_input.lower() in ['exit', 'quit']:
                    break
                
                # Process input through research team first
                print("\nthinking...", flush=True)
                
                # Get research team and its lead
                research_team = self.teams.get("researchers")
                if not research_team:
                    research_team = next(iter(self.teams.values()))
                
                lead_name = next(iter(research_team.members))
                lead_model = self.models[lead_name]
                
                # Process through all teams based on their flows
                responses = {}
                processed_teams = set()
                
                # Start with first team
                current_team = next(iter(self.teams.values()))
                while current_team and current_team.name not in processed_teams:
                    # Process within team
                    team_chat_id = next(
                        (chat_id for chat_id in team_chats 
                         if chat_id.startswith(f"{current_team.name}_")),
                        None
                    )
                    
                    if team_chat_id:
                        lead_name = next(iter(current_team.members))
                        content = responses.get(current_team.name, user_input)
                        response = await self.group_chat.process_message(
                            team_chats[team_chat_id],
                            content,
                            from_model=lead_name
                        )
                        responses[current_team.name] = response
                        print(f"\n{current_team.name} Team Response: {response}", flush=True)
                    
                    # Mark as processed
                    processed_teams.add(current_team.name)
                    
                    # Find next team based on flows
                    team_flows = current_team.get_team_flows()
                    next_team_name = next(
                        (team for team in team_flows 
                         if team not in processed_teams 
                         and team_flows[team] in ["><", "->"]  # Only follow push/attract flows
                         and team in self.teams),
                        None
                    )
                    current_team = self.teams.get(next_team_name)
                
        finally:
            # Save state if sticky
            if self.app.config.get("sticky", False):
                for team in self.teams.values():
                    state = team.save_state()
                    # Save team state (implementation needed)
            
            # Cleanup
            for model in self.models.values():
                if hasattr(model, 'cleanup'):
                    await model.cleanup()
            
            # Cleanup workspace if not sticky
            if not self.app.config.get("sticky", False):
                self.workspace_manager.cleanup_workspace(workspace_path)

def _infer_tool_type(name: str) -> Optional[Type[BaseTool]]:
    """Infer tool type from name"""
    TOOL_TYPES = {
        'web_search': WebSearchTool,
        'file_handler': FileHandlerTool,
        'code_interpreter': CodeInterpreterTool,
    }
    
    tool_type = TOOL_TYPES.get(name.lower())
    if not tool_type:
        raise ValueError(
            f"Unknown tool type: {name}. "
            f"Available types: {list(TOOL_TYPES.keys())}"
        )
    return tool_type

async def execute_glue_app(app: GlueApp) -> Any:
    """Execute GLUE application
    
    Args:
        app: The GLUE application to execute
        
    Returns:
        Any: Result of application execution
    """
    executor = GlueExecutor(app)
    return await executor.execute()
