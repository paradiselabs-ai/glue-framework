# src/glue/magnetic/rules.py

# ==================== Imports ====================
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum, auto

from ..core.types import ResourceState

if TYPE_CHECKING:
    from .field import MagneticResource

# ==================== Enums ====================
class AttractionPolicy(Enum):
    """Policies for handling attraction between resources"""
    ALLOW_ALL = auto()     # Allow all attractions
    DENY_ALL = auto()      # Deny all attractions
    STATE_BASED = auto()   # Allow based on resource states
    CUSTOM = auto()        # Use custom validation function

class PolicyPriority(Enum):
    """Priority levels for attraction rules"""
    LOW = 1     # Can be overridden by higher priority rules
    MEDIUM = 2  # Standard priority
    HIGH = 3    # Overrides lower priority rules
    SYSTEM = 4  # Cannot be overridden

# ==================== Type Definitions ====================
ValidationFunc = Callable[['MagneticResource', 'MagneticResource'], bool]
StateValidator = Callable[[ResourceState, ResourceState], bool]

# ==================== Data Classes ====================
@dataclass
class AttractionRule:
    """Rule for determining if two resources can attract"""
    name: str
    policy: AttractionPolicy
    priority: PolicyPriority = PolicyPriority.MEDIUM
    custom_validator: Optional[ValidationFunc] = None
    state_validator: Optional[StateValidator] = None
    description: str = ""
    enabled: bool = True

    def validate(
        self,
        source: 'MagneticResource',
        target: 'MagneticResource'
    ) -> bool:
        """Validate if two resources can attract based on this rule"""
        if not self.enabled:
            return True  # Disabled rules don't block

        if self.policy == AttractionPolicy.DENY_ALL:
            return False

        if self.policy == AttractionPolicy.ALLOW_ALL:
            return True

        if self.policy == AttractionPolicy.STATE_BASED and self.state_validator:
            return self.state_validator(source._state, target._state)

        if self.policy == AttractionPolicy.CUSTOM and self.custom_validator:
            return self.custom_validator(source, target)

        return True

# ==================== Rule Sets ====================
@dataclass
class RuleSet:
    """Collection of attraction rules with priority handling"""
    name: str
    rules: List[AttractionRule] = field(default_factory=list)
    description: str = ""
    enabled: bool = True

    def copy(self) -> 'RuleSet':
        """Create a copy of this rule set"""
        new_rules = [
            AttractionRule(
                name=rule.name,
                policy=rule.policy,
                priority=rule.priority,
                custom_validator=rule.custom_validator,
                state_validator=rule.state_validator,
                description=rule.description,
                enabled=rule.enabled
            )
            for rule in self.rules
        ]
        return RuleSet(
            name=f"{self.name}_copy",
            rules=new_rules,
            description=self.description,
            enabled=self.enabled
        )

    def add_rule(self, rule: AttractionRule) -> None:
        """Add a rule to the set"""
        self.rules.append(rule)
        # Sort rules by priority (highest first)
        self.rules.sort(key=lambda r: r.priority.value, reverse=True)

    def remove_rule(self, rule_name: str) -> None:
        """Remove a rule by name"""
        self.rules = [r for r in self.rules if r.name != rule_name]

    def validate(
        self,
        source: 'MagneticResource',
        target: 'MagneticResource'
    ) -> bool:
        """Validate attraction using all rules in the set"""
        if not self.enabled:
            return True

        for rule in self.rules:
            if rule.priority == PolicyPriority.SYSTEM:
                # System rules are absolute
                return rule.validate(source, target)
            
            if not rule.validate(source, target):
                return False

        return True

# ==================== Common Rules ====================
def create_state_validator(
    allowed_states: Set[ResourceState]
) -> StateValidator:
    """Create a validator that checks if resources are in allowed states"""
    def validator(state1: ResourceState, state2: ResourceState) -> bool:
        return state1 in allowed_states and state2 in allowed_states
    return validator

# Common rule sets
DEFAULT_RULES = RuleSet(
    name="default",
    rules=[
        AttractionRule(
            name="system_locked",
            policy=AttractionPolicy.STATE_BASED,
            priority=PolicyPriority.SYSTEM,
            state_validator=create_state_validator({
                ResourceState.IDLE,
                ResourceState.SHARED
            }),
            description="Prevent attraction to locked resources"
        )
    ],
    description="Default rules for resource attraction"
)
