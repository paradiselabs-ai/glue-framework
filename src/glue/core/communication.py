# src/glue/core/communication.py

"""GLUE Model Communication System"""

from typing import Dict, List, Any, Optional, Set
from collections import defaultdict
from datetime import datetime
from .model import Model
from .memory import MemoryManager
from .context import ContextState
from .logger import get_logger
from .types import Message, MessageType, WorkflowState

class ModelCommunication:
    """Manages communication between models"""
    
    def __init__(self, memory_manager: Optional[MemoryManager] = None):
        self.memory_manager = memory_manager or MemoryManager()
        self.logger = get_logger()
        self.active_workflows: Dict[str, WorkflowState] = {}
        self.pending_messages: Dict[str, List[Message]] = defaultdict(list)
        self.message_handlers: Dict[MessageType, List[callable]] = defaultdict(list)
        
    async def send_message(
        self,
        sender: Model,
        receiver: Model,
        msg_type: MessageType,
        content: Any,
        context: Optional[ContextState] = None,
        workflow_id: Optional[str] = None,
        requires_response: bool = False,
        response_timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Message]:
        """Send a message from one model to another"""
        message = Message(
            msg_type=msg_type,
            sender=sender.name,
            receiver=receiver.name,
            content=content,
            context=context,
            workflow_id=workflow_id,
            requires_response=requires_response,
            response_timeout=response_timeout,
            metadata=metadata or {}
        )
        
        # Store in memory
        self.memory_manager.store(
            key=f"message_{message.timestamp.isoformat()}",
            content=message,
            context=context,
            memory_type="short_term"
        )
        
        # Add to pending if response required
        if requires_response:
            self.pending_messages[receiver.name].append(message)
            
        # Handle based on message type
        if msg_type == MessageType.TOOL_REQUEST:
            return await self._handle_tool_request(message, sender, receiver)
        elif msg_type == MessageType.WORKFLOW:
            return await self._handle_workflow_message(message, sender, receiver)
        elif msg_type == MessageType.SYNC:
            return await self._handle_sync_message(message, sender, receiver)
        else:
            # Default handling
            return await self._deliver_message(message, receiver)
            
    async def _deliver_message(
        self,
        message: Message,
        receiver: Model
    ) -> Optional[Message]:
        """Deliver a message to its recipient"""
        try:
            # Enhance message with context
            enhanced_content = self._enhance_with_context(
                message.content,
                message.context
            )
            
            # Generate response if needed
            if message.requires_response:
                response_content = await receiver.generate(enhanced_content)
                response = Message(
                    msg_type=MessageType.RESPONSE,
                    sender=receiver.name,
                    receiver=message.sender,
                    content=response_content,
                    context=message.context,
                    workflow_id=message.workflow_id
                )
                return response
                
        except Exception as e:
            self.logger.error(f"Error delivering message: {e}")
            return None
            
    def _enhance_with_context(
        self,
        content: Any,
        context: Optional[ContextState]
    ) -> str:
        """Enhance message content with context"""
        if not context:
            return str(content)
            
        return f"""Context:
Type: {context.interaction_type}
Complexity: {context.complexity}
Tools Required: {', '.join(context.tools_required)}

Message:
{content}"""
            
    async def start_workflow(
        self,
        initiator: Model,
        participants: List[Model],
        initial_message: str,
        context: ContextState
    ) -> str:
        """Start a new multi-model workflow"""
        workflow_id = f"workflow_{datetime.now().timestamp()}"
        
        # Create workflow state
        workflow = WorkflowState(
            workflow_id=workflow_id,
            initiator=initiator.name,
            participants={m.name for m in participants},
            current_stage="initiated",
            context=context,
            started_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.active_workflows[workflow_id] = workflow
        
        # Notify all participants
        for participant in participants:
            await self.send_message(
                sender=initiator,
                receiver=participant,
                msg_type=MessageType.WORKFLOW,
                content=initial_message,
                context=context,
                workflow_id=workflow_id,
                requires_response=True
            )
            
        return workflow_id
        
    async def update_workflow(
        self,
        workflow_id: str,
        model: Model,
        new_stage: str,
        message: Optional[str] = None
    ) -> None:
        """Update a workflow's state"""
        if workflow_id not in self.active_workflows:
            raise ValueError(f"Unknown workflow: {workflow_id}")
            
        workflow = self.active_workflows[workflow_id]
        
        if model.name not in workflow.participants:
            raise ValueError(f"Model {model.name} not in workflow {workflow_id}")
            
        # Update state
        workflow.current_stage = new_stage
        workflow.updated_at = datetime.now()
        
        # Notify other participants
        if message:
            for participant in workflow.participants:
                if participant != model.name:
                    receiver = self._get_model_by_name(participant)
                    if receiver:
                        await self.send_message(
                            sender=model,
                            receiver=receiver,
                            msg_type=MessageType.WORKFLOW,
                            content=message,
                            context=workflow.context,
                            workflow_id=workflow_id
                        )
                        
    async def _handle_tool_request(
        self,
        message: Message,
        sender: Model,
        receiver: Model
    ) -> Optional[Message]:
        """Handle a tool request message"""
        try:
            tool_name = message.content.get("tool")
            tool_input = message.content.get("input")
            
            if tool_name in receiver._tools:
                tool = receiver._tools[tool_name]
                result = await tool.execute(tool_input)
                
                return Message(
                    msg_type=MessageType.TOOL_RESULT,
                    sender=receiver.name,
                    receiver=sender.name,
                    content=result,
                    context=message.context,
                    workflow_id=message.workflow_id
                )
            else:
                raise ValueError(f"Tool {tool_name} not available")
                
        except Exception as e:
            self.logger.error(f"Error handling tool request: {e}")
            return None
            
    async def _handle_workflow_message(
        self,
        message: Message,
        sender: Model,
        receiver: Model
    ) -> Optional[Message]:
        """Handle a workflow coordination message"""
        if not message.workflow_id:
            return None
            
        workflow = self.active_workflows.get(message.workflow_id)
        if not workflow:
            return None
            
        # Update workflow state
        workflow.updated_at = datetime.now()
        
        # Generate response if needed
        if message.requires_response:
            response_content = await receiver.generate(
                self._enhance_with_context(message.content, message.context)
            )
            
            return Message(
                msg_type=MessageType.RESPONSE,
                sender=receiver.name,
                receiver=sender.name,
                content=response_content,
                context=message.context,
                workflow_id=message.workflow_id
            )
            
    async def _handle_sync_message(
        self,
        message: Message,
        sender: Model,
        receiver: Model
    ) -> Optional[Message]:
        """Handle a state synchronization message"""
        try:
            # Update shared memory
            self.memory_manager.share(
                from_model=sender.name,
                to_model=receiver.name,
                key=f"sync_{message.timestamp.isoformat()}",
                content=message.content,
                context=message.context
            )
            
            # Acknowledge sync
            return Message(
                msg_type=MessageType.RESPONSE,
                sender=receiver.name,
                receiver=sender.name,
                content="State synchronized",
                context=message.context,
                workflow_id=message.workflow_id
            )
            
        except Exception as e:
            self.logger.error(f"Error handling sync message: {e}")
            return None
            
    def register_handler(
        self,
        msg_type: MessageType,
        handler: callable
    ) -> None:
        """Register a custom message handler"""
        self.message_handlers[msg_type].append(handler)
        
    def _get_model_by_name(self, name: str) -> Optional[Model]:
        """Helper to get model by name"""
        # This should be implemented based on your model management system
        raise NotImplementedError
        
    def get_workflow_state(self, workflow_id: str) -> Optional[WorkflowState]:
        """Get the current state of a workflow"""
        return self.active_workflows.get(workflow_id)
        
    def get_pending_messages(self, model_name: str) -> List[Message]:
        """Get pending messages for a model"""
        return self.pending_messages.get(model_name, [])
