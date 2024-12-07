# src/glue/expressions/core.py

"""Core GLUE Expression Language Components"""

from functools import wraps
from typing import Any, List, Dict, Union, Optional
from ..magnetic.field import AttractionStrength
from .chain import Chain

def glue_app(name: str):
    """Create GLUE application with minimal boilerplate"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator

class field:
    """Magnetic field context with minimal syntax"""
    def __init__(self, name: str, strength: str = "medium"):
        self.name = name
        self.strength = AttractionStrength[strength.upper()]
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass
    
    def __call__(self, *args, **kwargs):
        """Allow both context manager and decorator usage"""
        if len(args) == 1 and callable(args[0]):
            return self.decorate(args[0])
        return self
    
    def decorate(self, func):
        """Decorator form for even less boilerplate"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            async with self:
                return await func(*args, **kwargs)
        return wrapper

def magnet(name: str, strength: str = "medium", **kwargs) -> Dict[str, Any]:
    """Create magnetic component with minimal config"""
    config = {
        "name": name,
        "strength": AttractionStrength[strength.upper()],
        "__magnet__": True
    }
    config.update(kwargs)
    return config

def magnetize(tools: Union[List[str], Dict[str, Any]]) -> Dict[str, Any]:
    """Make tools magnetic with minimal syntax"""
    if isinstance(tools, list):
        return {t: magnet(t) for t in tools}
    
    result = {}
    for k, v in tools.items():
        if isinstance(v, dict):
            # Merge existing config with magnet defaults
            config = v.copy()
            config["name"] = k
            result[k] = magnet(**config)
        else:
            result[k] = magnet(k)
    return result
