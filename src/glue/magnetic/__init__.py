# src/glue/magnetic/__init__.py

"""GLUE Magnetic Field System"""

from .rules import AttractionRule, AttractionPolicy, PolicyPriority
from .field import MagneticField, MagneticResource, ResourceState

__all__ = [
    'AttractionRule',
    'AttractionPolicy',
    'PolicyPriority',
    'MagneticField',
    'MagneticResource',
    'ResourceState'
]
