# src/glue/core/context.py

"""GLUE Context Analysis System"""

import re
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
from enum import Enum, auto

class InteractionType(Enum):
    """Types of user interactions"""
    CHAT = auto()          # Simple conversation
    RESEARCH = auto()      # Information gathering
    TASK = auto()          # Specific task execution
    PULL = auto()          # One-way data flow
    UNKNOWN = auto()       # Fallback type

class ComplexityLevel(Enum):
    """Task complexity levels"""
    SIMPLE = 1        # Single-step, straightforward
    MODERATE = 2      # Multi-step, clear path
    COMPLEX = 3       # Multi-step, unclear path
    UNKNOWN = 0       # Fallback level

    def __lt__(self, other):
        if not isinstance(other, ComplexityLevel):
            return NotImplemented
        return self.value < other.value

    def __gt__(self, other):
        if not isinstance(other, ComplexityLevel):
            return NotImplemented
        return self.value > other.value

    def __le__(self, other):
        if not isinstance(other, ComplexityLevel):
            return NotImplemented
        return self.value <= other.value

    def __ge__(self, other):
        if not isinstance(other, ComplexityLevel):
            return NotImplemented
        return self.value >= other.value

@dataclass
class ContextState:
    """Represents the current context state"""
    interaction_type: InteractionType
    complexity: ComplexityLevel
    tools_required: Set[str]
    requires_research: bool
    requires_memory: bool
    requires_persistence: bool
    confidence: float  # 0.0 to 1.0

