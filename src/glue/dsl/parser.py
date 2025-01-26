# src/glue/dsl/parser.py

"""GLUE DSL Parser"""

import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from ..core.logger import get_logger
from ..core.types import AdhesiveType
from ..core.app import GlueApp
from .keywords import (
    get_keyword_type,
    PROVIDER_KEYWORDS,
    CONFIG_KEYWORDS,
    OPERATION_KEYWORDS,
    APP_KEYWORDS
)

@dataclass
class ToolBindingConfig:
    """Tool binding configuration"""
    tool_name: str
    type: AdhesiveType

@dataclass
class ModelConfig:
    """Model Configuration"""
    provider: str
    api_key: Optional[str]
    config: Dict[str, Any]
    tools: Dict[str, AdhesiveType]  # tool_name -> binding_type
    role: Optional[str]

@dataclass
class ToolConfig:
    """Tool Configuration"""
    path: Optional[str]
    provider: Optional[str]
    api_key: Optional[str]
    config: Dict[str, Any]

@dataclass
class TeamConfig:
    """Team Configuration"""
    name: str
    lead: Optional[str]  # Model name
    members: List[str]  # Model names
    tools: List[str]  # Tool names

@dataclass
class WorkflowConfig:
    """Workflow Configuration"""
    teams: Dict[str, TeamConfig] = field(default_factory=dict)  # name -> config
    attractions: List[Tuple[str, str]] = field(default_factory=list)  # (source, target) pairs
    repulsions: List[Tuple[str, str]] = field(default_factory=list)  # (source, target) pairs
    chat: List[Tuple[str, str]] = field(default_factory=list)  # (model1, model2) pairs
    pulls: List[Tuple[str, str]] = field(default_factory=list)  # (target, source) pairs

@dataclass
class GlueAppConfig:
    """GLUE Application Configuration"""
    name: str
    config: Dict[str, Any]
    model_configs: Dict[str, ModelConfig] = field(default_factory=dict)
    tool_configs: Dict[str, ToolConfig] = field(default_factory=dict)
    workflow: Optional[WorkflowConfig] = None

