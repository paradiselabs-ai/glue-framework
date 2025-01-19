# src/glue/core/patterns.py

"""Core interaction patterns for GLUE"""

from enum import Enum

class InteractionPattern(Enum):
    """Patterns for resource interaction"""
    ATTRACT = "><"  # Bidirectional attraction
    PUSH = "->"    # One-way push
    PULL = "<-"    # One-way pull
    REPEL = "<>"   # Repulsion
