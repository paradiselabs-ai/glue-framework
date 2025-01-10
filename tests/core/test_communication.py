# tests/core/test_communication.py

import pytest
from glue.core.model import Model
from glue.core.memory import MemoryManager
from glue.core.communication import (
    ModelCommunication,
    MessageType
)
from glue.core.context import ContextState, InteractionType, ComplexityLevel

class MockTool:
    """Mock tool for testing"""
    async def execute(self, input_str: str) -> str:
        return f"Executed {input_str}"

class MockModel(Model):
    """Mock model for testing"""
    async def generate(self, prompt: str) -> str:
        return f"Response to: {prompt}"

@pytest.fixture
def memory_manager():
    """Create memory manager for testing"""
    return MemoryManager()

@pytest.fixture
def communication(memory_manager):
    """Create communication system for testing"""
    return ModelCommunication(memory_manager=memory_manager)

@pytest.fixture
def model1(communication):
    """Create first test model"""
    model = MockModel("model1", "test")
    communication.set_communication(model)
    return model

@pytest.fixture
def model2(communication):
    """Create second test model"""
    model = MockModel("model2", "test")
    communication.set_communication(model)
    return model

@pytest.fixture
def context():
    """Create test context"""
    return ContextState(
        interaction_type=InteractionType.TASK,
        complexity=ComplexityLevel.MODERATE,
        tools_required={"test_tool"},
        requires_research=False,
        requires_memory=False,
        requires_persistence=False,
        confidence=0.8
    )

@pytest.mark.asyncio
async def test_basic_message_passing(model1, model2, context):
    """Test basic message passing between models"""
    # Bind models
    model1.bind_to(model2)
    model2.bind_to(model1)
    
    # Send message
    message = await model1.send_message(
        receiver=model2,
        content="Test message",
        context=context,
        requires_response=True
    )
    
    # Verify response
    assert message is not None
    assert message.msg_type == MessageType.RESPONSE
    assert message.sender == "model2"
    assert message.receiver == "model1"
    assert "Response to: Test message" in message.content

@pytest.mark.asyncio
async def test_tool_request(model1, model2, context):
    """Test tool request between models"""
    # Add tool to model2
    test_tool = MockTool()
    model2.add_tool("test_tool", test_tool)
    
    # Bind models
    model1.bind_to(model2)
    model2.bind_to(model1)
    
    # Request tool use
    result = await model1.request_tool(
        receiver=model2,
        tool_name="test_tool",
        tool_input="test input",
        context=context
    )
    
    # Verify result
    assert result is not None
    assert "Executed test input" in result

@pytest.mark.asyncio
async def test_workflow_management(model1, model2, context):
    """Test workflow management between models"""
    # Bind models
    model1.bind_to(model2)
    model2.bind_to(model1)
    
    # Start workflow
    workflow_id = await model1.start_workflow(
        participants=[model2],
        initial_message="Start workflow",
        context=context
    )
    
    # Verify workflow started
    assert workflow_id in model1.get_active_workflows()
    
    # Update workflow
    await model1.update_workflow(
        workflow_id=workflow_id,
        new_stage="processing",
        message="Processing workflow"
    )
    
    # Verify workflow updated
    workflow = model1.get_active_workflows()[workflow_id]
    assert workflow.current_stage == "processing"

@pytest.mark.asyncio
async def test_message_context(model1, model2, context):
    """Test context handling in messages"""
    # Bind models
    model1.bind_to(model2)
    model2.bind_to(model1)
    
    # Send message with context
    message = await model1.send_message(
        receiver=model2,
        content="Test with context",
        context=context,
        requires_response=True
    )
    
    # Verify context preserved
    assert message.context == context
    assert message.context.interaction_type == InteractionType.TASK
    assert message.context.complexity == ComplexityLevel.MODERATE
    assert "test_tool" in message.context.tools_required

@pytest.mark.asyncio
async def test_pending_messages(model1, model2, context):
    """Test pending message management"""
    # Bind models
    model1.bind_to(model2)
    model2.bind_to(model1)
    
    # Send messages requiring response
    await model1.send_message(
        receiver=model2,
        content="Message 1",
        requires_response=True,
        context=context
    )
    
    await model1.send_message(
        receiver=model2,
        content="Message 2",
        requires_response=True,
        context=context
    )
    
    # Check pending messages
    pending = model2.get_pending_messages()
    assert len(pending) == 2
    assert pending[0].content == "Message 1"
    assert pending[1].content == "Message 2"

@pytest.mark.asyncio
async def test_invalid_communication(model1, model2):
    """Test error handling for invalid communication"""
    # Don't bind models
    with pytest.raises(ValueError):
        await model1.send_message(
            receiver=model2,
            content="Should fail"
        )

@pytest.mark.asyncio
async def test_workflow_validation(model1, model2, context):
    """Test workflow validation"""
    # Don't bind models
    with pytest.raises(ValueError):
        await model1.start_workflow(
            participants=[model2],
            initial_message="Should fail",
            context=context
        )

@pytest.mark.asyncio
async def test_tool_validation(model1, model2, context):
    """Test tool request validation"""
    # Bind models but don't add tool
    model1.bind_to(model2)
    model2.bind_to(model1)
    
    result = await model1.request_tool(
        receiver=model2,
        tool_name="nonexistent_tool",
        tool_input="test",
        context=context
    )
    
    assert result is None

@pytest.mark.asyncio
async def test_multi_model_workflow(model1, model2, communication, context):
    """Test complex workflow with multiple models"""
    # Create third model
    model3 = MockModel("model3", "test")
    model3.set_communication(communication)
    
    # Bind all models
    model1.bind_to(model2)
    model1.bind_to(model3)
    model2.bind_to(model1)
    model2.bind_to(model3)
    model3.bind_to(model1)
    model3.bind_to(model2)
    
    # Start workflow with all models
    workflow_id = await model1.start_workflow(
        participants=[model2, model3],
        initial_message="Multi-model workflow",
        context=context
    )
    
    # Verify all models are in workflow
    workflow = model1.get_active_workflows()[workflow_id]
    assert len(workflow.participants) == 3
    assert "model1" in workflow.participants
    assert "model2" in workflow.participants
    assert "model3" in workflow.participants
    
    # Update workflow from different models
    await model1.update_workflow(
        workflow_id=workflow_id,
        new_stage="stage1",
        message="Stage 1"
    )
    
    await model2.update_workflow(
        workflow_id=workflow_id,
        new_stage="stage2",
        message="Stage 2"
    )
    
    await model3.update_workflow(
        workflow_id=workflow_id,
        new_stage="stage3",
        message="Stage 3"
    )
    
    # Verify final state
    final_state = model1.get_active_workflows()[workflow_id]
    assert final_state.current_stage == "stage3"
