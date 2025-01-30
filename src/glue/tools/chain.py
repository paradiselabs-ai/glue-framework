"""GLUE Tool Chain Optimization System"""

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import asyncio
from ..core.context import ContextState, ComplexityLevel

@dataclass
class ToolUsage:
    """Records how a tool was used"""
    tool_name: str
    input_type: str
    output_type: str
    success: bool
    execution_time: float
    complexity: ComplexityLevel

@dataclass
class ChainPattern:
    """Represents a successful tool chain pattern"""
    tools: List[str]
    success_rate: float
    avg_execution_time: float
    complexities: Set[ComplexityLevel]
    usage_count: int = 0

class ToolChainOptimizer:
    """
    Optimizes tool chains based on usage patterns and success rates.
    
    Features:
    - Learns successful tool combinations
    - Identifies redundant tool usage
    - Suggests optimal tool chains
    - Caches common patterns
    """
    
    def __init__(self):
        """Initialize the optimizer"""
        # Track individual tool usage
        self.tool_usage: Dict[str, List[ToolUsage]] = defaultdict(list)
        
        # Track successful chains
        self.chain_patterns: Dict[str, ChainPattern] = {}
        
        # Cache for quick lookups
        self.context_cache: Dict[str, List[str]] = {}
        
        # Complementary tools (work well together)
        self.complementary: Dict[str, Set[str]] = defaultdict(set)
        
        # Redundant tools (provide similar results)
        self.redundant: Dict[str, Set[str]] = defaultdict(set)
    
    def record_usage(
        self,
        tool_name: str,
        input_type: str,
        output_type: str,
        success: bool,
        execution_time: float,
        context: ContextState
    ) -> None:
        """Record a tool's usage"""
        usage = ToolUsage(
            tool_name=tool_name,
            input_type=input_type,
            output_type=output_type,
            success=success,
            execution_time=execution_time,
            complexity=context.complexity
        )
        
        self.tool_usage[tool_name].append(usage)
        
        # Update cache invalidation
        self._invalidate_caches(tool_name, context)
    
    def record_chain(
        self,
        tools: List[str],
        success: bool,
        execution_time: float,
        context: ContextState
    ) -> None:
        """Record a tool chain's usage"""
        chain_key = ">".join(tools)
        
        if chain_key in self.chain_patterns:
            pattern = self.chain_patterns[chain_key]
            # Update statistics
            pattern.usage_count += 1
            pattern.success_rate = (
                (pattern.success_rate * (pattern.usage_count - 1) + (1.0 if success else 0.0))
                / pattern.usage_count
            )
            pattern.avg_execution_time = (
                (pattern.avg_execution_time * (pattern.usage_count - 1) + execution_time)
                / pattern.usage_count
            )
            pattern.complexities.add(context.complexity)
        else:
            # Create new pattern
            self.chain_patterns[chain_key] = ChainPattern(
                tools=tools,
                success_rate=1.0 if success else 0.0,
                avg_execution_time=execution_time,
                complexities={context.complexity},
                usage_count=1
            )
        
        # Update complementary tools
        if success:
            for i, tool1 in enumerate(tools[:-1]):
                for tool2 in tools[i+1:]:
                    self.complementary[tool1].add(tool2)
                    self.complementary[tool2].add(tool1)
    
    def optimize_chain(
        self,
        proposed_tools: List[str],
        context: ContextState
    ) -> List[str]:
        """
        Optimize a proposed tool chain
        
        Args:
            proposed_tools: List of tools to potentially use
            context: Current conversation context
            
        Returns:
            Optimized list of tools to use
        """
        # Check cache first
        cache_key = (
            f"{'>'.join(proposed_tools)}:"
            f"{context.complexity.name}"
        )
        if cache_key in self.context_cache:
            return self.context_cache[cache_key]
        
        # Start with proposed tools
        optimized = proposed_tools.copy()
        
        # Remove redundant tools
        optimized = self._remove_redundant(optimized)
        
        # Add complementary tools if beneficial
        optimized = self._add_complementary(optimized, context)
        
        # Sort by historical success rate
        optimized = self._sort_by_success(optimized, context)
        
        # Cache result
        self.context_cache[cache_key] = optimized
        
        return optimized
    
    def _remove_redundant(self, tools: List[str]) -> List[str]:
        """Remove redundant tools from chain"""
        result = []
        for tool in tools:
            # Only add if not redundant with already included tools
            if not any(
                other in self.redundant[tool]
                for other in result
            ):
                result.append(tool)
        return result
    
    def _add_complementary(
        self,
        tools: List[str],
        context: ContextState
    ) -> List[str]:
        """Add beneficial complementary tools"""
        result = tools.copy()
        
        # Check each tool's complementary tools
        for tool in tools:
            for comp_tool in self.complementary[tool]:
                # Only add if:
                # 1. Not already in chain
                # 2. Has good success rate with this context
                # 3. Not redundant with existing tools
                if (comp_tool not in result and
                    self._check_tool_success(comp_tool, context) > 0.7 and
                    not any(other in self.redundant[comp_tool] for other in result)):
                    result.append(comp_tool)
        
        return result
    
    def _sort_by_success(
        self,
        tools: List[str],
        context: ContextState
    ) -> List[str]:
        """Sort tools by success rate in similar contexts"""
        return sorted(
            tools,
            key=lambda t: self._check_tool_success(t, context),
            reverse=True
        )
    
    def _check_tool_success(
        self,
        tool: str,
        context: ContextState
    ) -> float:
        """Check a tool's success rate in similar contexts"""
        if tool not in self.tool_usage:
            return 0.0
            
        relevant_usage = [
            usage for usage in self.tool_usage[tool]
            if usage.complexity == context.complexity
        ]
        
        if not relevant_usage:
            return 0.0
            
        return sum(1 for u in relevant_usage if u.success) / len(relevant_usage)
    
    def _invalidate_caches(self, tool: str, context: ContextState) -> None:
        """Invalidate relevant cache entries"""
        invalid_keys = set()
        for key in self.context_cache:
            if tool in key or str(context.complexity) in key:
                invalid_keys.add(key)
        
        for key in invalid_keys:
            del self.context_cache[key]
    
    def mark_redundant(self, tool1: str, tool2: str) -> None:
        """Mark two tools as redundant"""
        self.redundant[tool1].add(tool2)
        self.redundant[tool2].add(tool1)
    
    def clear_redundant(self, tool: str) -> None:
        """Clear redundant markings for a tool"""
        self.redundant[tool].clear()
        for other_redundant in self.redundant.values():
            other_redundant.discard(tool)
    
    def get_tool_stats(self, tool: str) -> Dict[str, Any]:
        """Get usage statistics for a tool"""
        if tool not in self.tool_usage:
            return {}
            
        usage = self.tool_usage[tool]
        total = len(usage)
        successful = sum(1 for u in usage if u.success)
        
        return {
            "total_uses": total,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_execution_time": sum(u.execution_time for u in usage) / total if total > 0 else 0.0,
            "complexities": {u.complexity for u in usage},
            "complementary_tools": list(self.complementary[tool]),
            "redundant_tools": list(self.redundant[tool])
        }
    
    def get_chain_stats(self, tools: List[str]) -> Optional[Dict[str, Any]]:
        """Get statistics for a tool chain"""
        chain_key = ">".join(tools)
        if chain_key not in self.chain_patterns:
            return None
            
        pattern = self.chain_patterns[chain_key]
        return {
            "success_rate": pattern.success_rate,
            "avg_execution_time": pattern.avg_execution_time,
            "usage_count": pattern.usage_count,
            "complexities": list(pattern.complexities)
        }
    
    def __str__(self) -> str:
        return (
            f"ToolChainOptimizer("
            f"tools={len(self.tool_usage)}, "
            f"patterns={len(self.chain_patterns)}, "
            f"cached={len(self.context_cache)})"
        )
