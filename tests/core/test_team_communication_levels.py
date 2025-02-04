"""Test both intra-team and inter-team communication in GLUE"""

import pytest
from glue.providers.smolagents import SmolAgentsProvider
from glue.core.types import AdhesiveType
from glue.core.team import Team
from glue.magnetic.field import MagneticField
from glue.core.group_chat import GroupChatManager

@pytest.mark.asyncio
async def test_intra_team_communication():
    """Test model-to-model communication within a team"""
    # Create research team
    research_team = Team(name="research_team")
    
    # Create group chat manager for intra-team communication
    chat_manager = GroupChatManager(name="research_chat")
    
    # Create team members with different roles
    researcher = SmolAgentsProvider(
        name="researcher",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        api_key="test-key"
    )
    
    assistant = SmolAgentsProvider(
        name="assistant",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE, AdhesiveType.VELCRO},
        api_key="test-key"
    )
    
    # Add models to chat system
    chat_manager.add_model(researcher)
    chat_manager.add_model(assistant)
    
    # Create dynamic tools for collaboration
    async def collect_data(topic: str) -> str:
        return f"Research data about {topic}"
        
    async def analyze_data(data: str) -> str:
        return f"Analysis of '{data}'"
    
    # Create and bind tools
    research_tool = await researcher.create_tool(
        name="data_collector",
        description="Collect research data",
        function=collect_data
    )
    
    analysis_tool = await assistant.create_tool(
        name="data_analyzer",
        description="Analyze research data",
        function=analyze_data
    )
    
    await chat_manager.add_tool(research_tool)
    await chat_manager.add_tool(analysis_tool)
    
    # Bind tools with GLUE for team sharing
    await chat_manager.bind_tool("researcher", "data_collector", AdhesiveType.GLUE)
    await chat_manager.bind_tool("assistant", "data_analyzer", AdhesiveType.GLUE)
    
    # Start chat between team members
    chat_id = await chat_manager.start_chat("researcher", "assistant")
    
    # Test collaborative workflow
    # 1. Researcher collects data
    research_msg = "Let's research quantum computing"
    research_response = await chat_manager.process_message(
        chat_id=chat_id,
        content=research_msg,
        from_model="researcher"
    )
    assert "Research data" in research_response
    
    # 2. Assistant analyzes the data
    analysis_msg = f"I'll analyze that: {research_response}"
    analysis_response = await chat_manager.process_message(
        chat_id=chat_id,
        content=analysis_msg,
        from_model="assistant"
    )
    assert "Analysis of" in analysis_response
    
    # Verify chat history maintains context
    active_chats = chat_manager.get_active_chats()
    assert chat_id in active_chats
    assert "researcher" in active_chats[chat_id].models
    assert "assistant" in active_chats[chat_id].models

@pytest.mark.asyncio
async def test_multi_level_communication():
    """Test both intra-team and inter-team communication"""
    # Create magnetic field for team-to-team communication
    field = MagneticField(name="research_flow")
    
    # Create teams
    research_team = Team(name="research_team")
    writing_team = Team(name="writing_team")
    
    # Create group chat managers for each team
    research_chat = GroupChatManager(name="research_chat")
    writing_chat = GroupChatManager(name="writing_chat")
    
    # Create team members
    researcher = SmolAgentsProvider(
        name="researcher",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    assistant = SmolAgentsProvider(
        name="assistant",
        team="research_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    writer = SmolAgentsProvider(
        name="writer",
        team="writing_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    editor = SmolAgentsProvider(
        name="editor",
        team="writing_team",
        available_adhesives={AdhesiveType.GLUE},
        api_key="test-key"
    )
    
    # Set up intra-team communication
    # Research team
    research_chat.add_model(researcher)
    research_chat.add_model(assistant)
    
    # Writing team
    writing_chat.add_model(writer)
    writing_chat.add_model(editor)
    
    # Create dynamic tools
    async def research_topic(topic: str) -> str:
        return f"Research findings on {topic}"
        
    async def analyze_data(data: str) -> str:
        return f"Analysis: {data}"
        
    async def write_doc(content: str) -> str:
        return f"Document draft:\n{content}"
        
    async def edit_doc(doc: str) -> str:
        return f"Edited document:\n{doc}"
    
    # Create and bind tools for research team
    research_tool = await researcher.create_tool(
        name="topic_research",
        description="Research topics",
        function=research_topic
    )
    
    analysis_tool = await assistant.create_tool(
        name="data_analysis",
        description="Analyze research data",
        function=analyze_data
    )
    
    await research_chat.add_tool(research_tool)
    await research_chat.add_tool(analysis_tool)
    await research_chat.bind_tool("researcher", "topic_research", AdhesiveType.GLUE)
    await research_chat.bind_tool("assistant", "data_analysis", AdhesiveType.GLUE)
    
    # Create and bind tools for writing team
    writing_tool = await writer.create_tool(
        name="doc_writer",
        description="Write documents",
        function=write_doc
    )
    
    editing_tool = await editor.create_tool(
        name="doc_editor",
        description="Edit documents",
        function=edit_doc
    )
    
    await writing_chat.add_tool(writing_tool)
    await writing_chat.add_tool(editing_tool)
    await writing_chat.bind_tool("writer", "doc_writer", AdhesiveType.GLUE)
    await writing_chat.bind_tool("editor", "doc_editor", AdhesiveType.GLUE)
    
    # Set up team-to-team magnetic flow
    await field.set_team_flow(
        source_team="research_team",
        target_team="writing_team",
        operator="->"  # Research pushes to writing
    )
    
    # Test multi-level communication
    # 1. Research team collaboration
    research_chat_id = await research_chat.start_chat("researcher", "assistant")
    
    # Researcher collects data
    research_msg = "Research quantum computing"
    research_response = await research_chat.process_message(
        chat_id=research_chat_id,
        content=research_msg,
        from_model="researcher"
    )
    
    # Assistant analyzes
    analysis_msg = f"Analyzing: {research_response}"
    analysis_response = await research_chat.process_message(
        chat_id=research_chat_id,
        content=analysis_msg,
        from_model="assistant"
    )
    
    # 2. Share with writing team through magnetic flow
    await field.share_team_results(
        source_team="research_team",
        target_team="writing_team",
        results={"research": analysis_response}
    )
    
    # 3. Writing team collaboration
    writing_chat_id = await writing_chat.start_chat("writer", "editor")
    
    # Writer creates draft
    writing_msg = f"Creating document from: {analysis_response}"
    writing_response = await writing_chat.process_message(
        chat_id=writing_chat_id,
        content=writing_msg,
        from_model="writer"
    )
    
    # Editor reviews
    editing_msg = f"Editing: {writing_response}"
    editing_response = await writing_chat.process_message(
        chat_id=writing_chat_id,
        content=editing_msg,
        from_model="editor"
    )
    
    # Verify intra-team communication
    assert "Research findings" in research_response
    assert "Analysis:" in analysis_response
    assert "Document draft" in writing_response
    assert "Edited document" in editing_response
    
    # Verify team-to-team flow
    flows = field.get_team_flows("research_team")
    assert "writing_team" in flows
    assert flows["writing_team"] == "->"
