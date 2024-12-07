# src/glue/expressions/chain.py

"""Chain operations for GLUE Expression Language"""

from typing import Any, Dict, List, Union, Callable
from functools import partial

class Chain:
    """Chain operator for sequential operations with minimal syntax"""
    
    def __init__(self, value: Any = None):
        self.value = value
        self.operations = []
    
    def __rshift__(self, other: Any) -> 'Chain':
        """Enable >> operator for chaining"""
        if isinstance(other, Chain):
            return self._chain_with_chain(other)
        return Chain(self)._add_operation(other)
    
    def __rrshift__(self, other: Any) -> 'Chain':
        """Enable chaining from the left"""
        if isinstance(other, (Callable, Chain)):
            self.value = other
            return self
        return Chain(other)
    
    def _add_operation(self, op: Any) -> 'Chain':
        """Add operation to chain"""
        if isinstance(op, dict):
            if op.get("__magnet__"):
                # Handle direct magnetic tool: model >> tool
                self.operations.append(("sequence", op))
            else:
                # Handle tool attraction: model >> {"memory": memory}
                self.operations.append(("attract", op))
        elif isinstance(op, (list, tuple)):
            # Handle parallel operations: model >> [branch_a, branch_b]
            self.operations.append(("parallel", op))
        else:
            # Handle sequential operation: model >> next_model
            self.operations.append(("sequence", op))
        return self
    
    def _chain_with_chain(self, other: 'Chain') -> 'Chain':
        """Combine two chains"""
        result = Chain(self.value)
        result.operations = self.operations + other.operations
        return result
    
    async def __call__(self, *args, **kwargs):
        """Make chain callable for execution"""
        result = self.value
        if isinstance(result, Chain):
            result = await result(*args, **kwargs)
        elif callable(result):
            result = await result(*args, **kwargs)
        
        for op_type, op in self.operations:
            if op_type == "attract":
                # Handle tool attraction
                for tool_name, tool in op.items():
                    if isinstance(tool, dict) and tool.get("__magnet__"):
                        # Pass through magnetic tool config
                        result = tool
                    else:
                        result = await self._attract(result, tool_name, tool)
            elif op_type == "parallel":
                # Handle parallel operations
                result = await self._parallel(result, op)
            else:
                # Handle sequential operation
                if isinstance(op, Chain):
                    result = await op(result)
                elif callable(op):
                    result = await op(result)
                elif isinstance(op, dict) and op.get("__magnet__"):
                    # Pass through magnetic tool config
                    result = op
                else:
                    result = op
        
        return result
    
    async def _attract(self, value: Any, tool_name: str, tool: Any) -> Any:
        """Handle tool attraction with minimal syntax"""
        if isinstance(tool, dict) and tool.get("__magnet__"):
            # Pass through magnetic tool config
            return tool
        elif hasattr(tool, "__magnet__"):
            # Magnetic tool attraction
            return await tool(value)
        return tool
    
    async def _parallel(self, value: Any, operations: List[Any]) -> List[Any]:
        """Handle parallel operations with minimal syntax"""
        results = []
        for op in operations:
            if isinstance(op, Chain):
                result = await op(value)
            elif callable(op):
                result = await op(value)
            elif isinstance(op, dict) and op.get("__magnet__"):
                # Pass through magnetic tool config
                result = op
            else:
                result = op
            results.append(result)
        return results
    
    def __str__(self) -> str:
        """Clean string representation"""
        return f"Chain({self.value} >> {len(self.operations)} ops)"
