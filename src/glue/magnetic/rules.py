# src/glue/magnetic/rules.py

# ==================== Imports ====================
from typing import Any, Callable, Dict, List, Optional, Set, Type, Union, Tuple, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum, auto

from ..core.types import ResourceState, AdhesiveType, InteractionPattern
from ..core.context import InteractionType

if TYPE_CHECKING:
    from .field import MagneticResource

# ==================== Enums ====================
class AttractionPolicy(Enum):
    """Policies for handling attraction between resources"""
    ALLOW_ALL = auto()     # Allow all attractions
    DENY_ALL = auto()      # Deny all attractions
    STATE_BASED = auto()   # Allow based on resource states
    PATTERN_BASED = auto() # Allow based on interaction patterns
    BINDING_BASED = auto() # Allow based on adhesive bindings
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
PatternValidator = Callable[[InteractionPattern, ResourceState, ResourceState], bool]
BindingValidator = Callable[[AdhesiveType, ResourceState, ResourceState], bool]

# ==================== Data Classes ====================
@dataclass
class AttractionRule:
    """Rule for determining if two resources can attract"""
    name: str
    policy: AttractionPolicy
    priority: PolicyPriority = PolicyPriority.MEDIUM
    custom_validator: Optional[ValidationFunc] = None
    state_validator: Optional[StateValidator] = None
    pattern_validator: Optional[PatternValidator] = None
    binding_validator: Optional[BindingValidator] = None
    description: str = ""
    enabled: bool = True

    def validate(
        self,
        source: 'MagneticResource',
        target: 'MagneticResource',
        pattern: Optional[InteractionPattern] = None,
        binding: Optional[AdhesiveType] = None
    ) -> bool:
        """
        Validate if two resources can interact based on this rule
        
        Args:
            source: Source resource
            target: Target resource
            pattern: Optional interaction pattern
            binding: Optional adhesive binding type
        """
        if not self.enabled:
            return True  # Disabled rules don't block

        if self.policy == AttractionPolicy.DENY_ALL:
            return False

        if self.policy == AttractionPolicy.ALLOW_ALL:
            return True

        if self.policy == AttractionPolicy.STATE_BASED and self.state_validator:
            return self.state_validator(source._state, target._state)

        if self.policy == AttractionPolicy.PATTERN_BASED and self.pattern_validator and pattern:
            return self.pattern_validator(pattern, source._state, target._state)

        if self.policy == AttractionPolicy.BINDING_BASED and self.binding_validator and binding:
            return self.binding_validator(binding, source._state, target._state)

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
                pattern_validator=rule.pattern_validator,
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
        source: 'MagneticResource',
        target: 'MagneticResource',
        pattern: Optional[InteractionPattern] = None,
        binding: Optional[AdhesiveType] = None
    ) -> bool:
        """
        Validate interaction using all rules in the set
        
        Args:
            source: Source resource
            target: Target resource
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
def create_state_validator(
    allowed_states: Set[ResourceState]
) -> StateValidator:
    """Create a validator that checks if resources are in allowed states"""
    def validator(state1: ResourceState, state2: ResourceState) -> bool:
        return state1 in allowed_states and state2 in allowed_states
    return validator

def create_pattern_validator(
    allowed_patterns: Dict[InteractionPattern, Tuple[Set[ResourceState], Set[ResourceState]]]
) -> PatternValidator:
    """
    Create a validator that checks if resources can use an interaction pattern
    
    Args:
        allowed_patterns: Dict mapping patterns to (source states, target states)
    """
    def validator(
        pattern: InteractionPattern,
        source_state: ResourceState,
        target_state: ResourceState
    ) -> bool:
        if pattern not in allowed_patterns:
            return False
        source_states, target_states = allowed_patterns[pattern]
        return source_state in source_states and target_state in target_states
    return validator

def create_binding_validator(
    allowed_bindings: Dict[AdhesiveType, Set[ResourceState]]
) -> BindingValidator:
    """
    Create a validator that checks if resources can use a binding type
    
    Args:
        allowed_bindings: Dict mapping binding types to allowed states
    """
    def validator(
        binding: AdhesiveType,
        source_state: ResourceState,
        target_state: ResourceState
    ) -> bool:
        if binding not in allowed_bindings:
            return False
        allowed_states = allowed_bindings[binding]
        return source_state in allowed_states and target_state in allowed_states
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
                # Pull teams can pull from any non-repelled resource
                (hasattr(source, 'is_pull_team') and source.is_pull_team and
                 not (hasattr(source, '_repelled_by') and target in source._repelled_by)) or
                # Allow normal interactions for non-pull teams
                not (hasattr(source, 'is_pull_team') and source.is_pull_team)
            ),
            description="Pull team validation"
        ),
        
        # Pattern state validation (HIGH priority)
        AttractionRule(
            name="pattern_states",
            policy=AttractionPolicy.PATTERN_BASED,
            priority=PolicyPriority.HIGH,
            pattern_validator=create_pattern_validator({
                InteractionPattern.ATTRACT: (
                    {ResourceState.IDLE, ResourceState.ACTIVE},  # Both states can attract
                    {ResourceState.IDLE, ResourceState.ACTIVE}
                ),
                InteractionPattern.PUSH: (
                    {ResourceState.ACTIVE},  # Only active resources can push
                    {ResourceState.IDLE}     # Only idle resources can receive
                ),
                InteractionPattern.PULL: (
                    {ResourceState.ACTIVE},  # Only active resources can pull
                    {ResourceState.IDLE}     # Only idle resources can be pulled from
                ),
                InteractionPattern.REPEL: (
                    {ResourceState.ACTIVE},  # Only active resources can repel
                    {ResourceState.ACTIVE}   # Only active resources can be repelled
                )
            }),
            description="Validate states for interaction patterns"
        ),
        
        # Context validation (HIGH priority)
        AttractionRule(
            name="context_states",
            policy=AttractionPolicy.CUSTOM,
            priority=PolicyPriority.HIGH,
            custom_validator=lambda source, target: (
                # Check if source has context
                not hasattr(source, '_context') or
                # If it does, validate based on interaction type
                (source._context.interaction_type == InteractionType.PULL and
                 hasattr(source, 'is_pull_team') and source.is_pull_team) or
                # Allow normal interactions for other types
                source._context.interaction_type != InteractionType.PULL
            ),
            description="Context-aware state validation"
        )
    ],
    description="Default rules for resource interaction"
)
