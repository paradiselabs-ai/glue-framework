# src/glue/dsl/executor.py

"""GLUE DSL Executor"""

import os
import asyncio
from typing import Any, Dict, Set, List, Tuple
from pathlib import Path
from copy import deepcopy
from .parser import GlueApp, ModelConfig, ToolConfig
from ..adhesive import (
    workspace, double_side_tape,
    tool as create_tool
)
from ..providers import (
    OpenRouterProvider
)
from ..magnetic.field import MagneticField
from ..core.conversation import ConversationManager
from ..core.workspace import WorkspaceManager
from ..core.logger import init_logger, get_logger

class GlueExecutor:
    """Executor for GLUE Applications"""
    
    def __init__(self, app: GlueApp):
        self.app = app
        self.tools = {}
        self.models = {}
        
        # Initialize logger
        self._setup_logger()
        self.logger = get_logger()
        
        # Initialize workspace manager
        self.workspace_manager = WorkspaceManager()
        
        # Initialize conversation manager
        self.conversation = ConversationManager(
            sticky=app.config.get("sticky", False)
        )
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
    
    def _determine_tool_stickiness(self, tool_config: ToolConfig) -> bool:
        """Determine tool stickiness based on app and tool config"""
        app_sticky = self.app.config.get("sticky", False)
        
        # If app isn't sticky, tools can't be sticky
        if not app_sticky:
            return False
        
        # Check if tool explicitly sets sticky
        if "sticky" in tool_config.config:
            return tool_config.config["sticky"]
        
        # Default to app stickiness
        return app_sticky
    
    async def _setup_tools(self, field: MagneticField, workspace_path: str):
        """Setup tools"""
        self.logger.info("\nSetting up tools...")
        self.logger.info(f"Available tools: {list(self.app.tool_configs.keys())}")
        
        # Print masked tool configs
        masked_configs = {
            name: self._mask_sensitive_data(config.__dict__)
            for name, config in self.app.tool_configs.items()
        }
        self.logger.debug(f"Tool configs: {masked_configs}")
        
        # Create tools with appropriate configuration
        for tool_name, tool_config in self.app.tool_configs.items():
            self.logger.info(f"\nSetting up tool: {tool_name}")
            
            # Print masked tool config
            self.logger.debug(f"Tool config: {self._mask_sensitive_data(tool_config.__dict__)}")
            
            # Get API key from environment if specified
            api_key = None
            if tool_config.api_key and tool_config.api_key.startswith("env:"):
                env_var = tool_config.api_key.replace("env:", "")
                api_key = os.getenv(env_var)
                if not api_key:
                    raise ValueError(
                        f"No API key found in environment variable {env_var} "
                        f"for tool {tool_name}"
                    )
                self.logger.info(f"Using API key from environment: {env_var}")
            
            try:
                # Create tool with config
                self.logger.info(f"Creating tool with provider: {tool_config.provider}")
                
                # Determine tool stickiness
                sticky = self._determine_tool_stickiness(tool_config)
                
                # Set workspace path for file operations
                config = {
                    **tool_config.config,
                    "sticky": sticky,
                    "workspace_dir": workspace_path
                }
                
                tool = create_tool(
                    tool_name,
                    api_key=api_key,
                    provider=tool_config.provider,
                    **config
                )
                
                # Add tool to field
                self.logger.info("Adding tool to field")
                await field.add_resource(tool)
                
                self.tools[tool_name] = tool
                self.logger.info(f"Tool {tool_name} setup complete (sticky={sticky})")
            except Exception as e:
                self.logger.error(f"Error setting up tool {tool_name}: {str(e)}")
                raise
    
    async def _setup_models(self):
        """Setup models"""
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
                
                # Extract model configuration
                model_settings = {
                    "api_key": api_key,
                    "system_prompt": config.role,
                }
                
                # Add optional configuration
                model_settings.update(config.config)
                
                # Print masked settings
                masked_settings = self._mask_sensitive_data(model_settings)
                self.logger.debug(f"Creating model with settings: {masked_settings}")
                
                self.models[model_name] = OpenRouterProvider(**model_settings)
                self.logger.info(f"Model {model_name} setup complete")
    
    async def _setup_workflow(self, field: MagneticField):
        """Setup workflow attractions and repulsions"""
        if not self.app.workflow:
            return
        
        self.logger.info("\nSetting up workflow...")
        
        # Setup attractions
        for source, target in self.app.workflow.attractions:
            self.logger.info(f"Creating attraction: {source} >< {target}")
            source_tool = self.tools.get(source)
            target_tool = self.tools.get(target)
            
            if source_tool and target_tool:
                await field.attract(source_tool, target_tool)
            else:
                # Skip if either is a model - models don't need to be magnetic
                if source not in self.models and target not in self.models:
                    self.logger.warning(f"Could not find tools for {source} >< {target}")
        
        # Setup repulsions
        for source, target in self.app.workflow.repulsions:
            self.logger.info(f"Creating repulsion: {source} <> {target}")
            source_tool = self.tools.get(source)
            target_tool = self.tools.get(target)
            
            if source_tool and target_tool:
                await field.repel(source_tool, target_tool)
            else:
                # Skip if either is a model - models don't need to be magnetic
                if source not in self.models and target not in self.models:
                    self.logger.warning(f"Could not find tools for {source} <> {target}")
    
    def _get_binding_patterns(self) -> Dict[str, List[Tuple[str, str]]]:
        """Get binding patterns from workflow"""
        patterns = {
            'glue': [],
            'velcro': [],
            'magnet': [],
            'tape': []
        }
        
        if self.app.workflow:
            # Convert attractions to tape bindings
            for source, target in self.app.workflow.attractions:
                patterns['tape'].append((source, target))
        
        return patterns
    
    async def execute(self) -> Any:
        """Execute GLUE application"""
        # Setup models first (they don't need the field)
        await self._setup_models()
        
        try:
            # Get workspace based on app stickiness
            workspace_path = self.workspace_manager.get_workspace(
                self.app.name,
                sticky=self.app.config.get("sticky", False)
            )
            
            # Create magnetic field for tools
            async with MagneticField(self.app.name) as field:
                # Setup tools in field
                await self._setup_tools(field, workspace_path)
                
                # Setup workflow
                await self._setup_workflow(field)
                
                # Create workspace
                async with workspace(self.app.name) as ws:
                    # Interactive prompt loop
                    while True:
                        print("\nprompt:", flush=True)
                        user_input = await asyncio.get_event_loop().run_in_executor(None, input)
                        
                        if user_input.lower() in ['exit', 'quit']:
                            break
                        
                        # Get model's response using conversation manager
                        print("\nthinking...", flush=True)
                        
                        # Get binding patterns from workflow
                        binding_patterns = self._get_binding_patterns()
                        
                        # Process through conversation manager
                        response = await self.conversation.process(
                            models=self.models,
                            binding_patterns=binding_patterns,
                            user_input=user_input,
                            tools=self.tools
                        )
                        
                        print(f"\nresponse: {response}", flush=True)
        finally:
            # Save conversation state if sticky
            if self.app.config.get("sticky", False):
                self.conversation.save_state()
            
            # Cleanup any remaining sessions
            for tool in self.tools.values():
                if hasattr(tool, 'cleanup'):
                    await tool.cleanup()
            
            # Cleanup workspace if not sticky
            if not self.app.config.get("sticky", False):
                self.workspace_manager.cleanup_workspace(workspace_path)

async def execute_glue_app(app: GlueApp) -> Any:
    """Execute GLUE application"""
    executor = GlueExecutor(app)
    return await executor.execute()
