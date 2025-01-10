# src/glue/core/model.py
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from .types import Message, MessageType, WorkflowState

@dataclass
class ModelConfig:
    """Configuration for a model"""
    temperature: float = 0.7
    max_tokens: int = 1000
    top_p: float = 1.0
    presence_penalty: float = 0.0
    frequency_penalty: float = 0.0
    stop_sequences: list[str] = field(default_factory=list)
    system_prompt: Optional[str] = None

class Model:
    """Base class for individual models within a CBM"""
    def __init__(
        self, 
        name: str,
        provider: str,
        api_key: Optional[str] = None,
        config: Optional[ModelConfig] = None,
        communication: Optional['ModelCommunication'] = None
    ):
        self.name = name
        self.provider = provider
        self.api_key = api_key
        self.config = config or ModelConfig()
        self.role: Optional[str] = None
        self._prompts: Dict[str, str] = {}
        self._tools: Dict[str, Any] = {}
        self._bound_models: Dict[str, 'Model'] = {}
        self._communication = communication
        self._active_workflows: Dict[str, WorkflowState] = {}

    def add_prompt(self, name: str, content: str) -> None:
        """Add a prompt template"""
        self._prompts[name] = content

    def get_prompt(self, name: str) -> Optional[str]:
        """Get a prompt template"""
        return self._prompts.get(name)

    def set_role(self, role: str) -> None:
        """Set the model's role in the CBM"""
        self.role = role
        # Also set as system prompt if not already set
        if not self.config.system_prompt:
            self.config.system_prompt = role

    def add_tool(self, name: str, tool: Any) -> None:
        """Add a tool that this model can use"""
        self._tools[name] = tool

    def bind_to(self, model: 'Model', binding_type: str = 'glue') -> None:
        """Create a binding to another model"""
        self._bound_models[model.name] = model
        
    async def generate(self, prompt: str) -> str:
        """Generate a response (to be implemented by provider-specific classes)"""
        raise NotImplementedError

    # Communication methods
    async def send_message(
        self,
        receiver: 'Model',
        content: Any,
        msg_type: MessageType = MessageType.QUERY,
        requires_response: bool = False,
        context: Optional['ContextState'] = None,
        workflow_id: Optional[str] = None
    ) -> Optional[Message]:
        """Send a message to another model"""
        if not self._communication:
            raise RuntimeError("Communication system not initialized")
            
        if receiver.name not in self._bound_models:
            raise ValueError(f"No binding exists with model {receiver.name}")
            
        return await self._communication.send_message(
            sender=self,
            receiver=receiver,
            msg_type=msg_type,
            content=content,
            context=context,
            workflow_id=workflow_id,
            requires_response=requires_response
        )

    async def request_tool(
        self,
        receiver: 'Model',
        tool_name: str,
        tool_input: Any,
        context: Optional['ContextState'] = None
    ) -> Optional[Any]:
        """Request to use another model's tool"""
        if not self._communication:
            raise RuntimeError("Communication system not initialized")
            
        response = await self._communication.send_message(
            sender=self,
            receiver=receiver,
            msg_type=MessageType.TOOL_REQUEST,
            content={
                "tool": tool_name,
                "input": tool_input
            },
            context=context,
            requires_response=True
        )
        
        if response and response.msg_type == MessageType.TOOL_RESULT:
            return response.content
        return None

    async def start_workflow(
        self,
        participants: List['Model'],
        initial_message: str,
        context: Optional['ContextState'] = None
    ) -> str:
        """Start a new workflow with other models"""
        if not self._communication:
            raise RuntimeError("Communication system not initialized")
            
        # Verify bindings exist
        for participant in participants:
            if participant.name not in self._bound_models:
                raise ValueError(f"No binding exists with model {participant.name}")
                
        workflow_id = await self._communication.start_workflow(
            initiator=self,
            participants=participants,
            initial_message=initial_message,
            context=context
        )
        
        # Get the workflow state from communication system
        workflow_state = self._communication.get_workflow_state(workflow_id)
        if workflow_state:
            self._active_workflows[workflow_id] = workflow_state
            # Sync workflow state to all participants
            for participant in participants:
                participant._active_workflows[workflow_id] = workflow_state
        
        return workflow_id

    async def update_workflow(
        self,
        workflow_id: str,
        new_stage: str,
        message: Optional[str] = None
    ) -> None:
        """Update a workflow's state"""
        if not self._communication:
            raise RuntimeError("Communication system not initialized")

        # First check with communication system
        workflow_state = self._communication.get_workflow_state(workflow_id)
        if not workflow_state:
            raise ValueError(f"Unknown workflow {workflow_id}")
            
        # Update local workflow state
        if workflow_id not in self._active_workflows:
            if self.name in workflow_state.participants:
                self._active_workflows[workflow_id] = workflow_state
            else:
                raise ValueError(f"Not participating in workflow {workflow_id}")
            
        await self._communication.update_workflow(
            workflow_id=workflow_id,
            model=self,
            new_stage=new_stage,
            message=message
        )

        # Update local state with latest from communication system
        updated_state = self._communication.get_workflow_state(workflow_id)
        if updated_state:
            self._active_workflows[workflow_id] = updated_state

    def get_pending_messages(self) -> List[Message]:
        """Get pending messages for this model"""
        if not self._communication:
            raise RuntimeError("Communication system not initialized")
            
        return self._communication.get_pending_messages(self.name)

    def get_active_workflows(self) -> Dict[str, WorkflowState]:
        """Get all active workflows this model is participating in"""
        return self._active_workflows.copy()

    def set_communication(self, communication: 'ModelCommunication') -> None:
        """Set the communication system"""
        self._communication = communication
