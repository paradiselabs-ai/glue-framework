"""GLUE Context Analysis System

This system analyzes user input to provide helpful context to models, but does not
restrict or control model behavior. Models remain free to:
1. Communicate and collaborate as they choose
2. Share tools according to adhesive bindings
3. Delegate tasks based on complexity
4. Make their own decisions about persistence

The analysis helps models understand tasks better by providing:
- Complexity assessment (SIMPLE, MODERATE, COMPLEX)
- Tool suggestions based on task requirements
- Persistence recommendations for data/results
- Memory requirements for context history
"""

import re
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
from enum import Enum, auto

class ComplexityLevel(Enum):
    """Task complexity levels (suggestions only)"""
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
    """
    Represents the current context state.
    Note: These are suggestions to help models, not restrictions.
    """
    complexity: ComplexityLevel
    tools_required: Set[str]
    requires_persistence: bool  # Whether results should persist (GLUE/VELCRO vs TAPE)
    requires_memory: bool      # Whether context history is needed
    confidence: float          # 0.0 to 1.0
    magnetic_flow: Optional[str] = None  # Suggested magnetic operator if needed

class ContextAnalyzer:
    """Analyzes user input to provide helpful context to models"""
    
    # Tool requirement patterns
    TOOL_PATTERNS = {
        "web_search": [
            r"(?i)search|look up|find",  # Direct search
            r"(?i)research|investigate|study",  # Research
            r"(?i)what|how|why|when|where|who",  # Questions
            r"(?i)tell me about|explain|describe"  # Information requests
        ],
        "file_handler": [
            r"(?i)save|store|keep",  # Storage
            r"(?i)create|make|generate|write",  # Creation
            r"(?i)organize|compile|document"  # Organization
        ],
        "code_interpreter": [
            r"(?i)run|execute",  # Execution
            r"(?i)analyze code|debug"  # Code analysis
        ]
    }
    
    # Persistence requirement patterns
    PERSISTENCE_PATTERNS = [
        r"(?i)save|store|keep",  # Direct storage
        r"(?i)remember|recall",  # Memory
        r"(?i)build (?:on|upon)|continue|update"  # Continuation
    ]
    
    def __init__(self):
        """Initialize the context analyzer"""
        self.interaction_history: List[ContextState] = []
    
    def analyze(self, input_text: str, available_tools: Optional[List[str]] = None) -> ContextState:
        """Analyze input text to provide helpful context"""
        # Determine complexity
        complexity = self._assess_complexity(input_text)
        
        # Initialize requirements
        tools_required = set()
        requires_persistence = False
        requires_memory = False
        magnetic_flow = None
        
        # Identify required tools
        if available_tools:
            tools_required = self._identify_tools(input_text, available_tools)
            
        # Analyze persistence needs
        requires_persistence = self._requires_persistence(input_text)
            
        # Analyze memory needs
        requires_memory = self._requires_memory(input_text)
        
        # Determine confidence
        confidence = self._calculate_confidence(
            input_text,
            tools_required,
            requires_persistence,
            complexity
        )
        
        # Create context state
        state = ContextState(
            complexity=complexity,
            tools_required=tools_required,
            requires_persistence=requires_persistence,
            requires_memory=requires_memory,
            confidence=confidence,
            magnetic_flow=magnetic_flow
        )
        
        # Update history
        self.interaction_history.append(state)
        
        return state
    
    def _assess_complexity(self, text: str) -> ComplexityLevel:
        """
        Assess the task's structural complexity based on:
        1. Number of steps/operations required
        2. Information-seeking requirements
        3. Linguistic complexity
        
        This helps models understand if a task is:
        - SIMPLE: One-shot operation ("search for X")
        - MODERATE: Clear sequence ("search for X then save it")
        - COMPLEX: Multiple steps or unclear path
        
        Note: This is just to help models understand the task.
        They remain free to collaborate regardless of complexity.
        """
        # Count potential steps/requirements
        steps = len(re.findall(r"(?i)(?:and|then|after|next|finally)", text))
        
        # Count question words (indicating information needs)
        questions = len(re.findall(r"(?i)(?:what|why|how|where|when|who)", text))
        
        # Analyze sentence structure
        sentences = len(re.findall(r"[.!?]+", text)) + 1
        words = len(text.split())
        avg_sentence_length = words / sentences
        
        # Check for complexity indicators
        complexity_indicators = len(re.findall(
            r"(?i)(?:complex|difficult|challenging|advanced|sophisticated)",
            text
        ))
        
        if (steps > 2 or questions > 2 or 
            avg_sentence_length > 20 or 
            complexity_indicators > 0):
            return ComplexityLevel.COMPLEX
        elif steps > 0 or questions > 0 or avg_sentence_length > 15:
            return ComplexityLevel.MODERATE
        return ComplexityLevel.SIMPLE
    
    def _identify_tools(
        self, 
        text: str, 
        available_tools: List[str]
    ) -> Set[str]:
        """
        Suggest tools that might be helpful based on input text.
        Models can use other tools if they choose.
        """
        required_tools = set()
        text_lower = text.lower()
        
        # Check each available tool
        for tool_name in available_tools:
            if tool_name in self.TOOL_PATTERNS:
                # Check tool's patterns
                for pattern in self.TOOL_PATTERNS[tool_name]:
                    if re.search(pattern, text):
                        required_tools.add(tool_name)
                        break
        
        return required_tools
    
    def _requires_memory(self, text: str) -> bool:
        """Suggest whether context history might be helpful"""
        memory_patterns = [
            r"(?i)(?:like|as) (?:before|previously|last time)",
            r"(?i)(?:again|repeat)",
            r"(?i)(?:remember|recall)",
            r"(?i)(?:you|we) (?:mentioned|discussed|talked about)"
        ]
        return any(re.search(pattern, text) for pattern in memory_patterns)
    
    def _requires_persistence(self, text: str) -> bool:
        """Suggest whether results should persist"""
        return any(re.search(pattern, text) for pattern in self.PERSISTENCE_PATTERNS)
    
    def _calculate_confidence(
        self,
        text: str,
        tools_required: Set[str],
        requires_persistence: bool,
        complexity: ComplexityLevel
    ) -> float:
        """Calculate confidence in the suggestions"""
        confidence = 0.5  # Base confidence
        
        # Tool requirement confidence
        if tools_required:
            confidence += 0.2
            
        # Persistence confidence
        if requires_persistence:
            confidence += 0.1
            
        # Complexity confidence
        if complexity != ComplexityLevel.UNKNOWN:
            confidence += 0.2
            
        return min(confidence, 1.0)
    
    def get_recent_context(self, n: int = 5) -> List[ContextState]:
        """Get the n most recent context states"""
        return self.interaction_history[-n:]
    
    def clear_history(self) -> None:
        """Clear the interaction history"""
        self.interaction_history.clear()
