# src/glue/magnetic/rules.py

# ==================== Imports ====================
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto

from ..core.types import AdhesiveType
from ..core.context import ComplexityLevel
from ..core.team import Team

# ==================== Constants ====================
ATTRACT = "><"  # Bidirectional attraction
PUSH = "->"    # One-way push
PULL = "<-"    # One-way pull
REPEL = "<>"   # Repulsion

# ==================== Enums ====================
class InteractionPattern(Enum):
    """Patterns for team interactions"""
    ATTRACT = ATTRACT  # Bidirectional attraction
    PUSH = PUSH       # One-way push
    PULL = PULL      # One-way pull
    REPEL = REPEL    # Repulsion

class AttractionPolicy(Enum):
    """Policies for handling attraction between teams"""
    ALLOW_ALL = auto()     # Allow all attractions
    DENY_ALL = auto()      # Deny all attractions
    BINDING_BASED = auto() # Allow based on adhesive bindings
    CUSTOM = auto()        # Use custom validation function

class PolicyPriority(Enum):
    """Priority levels for attraction rules"""
    LOW = 1     # Can be overridden by higher priority rules
    MEDIUM = 2  # Standard priority
    HIGH = 3    # Overrides lower priority rules
    SYSTEM = 4  # Cannot be overridden

# ==================== Type Definitions ====================
ValidationFunc = Callable[[Team, Team], bool]
BindingValidator = Callable[[AdhesiveType], bool]

# ==================== Data Classes ====================
@dataclass
class AttractionRule:
    """Rule for determining if two teams can interact"""
    name: str
    policy: AttractionPolicy
    priority: PolicyPriority = PolicyPriority.MEDIUM
    custom_validator: Optional[ValidationFunc] = None
    binding_validator: Optional[BindingValidator] = None
    description: str = ""
    enabled: bool = True

    def validate(
        self,
        source: Team,
        target: Team,
        pattern: Optional[InteractionPattern] = None,
        binding: Optional[AdhesiveType] = None
    ) -> bool:
        """
        Validate if two teams can interact based on this rule
        
        Args:
            source: Source team
            target: Target team
            pattern: Optional interaction pattern
            binding: Optional adhesive binding type
        """
        if not self.enabled:
            return True  # Disabled rules don't block

        if self.policy == AttractionPolicy.DENY_ALL:
            return False

        if self.policy == AttractionPolicy.ALLOW_ALL:
            return True

        if self.policy == AttractionPolicy.BINDING_BASED and self.binding_validator and binding:
            return self.binding_validator(binding)

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
                binding_validator=rule.binding_validator,
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
        source: Team,
        target: Team,
        pattern: Optional[InteractionPattern] = None,
        binding: Optional[AdhesiveType] = None
    ) -> bool:
        """
        Validate interaction using all rules in the set
        
        Args:
            source: Source team
            target: Target team
            pattern: Optional interaction pattern
            binding: Optional adhesive binding type
        """
        if not self.enabled:
            return True

        for rule in self.rules:
            if rule.priority == PolicyPriority.SYSTEM:
                # System rules are absolute
                return rule.validate(source, target, pattern, binding)
            
            if not rule.validate(source, target, pattern, binding):
                return False

        return True

# ==================== Common Rules ====================
def create_binding_validator(
    allowed_bindings: Set[AdhesiveType]
) -> BindingValidator:
    """
    Create a validator that checks if teams can use a binding type
    
    Args:
        allowed_bindings: Set of allowed binding types
    """
    def validator(binding: AdhesiveType) -> bool:
        return binding in allowed_bindings
    return validator

# Common rule sets
DEFAULT_RULES = RuleSet(
    name="default",
    rules=[
        # Pull team validation (SYSTEM priority)
        AttractionRule(
            name="pull_team",
            policy=AttractionPolicy.CUSTOM,
            priority=PolicyPriority.SYSTEM,
            custom_validator=lambda source, target: (
                # Pull teams can pull from any non-repelled team
                (hasattr(source, 'is_pull_team') and source.is_pull_team and
                 target.name not in source._repelled_by) or
                # Allow normal interactions for non-pull teams
                not (hasattr(source, 'is_pull_team') and source.is_pull_team)
            ),
            description="Pull team validation"
        ),
        
        # Context validation (HIGH priority)
        AttractionRule(
            name="context_states",
            policy=AttractionPolicy.CUSTOM,
            priority=PolicyPriority.HIGH,
            custom_validator=lambda source, target: (
                # Check if source has context
                not hasattr(source, '_context') or
                # If it does, validate based on complexity
                (source._context.complexity >= ComplexityLevel.MODERATE and
                 hasattr(source, 'is_pull_team') and source.is_pull_team) or
                # Allow normal interactions for simple tasks
                source._context.complexity <= ComplexityLevel.MODERATE
            ),
            description="Context-aware validation"
        )
    ],
    description="Default rules for team interaction"
)
