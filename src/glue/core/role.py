"""GLUE Dynamic Role System"""

from enum import Enum, auto
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass
from .context import ContextState, ComplexityLevel

class RoleState(Enum):
    """States a role can be in"""
    ACTIVE = auto()      # Primary responder
    PASSIVE = auto()     # Supporting/observing
    TOOL_USER = auto()   # Actively using tools
    OBSERVER = auto()    # Monitoring only

@dataclass
class RoleContext:
    """Context information for role decisions"""
    state: RoleState
    tools_enabled: bool
    response_type: str
    confidence: float
    primary_role: bool

class DynamicRole:
    """
    Manages dynamic role adjustments based on context.
    
    This system helps models naturally switch between modes
    and determine appropriate tool usage based on task complexity.
    """
    
    def __init__(self, base_role: str):
        """Initialize with base role description"""
        self.base_role = base_role
        self.current_state = RoleState.PASSIVE
        self.tools_enabled = True
        self.response_type = "standard"
        self.context_history: List[RoleContext] = []
        
        # Role-specific tool permissions
        self.allowed_tools: Set[str] = set()
        self.required_tools: Set[str] = set()
        
        # Track successful patterns
        self.success_patterns: Dict[str, float] = {}
        
        # Flag for roles that should never interact directly with users
        self.no_direct_interaction = "You do not interact with the user" in base_role.lower()
    
    def adjust_for_context(self, context: ContextState) -> RoleContext:
        """
        Adjust role behavior based on current context
        
        Args:
            context: Current conversation context
            
        Returns:
            RoleContext with updated state information
        """
        # Determine if this role should be active
        should_be_active = self._should_be_active(context)
        
        # Determine if tools should be enabled
        tools_needed = self._needs_tools(context)
        
        # Determine response type
        response_type = self._determine_response_type(context)
        
        # Calculate confidence in this role configuration
        confidence = self._calculate_confidence(
            context, should_be_active, tools_needed
        )
        
        # Update current state
        if should_be_active:
            self.current_state = RoleState.ACTIVE
        elif tools_needed:
            self.current_state = RoleState.TOOL_USER
        else:
            self.current_state = RoleState.PASSIVE
        
        self.tools_enabled = tools_needed
        self.response_type = response_type
        
        # Create context
        role_context = RoleContext(
            state=self.current_state,
            tools_enabled=self.tools_enabled,
            response_type=self.response_type,
            confidence=confidence,
            primary_role=should_be_active
        )
        
        # Store for learning
        self.context_history.append(role_context)
        
        return role_context
    
    def _should_be_active(self, context: ContextState) -> bool:
        """Determine if this role should be active"""
        # Never activate roles that don't interact with users
        if self.no_direct_interaction:
            return False
            
        # For simple tasks, only activate if we have required tools
        if context.complexity == ComplexityLevel.SIMPLE:
            return bool(self.required_tools & context.tools_required)
            
        # For moderate tasks, activate if we have any relevant tools
        if context.complexity == ComplexityLevel.MODERATE:
            return bool(self.allowed_tools & context.tools_required)
            
        # For complex tasks, activate if we have any tools that could help
        return bool(self.allowed_tools)
    
    def _needs_tools(self, context: ContextState) -> bool:
        """Determine if tools should be enabled"""
        # Always enable required tools
        if self.required_tools & context.tools_required:
            return True
            
        # For simple tasks, only use required tools
        if context.complexity == ComplexityLevel.SIMPLE:
            return False
            
        # For moderate/complex tasks, enable allowed tools
        return bool(self.allowed_tools)
    
    def _determine_response_type(self, context: ContextState) -> str:
        """Determine appropriate response type"""
        if context.complexity == ComplexityLevel.SIMPLE:
            return "direct"
            
        if context.complexity == ComplexityLevel.MODERATE:
            return "analytical"
            
        return "procedural"
    
    def _calculate_confidence(
        self,
        context: ContextState,
        active: bool,
        tools_enabled: bool
    ) -> float:
        """Calculate confidence in role configuration"""
        confidence = 0.5  # Base confidence
        
        # Check if we've seen similar contexts
        pattern_key = f"{context.complexity.name}:{active}:{tools_enabled}"
        if pattern_key in self.success_patterns:
            confidence = max(confidence, self.success_patterns[pattern_key])
        
        # Adjust based on tool alignment
        if context.tools_required & self.required_tools:
            confidence += 0.2
        if context.tools_required & self.allowed_tools:
            confidence += 0.1
            
        # Adjust based on complexity
        if context.complexity == ComplexityLevel.SIMPLE and not tools_enabled:
            confidence += 0.1  # More confident in simple tasks without tools
        if context.complexity != ComplexityLevel.SIMPLE and tools_enabled:
            confidence += 0.1  # More confident using tools for complex tasks
            
        return min(confidence, 1.0)
    
    def record_success(
        self,
        context: ContextState,
        success: bool,
        feedback: Optional[str] = None
    ) -> None:
        """Record success/failure for learning"""
        if not self.context_history:
            return
            
        # Get the context we used
        last_context = self.context_history[-1]
        
        # Create pattern key
        pattern_key = (
            f"{context.complexity.name}:"
            f"{last_context.state == RoleState.ACTIVE}:"
            f"{last_context.tools_enabled}"
        )
        
        # Update success rate
        current_rate = self.success_patterns.get(pattern_key, 0.5)
        if success:
            # Increase confidence
            new_rate = current_rate + (1 - current_rate) * 0.1
        else:
            # Decrease confidence
            new_rate = current_rate * 0.9
            
        self.success_patterns[pattern_key] = new_rate
    
    def enhance_prompt(self, prompt: str, context: ContextState) -> str:
        """Enhance prompt based on current role state"""
        import re
        
        # Start with base role
        enhanced = f"{self.base_role}\n\n"
        
        # Add role guidance based on complexity
        if context.complexity != ComplexityLevel.SIMPLE:
            if self.current_state == RoleState.ACTIVE:
                enhanced += "You are the primary responder. "
            elif self.current_state == RoleState.TOOL_USER:
                enhanced += "You should use tools to accomplish tasks. "
            elif self.current_state == RoleState.PASSIVE:
                enhanced += "You are in a supporting role. "
            
            # Add tool guidance
            if self.tools_enabled:
                if self.required_tools:
                    enhanced += f"You must use these tools: {', '.join(self.required_tools)}. "
                if self.allowed_tools - self.required_tools:
                    enhanced += f"You may use these tools if needed: {', '.join(self.allowed_tools - self.required_tools)}. "
            else:
                enhanced += "Focus on direct interaction without using tools. "
            
            # Add response type guidance
            if self.response_type == "direct":
                enhanced += "Keep responses clear and concise. "
            elif self.response_type == "analytical":
                enhanced += "Provide detailed analytical responses. "
            elif self.response_type == "procedural":
                enhanced += "Focus on clear step-by-step instructions. "
        
        # Add the original prompt
        enhanced += f"\n\nPrompt: {prompt}"
        
        return enhanced
    
    def allow_tool(self, tool_name: str) -> None:
        """Allow use of a tool"""
        self.allowed_tools.add(tool_name)
    
    def require_tool(self, tool_name: str) -> None:
        """Require use of a tool"""
        self.required_tools.add(tool_name)
        self.allowed_tools.add(tool_name)
    
    def clear_tools(self) -> None:
        """Clear all tool permissions"""
        self.allowed_tools.clear()
        self.required_tools.clear()
    
    def __str__(self) -> str:
        return (
            f"DynamicRole(state={self.current_state.name}, "
            f"tools_enabled={self.tools_enabled}, "
            f"response_type={self.response_type})"
        )
