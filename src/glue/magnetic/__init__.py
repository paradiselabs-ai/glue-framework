# src/glue/magnetic/__init__.py

"""GLUE Magnetic Field System"""

from .rules import AttractionRule, AttractionPolicy, PolicyPriority
from .field import MagneticField
from ..core.types import ResourceState

__all__ = [
    'AttractionRule',
    'AttractionPolicy',
    'PolicyPriority',
    'MagneticField',
    'ResourceState'
]
