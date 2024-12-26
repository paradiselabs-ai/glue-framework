# src/glue/adhesive/chain.py

"""Chain operations using magnetic fields"""

from typing import Any, List, Dict, Union, Callable, Tuple, Optional
from functools import partial
from enum import Enum

from .import AdhesiveType

class ChainOp:
    """Chain operation wrapper"""
    def __init__(self, func: Callable[..., Any], adhesive: AdhesiveType = AdhesiveType.GLUE_ATTRACT):
        self.func = func
        self.adhesive = adhesive
    
    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return await self.func(*args, **kwargs)
    
    def __rshift__(self, other: Any) -> Tuple[Callable[..., Any], Any, AdhesiveType]:
        """Support >> operator for push flow"""
        return (self.func, other, AdhesiveType.GLUE_PUSH)
    
    def __lshift__(self, other: Any) -> Tuple[Callable[..., Any], Any, AdhesiveType]:
        """Support << operator for pull flow"""
        return (self.func, other, AdhesiveType.GLUE_PULL)
    
    def __xor__(self, other: Any) -> Tuple[Callable[..., Any], Any, AdhesiveType]:
        """Support ^ operator for bidirectional attraction"""
        return (self.func, other, AdhesiveType.GLUE_ATTRACT)
    
    def __invert__(self) -> 'ChainOp':
        """Support ~ operator for repulsion"""
        self.adhesive = AdhesiveType.GLUE_REPEL
        return self

class Chain:
    """Chain of magnetic operations"""
    
    def __init__(self):
        self.operations = []
        self.error_handlers = []
    
    def add_operation(self, op: Any) -> 'Chain':
        """Add operation to chain"""
        if isinstance(op, tuple):
            # Handle operator results
            if len(op) == 3:  # (func, target, adhesive)
                left, right, adhesive = op
                if isinstance(right, dict):
                    # Handle attraction with config: tool >> {"memory": memory}
                    self.operations.append(("magnetic", left, right, adhesive))
                else:
                    # Handle direct flow: tool1 >> tool2
                    self.operations.append(("flow", left, right, adhesive))
            elif len(op) == 2:  # Legacy (func, target)
                left, right = op
                if isinstance(right, dict):
                    self.operations.append(("magnetic", left, right, AdhesiveType.GLUE_ATTRACT))
                else:
                    self.operations.append(("flow", left, right, AdhesiveType.GLUE_ATTRACT))
        elif callable(op):
            # Handle single function
            self.operations.append(("execute", op, None, AdhesiveType.GLUE_ATTRACT))
        else:
            # Handle direct operation
            self.operations.append(("execute", op, None, AdhesiveType.GLUE_ATTRACT))
        return self
    
    def add_error_handler(self, handler: Callable) -> 'Chain':
        """Add error handler"""
        if isinstance(handler, ChainOp):
            handler = handler.func
        self.error_handlers.append(handler)
        return self
    
    async def _execute_operation(
        self,
        op: Union[Tuple[str, ...], Callable[..., Any], Any],
        result: Any,
        adhesive: Optional[AdhesiveType] = None
    ) -> Tuple[Any, bool]:
        """Execute a single operation with error handling"""
        try:
            if isinstance(op, tuple):
                # Handle nested chain operations
                chain = Chain()
                chain.add_operation(op)
                return await chain(result), False
            elif hasattr(op, "execute"):
                # Handle tool execution
                if adhesive and adhesive.name.startswith('TAPE'):
                    op._break_after_use = True
                elif adhesive and adhesive.name.startswith('VELCRO'):
                    op._allow_reconnect = True
                elif adhesive and adhesive.name.startswith('GLUE'):
                    op._persist_context = True
                return await op.execute(input_data=result), False
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
                op_type, left, right, adhesive = op
                
                if op_type == "execute":
                    # Handle single operation
                    result, handled = await self._execute_operation(left, result, adhesive)
                    if handled:
                        return result
                        
                elif op_type == "flow":
                    # Handle sequential operations with magnetic flow
                    if adhesive in [AdhesiveType.GLUE_PUSH, AdhesiveType.VELCRO_PUSH, AdhesiveType.TAPE_PUSH]:
                        # Push flow: left -> right
                        result, handled = await self._execute_operation(left, result, adhesive)
                        if handled:
                            return result
                        result, handled = await self._execute_operation(right, result, adhesive)
                        if handled:
                            return result
                    elif adhesive in [AdhesiveType.GLUE_PULL, AdhesiveType.VELCRO_PULL, AdhesiveType.TAPE_PULL]:
                        # Pull flow: right <- left
                        result, handled = await self._execute_operation(right, result, adhesive)
                        if handled:
                            return result
                        result, handled = await self._execute_operation(left, result, adhesive)
                        if handled:
                            return result
                    else:
                        # Default bidirectional
                        result, handled = await self._execute_operation(left, result, adhesive)
                        if handled:
                            return result
                        result, handled = await self._execute_operation(right, result, adhesive)
                        if handled:
                            return result
                        
                elif op_type == "magnetic":
                    # Handle tool attraction with configuration
                    tool, targets = left, right
                    result, handled = await self._execute_operation(tool, result, adhesive)
                    if handled:
                        return result
                    
                    for target_name, target in targets.items():
                        result, handled = await self._execute_operation(target, result, adhesive)
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
        """Support >> operator for push flow"""
        if callable(other) and not hasattr(other, "__rshift__"):
            other = ChainOp(other)
        return self.add_operation((self, other, AdhesiveType.GLUE_PUSH))
    
    def __lshift__(self, other: Any) -> 'Chain':
        """Support << operator for pull flow"""
        if callable(other) and not hasattr(other, "__lshift__"):
            other = ChainOp(other)
        return self.add_operation((self, other, AdhesiveType.GLUE_PULL))
    
    def __xor__(self, other: Any) -> 'Chain':
        """Support ^ operator for bidirectional attraction"""
        if callable(other) and not hasattr(other, "__xor__"):
            other = ChainOp(other)
        return self.add_operation((self, other, AdhesiveType.GLUE_ATTRACT))
    
    def __str__(self) -> str:
        """String representation"""
        return f"Chain({len(self.operations)} operations)"
