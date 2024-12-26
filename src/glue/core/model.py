# src/glue/core/model.py
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from .types import Message, MessageType, WorkflowState
from .logger import get_logger

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
        self.logger = get_logger()

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

    async def use_tool(self, tool_name: str, input_data: Any) -> Any:
        """Execute a tool if available"""
        if tool_name not in self._tools:
            raise ValueError(f"Tool {tool_name} not available")
        return await self._tools[tool_name].execute(input_data)

    async def check_tool_availability(self, tool_name: str) -> bool:
        """Check if a tool is available and usable"""
        return tool_name in self._tools and self._tools[tool_name] is not None

    def bind_to(self, model: 'Model', binding_type: str = 'glue') -> None:
        """Create a binding to another model"""
        self._bound_models[model.name] = model
        
    async def _analyze_tool_needs(self, prompt: str) -> Dict[str, float]:
        """Analyze prompt to determine which tools might be needed.
        Returns dict of tool_name -> confidence score (0-1)"""
        tool_scores = {}
        prompt_lower = prompt.lower()
        
        # Common intent patterns
        search_patterns = [
            r'(search|find|look up|research|tell me about)',
            r'(latest|recent|current|new)',
            r'(news|information|details|data)',
            r'what (is|are|was|were)',
            r'how (to|do|does|did)',
            r'when (was|were|did|is)',
            r'where (is|are|was|were)'
        ]
        
        file_patterns = [
            r'(save|write|store|export|output)',
            r'(file|document|report|notes)',
            r'(create|make|generate) (a|the)',
            r'(\.txt|\.md|\.json|\.csv)'
        ]
        
        for tool_name in self._tools:
            tool = self._tools[tool_name]
            if not hasattr(tool, 'description'):
                continue
            
            # Base score from tool description
            description = tool.description.lower()
            keywords = description.split()
            base_score = sum(1 for word in keywords if word in prompt_lower) / len(keywords) if keywords else 0
            
            # Intent matching score
            intent_score = 0
            if tool_name == 'web_search':
                intent_score = max(
                    sum(1 for pattern in search_patterns if re.search(pattern, prompt_lower)) / len(search_patterns),
                    base_score
                )
            elif tool_name == 'file_handler':
                intent_score = max(
                    sum(1 for pattern in file_patterns if re.search(pattern, prompt_lower)) / len(file_patterns),
                    base_score
                )
            
            # Combine scores with intent having higher weight
            final_score = (intent_score * 0.7 + base_score * 0.3)
            if final_score > 0:
                tool_scores[tool_name] = final_score
                self.logger.debug(f"Tool {tool_name} score: {final_score:.2f}")
        
        return tool_scores

    async def _execute_tool_chain(
        self,
        prompt: str,
        tool_scores: Dict[str, float]
    ) -> Dict[str, Any]:
        """Execute a chain of tools based on scores and dependencies"""
        results = {}
        
        # Sort tools by score
        sorted_tools = sorted(
            tool_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        for tool_name, score in sorted_tools:
            if score < 0.1:  # Minimum confidence threshold
                continue
                
            try:
                # Check if tool is available and we can use it
                if await self.check_tool_availability(tool_name):
                    self.logger.debug(f"Executing tool {tool_name} (score: {score})")
                    result = await self.use_tool(tool_name, prompt)
                    results[tool_name] = result
                    
                    # Share results with bound models if needed
                    for model in self._bound_models.values():
                        if hasattr(model, "_tools"):
                            await self.send_message(
                                receiver=model,
                                content=result,
                                requires_response=True
                            )
            except Exception as e:
                self.logger.error(f"Tool {tool_name} execution failed: {str(e)}")
                continue
        
        return results

    async def _enhance_prompt_with_results(
        self,
        prompt: str,
        tool_results: Dict[str, Any]
    ) -> str:
        """Enhance the original prompt with tool results"""
        if not tool_results:
            return prompt
            
        enhanced = [prompt, "\n\nTool Results:"]
        for tool_name, result in tool_results.items():
            enhanced.append(f"\n\n{tool_name} Results:\n{result}")
        
        return "\n".join(enhanced)

    async def generate(self, prompt: str) -> str:
        """Generate a response using available tools and capabilities"""
        try:
            # Analyze which tools might be needed
            tool_scores = await self._analyze_tool_needs(prompt)
            
            # Execute relevant tools
            tool_results = await self._execute_tool_chain(prompt, tool_scores)
            
            # Enhance prompt with tool results
            enhanced_prompt = await self._enhance_prompt_with_results(
                prompt, tool_results
            )
            
            # Generate response (to be implemented by provider-specific classes)
            raise NotImplementedError
            
        except Exception as e:
            raise RuntimeError(f"Generation failed: {str(e)}")

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
        
        self._active_workflows[workflow_id] = self._communication.get_workflow_state(workflow_id)
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
            
        if workflow_id not in self._active_workflows:
            raise ValueError(f"Not participating in workflow {workflow_id}")
            
        await self._communication.update_workflow(
            workflow_id=workflow_id,
            model=self,
            new_stage=new_stage,
            message=message
        )

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