class GlueParser:
    """Parser for GLUE DSL"""
    
    def __init__(self):
        self.app: Optional[GlueAppConfig] = None
        self.models: Dict[str, ModelConfig] = {}
        self.tools: Dict[str, ToolConfig] = {}
        self.workflow: Optional[WorkflowConfig] = None
        self.logger = get_logger()
    
    def parse(self, content: str) -> GlueAppConfig:
        """Parse GLUE DSL content"""
        # Remove comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        self.logger.debug(f"Cleaned content:\n{content}")
        
        # Extract blocks
        blocks = self._extract_blocks(content)
        self.logger.debug(f"Extracted blocks:\n{blocks}")
        
        # First pass: Find and parse app block
        for block_type, block_content in blocks:
            # Check for app block
            keyword_type, _ = get_keyword_type(block_type)
            if keyword_type == 'app':
                self.logger.debug(f"Parsing app block: {block_type}")
                self._parse_app(block_content)
                break
        
        # Second pass: Parse remaining blocks
        for block_type, block_content in blocks:
            # Skip app blocks (already parsed)
            keyword_type, _ = get_keyword_type(block_type)
            if keyword_type == 'app':
                continue
            
            self.logger.debug(f"Parsing block: {block_type}\nContent: {block_content}")
            
            # Get block type and name
            parts = block_type.strip().split(None, 1)
            block_type = parts[0].lower()
            block_name = parts[1] if len(parts) > 1 else None
            
            if block_type == 'model':
                self._parse_model(block_name, block_content)
            elif block_type == 'tool':
                self._parse_tool(block_name, block_content)
            elif block_type in ['workflow', 'magnetize']:
                self._parse_workflow(block_content)
        
        # Create app with parsed components
        if not self.app:
            self.app = GlueAppConfig(
                name="glue_app",
                config={},
                model_configs=self.models,
                tool_configs=self.tools,
                workflow=self.workflow
            )
        else:
            self.app.model_configs = self.models
            self.app.tool_configs = self.tools
            self.app.workflow = self.workflow
        
        return self.app
    
    def _extract_blocks(self, content: str) -> List[Tuple[str, str]]:
        """Extract blocks from content"""
        blocks = []
        
        # Match block patterns
        def find_matching_brace(s: str, start: int) -> int:
            """Find matching closing brace"""
            count = 1
            i = start
            while count > 0 and i < len(s):
                if s[i] == '{':
                    count += 1
                elif s[i] == '}':
                    count -= 1
                i += 1
            return i - 1 if count == 0 else -1
        
        # Find blocks with braces
        i = 0
        while i < len(content):
            # Find block start
            match = re.search(r'(\w+(?:\s+\w+)?)\s*{', content[i:])
            if not match:
                break
                
            block_type = match.group(1)
            block_start = i + match.end()
            
            # Find matching closing brace
            block_end = find_matching_brace(content, block_start)
            if block_end == -1:
                break
                
            # Extract block content
            block_content = content[block_start:block_end].strip()
            blocks.append((block_type, block_content))
            
            i = block_end + 1
        
        return blocks
    
    def _parse_value(self, value: str) -> Any:
        """Parse a value, converting types as needed"""
        # Remove quotes if present
        value = value.strip('"')
        
        # Convert to bool if true/false
        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        
        # Try to convert to number
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
    
    def _parse_app(self, content: str):
        """Parse app block"""
        self.logger.debug(f"Parsing app block:\n{content}")
        
        name = "glue_app"
        config = {}
        
        # Parse nested blocks
        nested_blocks = self._extract_blocks(content)
        for block_type, block_content in nested_blocks:
            if block_type == "config":
                config = self._parse_config_block(block_content)
        
        # Parse remaining lines for top-level config
        for line in content.split('\n'):
            line = line.strip()
            if line and '=' in line and '{' not in line:
                key, value = [x.strip() for x in line.split('=', 1)]
                if key == 'name':
                    name = value.strip('"')
                else:
                    config[key] = self._parse_value(value)
        
        self.app = GlueAppConfig(
            name=name,
            config=config
        )
    
    def _parse_config_block(self, content: str) -> Dict[str, Any]:
        """Parse a config block"""
        config = {}
        for line in content.split('\n'):
            line = line.strip()
            if line and '=' in line:
                key, value = [x.strip() for x in line.split('=', 1)]
                config[key] = self._parse_value(value)
        return config
    
    def _parse_model(self, name: str, content: str):
        """Parse model block"""
        self.logger.debug(f"Parsing model {name}:\n{content}")
        
        provider = None
        api_key = None
        config = {}
        tools = {}  # tool_name -> binding_strength
        role = None
        
        # SmoLAgents specific config
        agent_type = None
        model_type = None
        model_name = None
        
        # Parse nested blocks
        nested_blocks = self._extract_blocks(content)
        for block_type, block_content in nested_blocks:
            if block_type == "config":
                config = self._parse_config_block(block_content)
        
        # Parse remaining lines
        for line in content.split('\n'):
            line = line.strip()
            if not line or '{' in line:
                continue
            
            if '=' in line:
                key, value = [x.strip() for x in line.split('=', 1)]
                key = key.lower()
                
                # First check if it's the provider key directly
                if key == 'provider':
                    # Get normalized provider value
                    _, normalized = get_keyword_type(value.lower())
                    provider = normalized
                    self.logger.debug(f"Found provider: {provider}")
                    
                    # If it's smolagents, look for specific config
                    if provider == 'smolagents':
                        # Set defaults
                        agent_type = 'code'  # Default to CodeAgent
                        model_type = 'hf'    # Default to HuggingFace
                elif key == 'tools':
                    # Parse tools block
                    tools_block = self._extract_blocks(value)
                    if tools_block:
                        # Parse tool bindings from block
                        for line in tools_block[0][1].split('\n'):
                            line = line.strip()
                            if '=' in line:
                                tool_name, strength = [x.strip() for x in line.split('=', 1)]
                                try:
                                    # Convert string to AdhesiveType
                                    if strength.lower() == 'tape':
                                        tools[tool_name] = AdhesiveType.TAPE
                                    elif strength.lower() == 'velcro':
                                        tools[tool_name] = AdhesiveType.VELCRO
                                    elif strength.lower() == 'glue':
                                        tools[tool_name] = AdhesiveType.GLUE
                                    else:
                                        raise ValueError(f"Invalid binding type: {strength} - must be tape, velcro, or glue")
                                except ValueError:
                                    self.logger.warning(f"Invalid binding strength: {strength}")
                    else:
                        # Legacy format: comma-separated list
                        tools = {t.strip(): AdhesiveType.VELCRO 
                               for t in value.strip('[]').split(',')}
                elif key == 'role':
                    role = value.strip('"')
                elif key.startswith('os.'):
                    api_key = f"env:{key[3:].upper()}"
                else:
                    # Handle SmoLAgents specific config
                    if key == 'agent_type':
                        agent_type = SMOLAGENTS_KEYWORDS.get(value.lower(), 'code')
                    elif key == 'model_type':
                        model_type = SMOLAGENTS_KEYWORDS.get(value.lower(), 'hf')
                    elif key == 'model_name':
                        model_name = value.strip('"')
                    # Add to config if not a special key
                    elif key not in ['provider', 'tools', 'role']:
                        config[key] = self._parse_value(value)
        
        # Create model config
        if provider == 'smolagents':
            # Add SmoLAgents specific config
            config.update({
                'agent_type': agent_type,
                'model_type': model_type,
                'model_name': model_name
            })
            
        self.models[name] = ModelConfig(
            provider=provider,
            api_key=api_key,
            config=config,
            tools=tools,
            role=role
        )
    
    def _parse_tool(self, name: str, content: str):
        """Parse tool block"""
        self.logger.debug(f"Parsing tool {name}:\n{content}")
        
        provider = None
        api_key = None
        config = {}
        
        # Parse nested blocks
        nested_blocks = self._extract_blocks(content)
        for block_type, block_content in nested_blocks:
            if block_type == "config":
                config = self._parse_config_block(block_content)
        
        # Parse remaining lines
        for line in content.split('\n'):
            line = line.strip()
            if not line or '{' in line:
                continue
            
            # Check for os.* environment variables first
            if line.startswith('os.'):
                api_key = f"env:{line[3:].upper()}"
                self.logger.debug(f"Found API key: {api_key}")
                continue
            
            if '=' in line:
                key, value = [x.strip() for x in line.split('=', 1)]
                key = key.lower()
                
                # First check if it's the provider key directly
                if key == 'provider':
                    # Get normalized provider value
                    _, normalized = get_keyword_type(value.lower())
                    provider = normalized
                    self.logger.debug(f"Found provider: {provider}")
                else:
                    # Add to config if not a special key
                    if key not in ['provider']:
                        config[key] = self._parse_value(value)
        
        self.tools[name] = ToolConfig(
            path=None,
            provider=provider,
            api_key=api_key,
            config=config
        )
    

    def _parse_workflow(self, content: str):
        """Parse workflow block"""
        self.logger.debug(f"Parsing workflow block:\n{content}")
        
        teams = {}
        attractions = []
        repulsions = []
        pull_pairs = []
        
        # Parse team blocks
        nested_blocks = self._extract_blocks(content)
        for block_type, block_content in nested_blocks:
            # Get team name
            team_name = block_type
            
            # Parse team config
            lead = None
            members = []
            tools = []
            
            for line in block_content.split('\n'):
                line = line.strip()
                if '=' in line:
                    key, value = [x.strip() for x in line.split('=', 1)]
                    if key == 'lead':
                        lead = value.strip('"')
                    elif key == 'members':
                        members = [m.strip() for m in value.strip('[]').split(',')]
                    elif key == 'tools':
                        tools = [t.strip() for t in value.strip('[]').split(',')]
                        
            teams[team_name] = TeamConfig(
                name=team_name,
                lead=lead,
                members=members,
                tools=tools
            )
        
        # Parse flow lines
        for line in content.split('\n'):
            line = line.strip()
            if "->" in line:  # Push flow
                parts = [p.strip() for p in line.split("->")]
                if len(parts) == 2:
                    attractions.append((parts[0], parts[1]))
            elif "<-" in line and "pull" in line.lower():  # Pull flow
                parts = [p.strip() for p in line.split("<-")]
                if len(parts) == 2:
                    target = parts[0].strip()
                    source = parts[1].strip()
                    pull_pairs.append((target, source))
            elif "<>" in line:  # Repulsion
                parts = [p.strip() for p in line.split("<>")]
                if len(parts) == 2:
                    repulsions.append((parts[0], parts[1]))
        
        self.workflow = WorkflowConfig(
            teams=teams,
            attractions=attractions,
            repulsions=repulsions,
            pulls=pull_pairs
        )

def parse_glue_file(path: str) -> GlueAppConfig:
    """Parse GLUE file"""
    with open(path) as f:
        content = f.read()
    
    parser = GlueParser()
    return parser.parse(content)
