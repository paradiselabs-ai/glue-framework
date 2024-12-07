# src/glue/core/types.py

"""Common types used across GLUE core modules"""

from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

class MessageType(Enum):
    """Types of messages that models can exchange"""
    QUERY = auto()          # Request for information
    RESPONSE = auto()       # Response to a query
    UPDATE = auto()         # State update
    TOOL_REQUEST = auto()   # Request to use a tool
    TOOL_RESULT = auto()    # Result from tool usage
    WORKFLOW = auto()       # Workflow coordination
    SYNC = auto()          # State synchronization

@dataclass
class Message:
    """A message between models"""
    msg_type: MessageType
    sender: str
    receiver: str
    content: Any
    context: Optional['ContextState'] = None
    timestamp: datetime = field(default_factory=datetime.now)
    workflow_id: Optional[str] = None
    requires_response: bool = False
    response_timeout: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class WorkflowState:
    """State of a multi-model workflow"""
    workflow_id: str
    initiator: str
    participants: Set[str]
    current_stage: str
    context: 'ContextState'
    started_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
