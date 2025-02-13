"""Pydantic models for GLUE core components"""

from datetime import datetime
from typing import Dict, List, Set, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, ConfigDict
from enum import Enum

from .types import AdhesiveType, IntentAnalysis

class ModelConfig(BaseModel):
    """Configuration for a model"""
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1000, gt=0)
    top_p: float = Field(default=1.0, ge=0.0, le=1.0)
    presence_penalty: float = Field(default=0.0)
    frequency_penalty: float = Field(default=0.0)
    stop_sequences: List[str] = Field(default_factory=list)
    system_prompt: Optional[str] = None
    provider_config: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration")

class ToolResult(BaseModel):
    """Result from a tool execution"""
    tool_name: str
    result: Any
    adhesive: AdhesiveType
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class TeamContext(BaseModel):
    """Shared team context"""
    shared_knowledge: Dict[str, Any] = Field(default_factory=dict)
    shared_results: Dict[str, ToolResult] = Field(default_factory=dict)
    team_state: Dict[str, Any] = Field(default_factory=dict)

class ConversationMessage(BaseModel):
    """A message in the conversation history"""
    type: str = Field(..., description="Type of interaction (message, tool_use, etc)")
    content: Any
    timestamp: datetime = Field(default_factory=datetime.now)
    team: str
    tools_used: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ToolBinding(BaseModel):
    """Tool binding configuration"""
    tool_name: str
    adhesive: AdhesiveType
    permissions: List[str] = Field(default_factory=list)
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('adhesive')
    @classmethod
    def validate_adhesive(cls, v):
        if v not in AdhesiveType:
            raise ValueError(f'Invalid adhesive type: {v}')
        return v

class ModelState(BaseModel):
    """Current state of a model"""
    name: str
    provider: str
    team: str
    available_adhesives: Set[AdhesiveType]
    role: Optional[str] = None
    config: ModelConfig
    tool_bindings: Dict[str, ToolBinding] = Field(default_factory=dict)
    session_results: Dict[str, ToolResult] = Field(default_factory=dict)
    conversation_history: List[ConversationMessage] = Field(default_factory=list)
    team_context: TeamContext = Field(default_factory=TeamContext)
    attracted_to: Set[str] = Field(default_factory=set)
    repelled_by: Set[str] = Field(default_factory=set)

    model_config = ConfigDict(arbitrary_types_allowed=True)

class SmolAgentsTool(BaseModel):
    """SmolAgents tool wrapper"""
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    inputs: Dict[str, Dict[str, Any]] = Field(..., description="Input schema")
    output_type: str = Field(..., description="Output type")
    forward_func: Any = Field(..., description="Tool implementation function")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

class PrefectTaskConfig(BaseModel):
    """Configuration for Prefect task integration"""
    max_retries: int = Field(default=3)
    retry_delay_seconds: int = Field(default=10)
    timeout_seconds: int = Field(default=300)
    cache_key_fn: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class MagneticFlow(BaseModel):
    """Magnetic flow between teams with Prefect integration"""
    source_team: str
    target_team: str
    flow_type: str
    prefect_config: Optional[PrefectTaskConfig] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator('flow_type')
    @classmethod
    def validate_flow_type(cls, v):
        if v not in {'push', 'pull', 'repel'}:
            raise ValueError(f'Invalid flow type: {v}')
        return v
