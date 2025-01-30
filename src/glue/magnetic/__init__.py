"""GLUE Magnetic Field System

Provides field-based coordination between models and teams through:
- Attraction rules and policies
- Field-based state management
- Interaction patterns
"""

from .rules import (
    AttractionRule,
    AttractionPolicy,
    PolicyPriority,
    InteractionPattern
)
from .field import MagneticField

__all__ = [
    'AttractionRule',
    'AttractionPolicy',
    'PolicyPriority',
    'MagneticField',
    'InteractionPattern'
]
