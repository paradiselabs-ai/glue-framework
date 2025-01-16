# src/glue/dsl/parser.py

"""GLUE DSL Parser"""

import re
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from ..core.logger import get_logger
from ..core.binding import AdhesiveType
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
    tools: Dict[str, AdhesiveType]
    role: Optional[str]
    chain: Optional[Dict[str, Any]] = None  # Add chain support

@dataclass
class ToolConfig:
    """Tool Configuration"""
    path: Optional[str]
    provider: Optional[str]
    api_key: Optional[str]
    config: Dict[str, Any]

@dataclass
class WorkflowConfig:
    """Workflow Configuration"""
    attractions: List[Tuple[str, str]]  # (source, target) pairs
    repulsions: List[Tuple[str, str]]   # (source, target) pairs
    chat: List[Tuple[str, str]] = field(default_factory=list)  # (model1, model2) pairs
    pulls: List[Tuple[str, str]] = field(default_factory=list)  # (target, source) pairs

@dataclass
class GlueApp:
    """GLUE Application Configuration"""
    name: str
    config: Dict[str, Any]
    model_configs: Dict[str, ModelConfig] = field(default_factory=dict)
    tool_configs: Dict[str, ToolConfig] = field(default_factory=dict)
    workflow: Optional[WorkflowConfig] = None
    tools: List[str] = field(default_factory=list)  # List of tool names
    model: Optional[str] = None  # Primary model name

