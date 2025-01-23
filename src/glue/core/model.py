# src/glue/core/model.py
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field
from datetime import datetime
from .types import Message, MessageType, WorkflowState, IntentAnalysis
from ..tools.base import BaseTool
from .tool_binding import ToolBinding, AdhesiveType, ToolBindingState

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

    def add_tool(self, name: str, tool: BaseTool, binding_type: str = 'velcro') -> None:
        """
        Add a tool that this model can use
        
        Args:
            name: Name of the tool
            tool: Tool instance
            binding_type: Type of binding (glue, velcro, tape)
        """
        # Create appropriate binding based on persistence needs
        if binding_type == 'glue':
            # Permanent binding with full persistence
            binding = ToolBinding.glue(
                properties={
                    "maintains_context": True,
                    "context_duration": "permanent"
                }
            )
        elif binding_type == 'velcro':
            # Flexible binding with session persistence
            binding = ToolBinding.velcro(
                properties={
                    "maintains_context": True,
                    "context_duration": "session",
                    "reconnect_attempts": 3
                }
            )
        else:  # tape
            # Temporary binding with no persistence
            binding = ToolBinding.tape(
                properties={
                    "maintains_context": False,
                    "duration_ms": 1800000  # 30 minutes
                }
            )
            
        # Initialize binding
        binding.bind()
        
        # Create tool instance with binding
        instance = tool.create_instance(binding=binding)
        
        # Store tool and binding
        self._tools[name] = instance
        if not hasattr(self, 'tool_bindings'):
            self.tool_bindings = {}
        self.tool_bindings[name] = binding

    def bind_to(self, model: 'Model', binding_type: str = 'glue') -> None:
        """Create a binding to another model"""
        self._bound_models[model.name] = model
        
    async def analyze_intent(self, prompt: str, context: Dict[str, Any]) -> IntentAnalysis:
        """
        Analyze prompt to determine intent and tool needs
        
        Args:
            prompt: The user's prompt
            context: Context about available tools and team members
        """
        # Let the model analyze the prompt
        analysis = await self.generate(
            f"""Analyze this prompt and determine:
1. What tools might be needed
2. How relevant this is to our team ({context['field_name']})
3. Score from 0-1 how strongly we should handle this

Prompt: {prompt}

Available tools:
{chr(10).join(f'- {t}' for t in context['available_tools'])}

Team members:
{chr(10).join(f'- {m}' for m in context['team_members'])}
""")
        
        # Parse the analysis (provider-specific)
        return self._parse_intent_analysis(analysis)
        
    async def process(self, prompt: str, context: Optional[List[Dict]] = None) -> str:
        """
        Process a prompt with context
        
        Args:
            prompt: The prompt to process
            context: Optional conversation history
        """
        # Format context
        context_str = ""
        if context:
            context_str = "\nPrevious conversation:\n" + "\n".join(
                f"{m['type']}: {m['content']}" for m in context
            )
            
        # Generate response
        response = await self.generate(
            f"{self.config.system_prompt or ''}{context_str}\n\nUser: {prompt}"
        )
        
        return response
        
    async def execute_tool(self, tool_name: str, *args, **kwargs) -> Any:
        """Execute a tool owned by this model"""
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not found")
            
        tool = self._tools[tool_name]
        result = await tool.safe_execute(*args, **kwargs)
        
        # Format result for memory
        return tool.format_result(result)
        
    async def generate(self, prompt: str) -> str:
        """Generate a response (to be implemented by provider-specific classes)"""
        raise NotImplementedError
        
    def _parse_intent_analysis(self, analysis: str) -> IntentAnalysis:
        """Parse intent analysis (to be implemented by provider-specific classes)"""
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