class ContextAnalyzer:
    """Analyzes user input to determine context and requirements"""
    
    # Patterns indicating research needs (expanded)
    RESEARCH_PATTERNS = {
        # Direct research indicators
        r"(?i)research": 0.8,
        r"(?i)find (?:information|details|data) (?:about|on|for)": 0.8,
        r"(?i)look up": 0.7,
        r"(?i)search for": 0.7,
        
        # Indirect research indicators
        r"(?i)tell me about": 0.6,
        r"(?i)what (?:is|are|was|were)": 0.6,
        r"(?i)how (?:does|do|did)": 0.6,
        
        # Topic exploration indicators
        r"(?i)learn about": 0.7,
        r"(?i)explain": 0.6,
        r"(?i)describe": 0.6,
        
        # Information gathering indicators
        r"(?i)gather": 0.7,
        r"(?i)collect": 0.7,
        r"(?i)compile": 0.7,
        
        # Analysis indicators
        r"(?i)analyze": 0.7,
        r"(?i)investigate": 0.7,
        r"(?i)study": 0.7
    }
    
    # Patterns indicating task execution
    TASK_PATTERNS = {
        r"(?i)create(?: a)?": 0.8,
        r"(?i)generate": 0.8,
        r"(?i)make(?: a)?": 0.7,
        r"(?i)build": 0.7,
        r"(?i)execute": 0.8,
        r"(?i)run": 0.7,
        r"(?i)analyze": 0.7,
        r"(?i)save": 0.8,
        r"(?i)write": 0.8
    }
    
    # Patterns indicating chat (reduced priority)
    CHAT_PATTERNS = {
        r"(?i)^(?:hi|hello|hey)(?:\s|$)": 0.9,
        r"(?i)^(?:thanks|thank you)": 0.9,
        r"(?i)how are you": 0.9,
        r"(?i)nice to": 0.8,
        r"(?i)good (?:morning|afternoon|evening)": 0.9
    }
    
    # Tool requirement patterns (expanded)
    TOOL_PATTERNS = {
        "web_search": [
            # Direct search indicators
            r"(?i)search",
            r"(?i)look up",
            r"(?i)find (?:information|details|data)",
            r"(?i)research",
            
            # Information requests
            r"(?i)tell me about",
            r"(?i)what (?:is|are|was|were)",
            r"(?i)how (?:does|do|did)",
            
            # Topic exploration
            r"(?i)learn about",
            r"(?i)explain",
            r"(?i)describe",
            
            # Analysis requests
            r"(?i)analyze",
            r"(?i)investigate",
            r"(?i)study"
        ],
        "file_handler": [
            # Direct file operations
            r"(?i)save",
            r"(?i)create (?:a )?(?:file|document)",
            r"(?i)write (?:to|a) (?:file|document)",
            r"(?i)store",
            
            # Content management
            r"(?i)organize",
            r"(?i)compile",
            r"(?i)document",
            
            # File requests
            r"(?i)make a (?:file|document)",
            r"(?i)generate a (?:file|document)"
        ],
        "code_interpreter": [
            r"(?i)run",
            r"(?i)execute",
            r"(?i)analyze code",
            r"(?i)debug"
        ]
    }
    
    def __init__(self):
        """Initialize the context analyzer"""
        self.interaction_history: List[ContextState] = []
    
    def analyze(self, input_text: str, available_tools: Optional[List[str]] = None) -> ContextState:
        """
        Analyze input text to determine context and requirements
        
        Args:
            input_text: The user's input text
            available_tools: List of available tool names
            
        Returns:
            ContextState object representing the analysis results
        """
        # First check for research requirements
        requires_research = self._requires_research(input_text)
        
        # Determine interaction type and confidence
        interaction_type, confidence = self._determine_type(input_text, requires_research)
        
        # Determine complexity
        complexity = self._assess_complexity(input_text)
        
        # Initialize requirements
        tools_required = set()
        requires_memory = False
        requires_persistence = False
        
        # Only analyze tool requirements if not a chat interaction
        if interaction_type != InteractionType.CHAT:
            # Identify required tools based on both patterns and context
            tools_required = self._identify_tools(input_text, available_tools, requires_research)
            
            # Analyze additional requirements
            requires_memory = self._requires_memory(input_text)
            requires_persistence = self._requires_persistence(input_text)
            
            # Adjust for research context
            if requires_research:
                # Ensure research tools are included
                if available_tools and "web_search" in available_tools:
                    tools_required.add("web_search")
                # Increase complexity for research tasks
                if complexity == ComplexityLevel.SIMPLE:
                    complexity = ComplexityLevel.MODERATE
        
        # Create context state
        state = ContextState(
            interaction_type=interaction_type,
            complexity=complexity,
            tools_required=tools_required,
            requires_research=requires_research,
            requires_memory=requires_memory,
            requires_persistence=requires_persistence,
            confidence=confidence
        )
        
        # Update history
        self.interaction_history.append(state)
        
        return state
    
    def _determine_type(self, text: str, requires_research: bool) -> tuple[InteractionType, float]:
        """Determine the type of interaction and confidence level"""
        # Simple greeting check (only obvious greetings)
        if re.match(r"^(?:hi|hello|hey|thanks?|thank you)(?:\s.*)?$", text, re.I):
            return InteractionType.CHAT, 0.9
            
        # Information seeking check
        if any(word in text.lower() for word in [
            "what", "how", "why", "when", "where", "who",
            "find", "search", "look up", "tell me about"
        ]):
            return InteractionType.RESEARCH, 0.8
            
        # Task execution check
        if any(word in text.lower() for word in [
            "write", "create", "make", "generate", "run", "execute"
        ]):
            return InteractionType.TASK, 0.8
            
        # Default to research for any other question-like input
        if "?" in text or requires_research:
            return InteractionType.RESEARCH, 0.7
            
        # Default to unknown for anything else
        return InteractionType.UNKNOWN, 0.3
    
    def _assess_complexity(self, text: str) -> ComplexityLevel:
        """Assess the complexity of the interaction"""
        # Count potential steps/requirements
        steps = len(re.findall(r"(?i)(?:and|then|after|next|finally)", text))
        
        # Count question words (indicating information needs)
        questions = len(re.findall(r"(?i)(?:what|why|how|where|when|who)", text))
        
        # Analyze sentence structure
        sentences = len(re.findall(r"[.!?]+", text)) + 1
        words = len(text.split())
        avg_sentence_length = words / sentences
        
        if steps > 2 or questions > 2 or avg_sentence_length > 20:
            return ComplexityLevel.COMPLEX
        elif steps > 0 or questions > 0 or avg_sentence_length > 15:
            return ComplexityLevel.MODERATE
        return ComplexityLevel.SIMPLE
    
    def _identify_tools(
        self, 
        text: str, 
        available_tools: Optional[List[str]] = None,
        requires_research: bool = False
    ) -> Set[str]:
        """Identify required tools based on input text and context"""
        required_tools = set()
        text_lower = text.lower()
        
        # Only process available tools
        if not available_tools:
            return required_tools
            
        # Research/Information tools
        if "web_search" in available_tools:
            # Add web_search for any information seeking or research intent
            if requires_research or any(word in text_lower for word in [
                "what", "how", "why", "when", "where", "who",
                "find", "search", "look up", "tell me about"
            ]):
                required_tools.add("web_search")
        
        # Code execution tools
        if "code_interpreter" in available_tools:
            # Add code_interpreter for any code or execution intent
            if any(word in text_lower for word in [
                "code", "script", "program",
                "run", "execute", "debug"
            ]):
                required_tools.add("code_interpreter")
        
        # File handling tools
        if "file_handler" in available_tools:
            # Add file_handler for any file operation intent
            if any(word in text_lower for word in [
                "file", "document", "save",
                "write", "read", "store"
            ]):
                required_tools.add("file_handler")
        
        return required_tools
    
    def _requires_research(self, text: str) -> bool:
        """Determine if the interaction requires research or information gathering"""
        text_lower = text.lower()
        
        # Check for question words
        if any(word in text_lower for word in [
            "what", "how", "why", "when", "where", "who"
        ]):
            return True
            
        # Check for research/information verbs
        if any(word in text_lower for word in [
            "find", "search", "look up", "research",
            "learn", "explain", "tell me about"
        ]):
            return True
            
        # Check for question mark
        if "?" in text:
            return True
            
        return False
    
    def _requires_memory(self, text: str) -> bool:
        """Determine if the interaction requires memory of past interactions"""
        memory_patterns = [
            r"(?i)(?:like|as) (?:before|previously|last time)",
            r"(?i)(?:again|repeat)",
            r"(?i)(?:remember|recall)",
            r"(?i)(?:you|we) (?:mentioned|discussed|talked about)"
        ]
        return any(re.search(pattern, text) for pattern in memory_patterns)
    
    def _requires_persistence(self, text: str) -> bool:
        """Determine if the interaction requires persistent storage"""
        persistence_patterns = [
            r"(?i)save",
            r"(?i)store",
            r"(?i)keep",
            r"(?i)remember this",
            r"(?i)create a (?:file|document)",
            r"(?i)write (?:to|a) (?:file|document)"
        ]
        return any(re.search(pattern, text) for pattern in persistence_patterns)
    
    def get_recent_context(self, n: int = 5) -> List[ContextState]:
        """Get the n most recent context states"""
        return self.interaction_history[-n:]
    
    def clear_history(self) -> None:
        """Clear the interaction history"""
        self.interaction_history.clear()