class GlueParser:
    """Parser for GLUE DSL"""
    
    def __init__(self):
        self.app: Optional[GlueApp] = None
        self.models: Dict[str, ModelConfig] = {}
        self.tools: Dict[str, ToolConfig] = {}
        self.workflow: Optional[WorkflowConfig] = None
        self.logger = get_logger()
    
    def parse(self, content: str) -> GlueApp:
        """Parse GLUE DSL content"""
        self.logger.debug("Starting parse")
        # Remove comments
        content = re.sub(r'//.*$', '', content, flags=re.MULTILINE)
        
        # First handle colon-style tool definitions
        for line in content.split('\n'):
            line = line.strip()
            if ':' in line:
                name, value = [x.strip() for x in line.split(':', 1)]
                if not name.startswith(('model', 'tool', 'workflow')):  # Avoid block headers
                    self.tools[name] = ToolConfig(
                        path=self._parse_value(value),
                        provider=None,
                        api_key=None,
                        config={}
                    )
        
        # Extract and parse blocks
        blocks = self._extract_blocks(content)
        self.logger.debug(f"Extracted blocks: {blocks}")
        
        # First pass: Find and parse app block
        for block_type, block_content in blocks:
            if block_type == 'glue app':
                self._parse_app(block_content)
                break
        
        # Second pass: Parse remaining blocks
        for block_type, block_content in blocks:
            self.logger.debug(f"Processing block: {block_type}")
            
            if block_type == 'workflow':
                self._parse_workflow(block_content)
                if self.workflow:
                    self.app.workflow = self.workflow
            elif block_type.startswith('model') or not any(block_type.startswith(x) for x in ['glue app', 'workflow', 'tool']):
                name = block_type.split(None, 1)[1] if ' ' in block_type else block_type
                self._parse_model(name, block_content)
            elif block_type.startswith('tool'):
                name = block_type.split(None, 1)[1]
                self._parse_tool(name, block_content)

        # Final pass: Handle top-level configurations AFTER blocks are parsed
        for line in content.split('\n'):
            line = line.strip()
            if '_role' in line and '=' in line:
                key, value = [x.strip() for x in line.split('=', 1)]
                model_name = key.replace('_role', '').strip()
                if model_name in self.models:
                    self.models[model_name].role = self._parse_value(value)
                    
        if self.app:
            self.app.model_configs = self.models
            if self.workflow:
                self.app.workflow = self.workflow

        return self.app
    
    def _extract_blocks(self, content: str) -> List[Tuple[str, str]]:
        """Extract blocks from content"""
        blocks = []
        self.logger.debug("Starting block extraction")
        
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
                
            block_type = match.group(1).strip()  # Add strip() here
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
        tools = []
        model = None
        
        # Parse lines
        for line in content.split('\n'):
            line = line.strip()
            if not line or '{' in line:
                continue
                
            if '=' in line:
                key, value = [x.strip() for x in line.split('=', 1)]
                if key == 'app_name':
                    name = value.strip('"')
                elif key == 'tools':
                    # Parse comma-separated tool list
                    tools = [t.strip() for t in value.split(',')]
                elif key == 'model':
                    model = value.strip()
                else:
                    config[key] = self._parse_value(value)
        
        self.app = GlueApp(
            name=name,
            config=config,
            tools=tools,
            model=model
        )
        
    def _parse_chain_config(self, value: str) -> Dict[str, Any]:
        """Parse chain configuration"""
        # Remove curly braces and whitespace
        value = value.strip()
        if value.startswith('{'):
            value = value[1:]
        if value.endswith('}'):
            value = value[:-1]
        value = value.strip()
        
        # Split on >> and clean up whitespace
        tools = [t.strip() for t in value.split('>>')]
        
        # Remove any empty strings and create chain config
        tools = [t for t in tools if t]
        if tools:  # Only create config if we have tools
            return {
                "type": "sequential",
                "tools": tools
            }
        return None
    
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
        provider = None
        api_key = None
        config = {}
        tools = {}
        role = None
        chain = None  
        
        # Parse nested blocks first
        nested_blocks = self._extract_blocks(content)
        for block_type, block_content in nested_blocks:
            if block_type == "config":
                config = self._parse_config_block(block_content)
        
        # Parse remaining lines
        lines = [line.strip() for line in content.split('\n')]
        for line in lines:
            if not line or '{' in line:
                continue

            if line.startswith('os.'):
                key = line[3:]
                if key in PROVIDER_KEYWORDS:
                    provider = PROVIDER_KEYWORDS[key]
                    continue
                elif key == 'api_key':
                    if provider:
                        api_key = f"env:{provider.upper()}_API_KEY"
                    continue
            
            if '=' in line:
                parts = line.split('=', 1)
                if len(parts) < 2:
                    continue

                key = parts[0].strip()
                value = parts[1].strip()    
                
                if key == 'double_side_tape':
                    value = value.strip()
                    if value.startswith('{') and value.endswith('}'):
                        # Extract content between braces
                        value = value[1:-1].strip()
                        if '>>' in value:
                            # Split on >> and clean up whitespace
                            tool_chain = [t.strip() for t in value.split('>>')]
                            # Create chain configuration
                            chain = {
                                "type": "sequential",
                                "tools": tool_chain
                            }
                elif key == 'role':
                    role = value.strip('"')
                elif key == 'tools':
                    if '{' in value:
                        tools_block = self._extract_blocks(value)
                        if tools_block:
                            for tool_line in tools_block[0][1].split('\n'):
                                if '=' in tool_line:
                                    tool_name, strength = [x.strip() for x in tool_line.split('=', 1)]
                                    strength = strength.lower()
                                    if strength == 'tape':
                                        tools[tool_name] = AdhesiveType.TAPE
                                    elif strength == 'velcro':
                                        tools[tool_name] = AdhesiveType.VELCRO
                                    elif strength == 'glue':
                                        tools[tool_name] = AdhesiveType.GLUE
                                    elif strength == 'magnet':
                                        tools[tool_name] = AdhesiveType.MAGNET
                    else:
                        tools = {t.strip(): AdhesiveType.VELCRO for t in value.strip('[]').split(',')}
                else:
                    config[key] = self._parse_value(value)
        
        # Create the model config
        model_name = name.split()[-1] if name.startswith('model') else name
        self.logger.debug(f"Creating model with name: {model_name}")
        self.models[model_name] = ModelConfig(
            provider=provider,
            api_key=api_key,
            config=config,
            tools=tools,
            role=role,
            chain=chain
        )
        self.logger.debug(f"After adding model, models dict contains: {list(self.models.keys())}")

    
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
        
        attractions = []  # (source, target, binding_strength)
        repulsions = []
        chat_pairs = []
        pull_pairs = []
        
        # Parse lines for direct attractions first
        for line in content.split('\n'):
            line = line.strip()
            if "><" in line:
                # Check for binding strength
                if "|" in line:
                    attraction, strength = line.split("|")
                    parts = [p.strip() for p in attraction.split("><")]
                    if len(parts) == 2:
                        try:
                            # Convert string to AdhesiveType
                            strength = strength.strip().lower()
                            if strength == 'tape':
                                binding = AdhesiveType.TAPE
                            elif strength == 'velcro':
                                binding = AdhesiveType.VELCRO
                            elif strength == 'glue':
                                binding = AdhesiveType.GLUE
                            elif strength == 'magnet':
                                binding = AdhesiveType.MAGNET
                            else:
                                raise ValueError(f"Invalid binding type: {strength}")
                            attractions.append((parts[0], parts[1]))
                        except ValueError:
                            self.logger.warning(f"Invalid binding strength: {strength}")
                else:
                    parts = [p.strip() for p in line.split("><")]
                    if len(parts) == 2:
                        # Default to VELCRO if no binding specified
                        attractions.append((parts[0], parts[1]))
            elif "<>" in line:
                parts = [p.strip() for p in line.split("<>")]
                if len(parts) == 2:
                    repulsions.append((parts[0], parts[1]))
            elif "<-" in line:
                parts = [p.strip() for p in line.split("<-")]
                if len(parts) == 2:
                    # Note: parts[0] is target, parts[1] is source
                    pull_pairs.append((parts[0], parts[1]))
            elif "<-->" in line:
                parts = [p.strip() for p in line.split("<-->")]
                if len(parts) == 2:
                    chat_pairs.append((parts[0], parts[1]))
        
        # Then parse nested blocks for any additional configurations
        nested_blocks = self._extract_blocks(content)
        for block_type, block_content in nested_blocks:
            if block_type == "magnetic attraction":
                # Parse attraction rules from block
                for line in block_content.split('\n'):
                    line = line.strip()
                    if "><" in line:
                        parts = [p.strip() for p in line.split("><")]
                        if len(parts) == 2:
                            attractions.append((parts[0], parts[1]))
            elif block_type == "magnetic pull":
                # Parse pull rules
                for line in block_content.split('\n'):
                    line = line.strip()
                    if "<-" in line:
                        parts = [p.strip() for p in line.split("<-")]
                        if len(parts) == 2:
                            # Note: parts[0] is target, parts[1] is source
                            pull_pairs.append((parts[0], parts[1]))
            elif block_type == "chat":
                # Parse chat relationships
                for line in block_content.split('\n'):
                    line = line.strip()
                    if "<-->" in line:
                        parts = [p.strip() for p in line.split("<-->")]
                        if len(parts) == 2:
                            chat_pairs.append((parts[0], parts[1]))
            elif block_type == "repel":
                # Parse repulsion rules
                for line in block_content.split('\n'):
                    line = line.strip()
                    if "<>" in line:
                        parts = [p.strip() for p in line.split("<>")]
                        if len(parts) == 2:
                            repulsions.append((parts[0], parts[1]))
        
        self.workflow = WorkflowConfig(
            attractions=attractions,
            repulsions=repulsions,
            chat=chat_pairs,
            pulls=pull_pairs
        )
        # Make sure workflow gets attached to app
        if hasattr(self, 'app') and self.app:
            self.app.workflow = self.workflow

def parse_glue_file(path: str) -> GlueApp:
    """Parse GLUE file"""
    with open(path) as f:
        content = f.read()
    
    parser = GlueParser()
    return parser.parse(content)
