# src/glue/adhesive/chain.py

"""Chain operations using double-sided tape"""

from typing import Any, List, Dict, Union, Callable, Tuple
from functools import partial

class ChainOp:
    """Chain operation wrapper"""
    def __init__(self, func: Callable):
        self.func = func
    
    async def __call__(self, *args, **kwargs):
        return await self.func(*args, **kwargs)
    
    def __rshift__(self, other: Any) -> tuple:
        """Support >> operator"""
        return (self.func, other)

class Chain:
    """Chain of sequential operations using double-sided tape"""
    
    def __init__(self):
        self.operations = []
        self.error_handlers = []
    
    def add_operation(self, op: Any) -> 'Chain':
        """Add operation to chain"""
        if isinstance(op, tuple):
            # Handle >> operator results
            if len(op) == 2:
                left, right = op
                if isinstance(right, dict):
                    # Handle attraction: tool >> {"memory": memory}
                    self.operations.append(("stick_to", left, right))
                else:
                    # Handle sequence: tool1 >> tool2
                    self.operations.append(("sequence", left, right))
        elif callable(op):
            # Handle single function
            self.operations.append(("stick", op))
        else:
            # Handle direct operation
            self.operations.append(("stick", op))
        return self
    
    def add_error_handler(self, handler: Callable) -> 'Chain':
        """Add error handler using duct tape"""
        if isinstance(handler, ChainOp):
            handler = handler.func
        self.error_handlers.append(handler)
        return self
    
    async def _execute_operation(self, op: Any, result: Any) -> Tuple[Any, bool]:
        """Execute a single operation with error handling"""
        try:
            if isinstance(op, tuple):
                # Handle nested chain operations
                chain = Chain()
                chain.add_operation(op)
                return await chain(result), False
            elif hasattr(op, "execute"):
                # Handle tool execution
                return await op.execute(result), False
            elif callable(op):
                # Handle function execution
                if isinstance(op, ChainOp):
                    op = op.func
                return await op(result), False
            else:
                return op, False
        except Exception as e:
            # Try error handlers
            for handler in self.error_handlers:
                try:
                    return await handler(e, result), True
                except:
                    continue
            raise  # Re-raise if no handler succeeded
    
    async def process(self, input_data: Any) -> Any:
        """Process input through chain"""
        result = input_data
        
        for op in self.operations:
            try:
                if op[0] == "stick":
                    # Handle single operation
                    result, handled = await self._execute_operation(op[1], result)
                    if handled:
                        return result
                        
                elif op[0] == "sequence":
                    # Handle sequential operations
                    left, right = op[1:]
                    result, handled = await self._execute_operation(left, result)
                    if handled:
                        return result
                    result, handled = await self._execute_operation(right, result)
                    if handled:
                        return result
                        
                elif op[0] == "stick_to":
                    # Handle tool attraction
                    tool, targets = op[1:]
                    result, handled = await self._execute_operation(tool, result)
                    if handled:
                        return result
                    
                    for target_name, target in targets.items():
                        result, handled = await self._execute_operation(target, result)
                        if handled:
                            return result
            except Exception as e:
                # Try error handlers at chain level
                for handler in self.error_handlers:
                    try:
                        return await handler(e, result)
                    except:
                        continue
                raise  # Re-raise if no handler succeeded
        
        return result
    
    async def __call__(self, input_data: Any) -> Any:
        """Make chain callable"""
        return await self.process(input_data)
    
    def __rshift__(self, other: Any) -> 'Chain':
        """Support >> operator for chaining"""
        if callable(other) and not hasattr(other, "__rshift__"):
            other = ChainOp(other)
        return self.add_operation((self, other))
    
    def __str__(self) -> str:
        """String representation"""
        return f"Chain({len(self.operations)} operations)"
