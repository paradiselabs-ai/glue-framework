"""GLUE Magnetic Field System

Provides field-based coordination between models and teams through:
- Team-to-team information flow
- Magnetic operators (><, ->, <-, <>)
- Flow state management
"""

from .field import MagneticField
from .models import (
    FlowConfig,
    FlowState,
    FieldConfig,
    FieldState,
    FieldEvent,
    FlowEstablishedEvent,
    FlowBrokenEvent,
    TeamRepelledEvent,
    ResultsSharedEvent,
    FlowError
)

__all__ = [
    'MagneticField',
    'FlowConfig',
    'FlowState',
    'FieldConfig',
    'FieldState',
    'FieldEvent',
    'FlowEstablishedEvent',
    'FlowBrokenEvent',
    'TeamRepelledEvent',
    'ResultsSharedEvent',
    'FlowError'
]
