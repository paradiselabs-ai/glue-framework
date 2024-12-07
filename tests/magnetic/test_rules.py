# tests/magnetic/test_rules.py

# ==================== Imports ====================
import pytest
from src.glue.magnetic.rules import (
    AttractionPolicy,
    PolicyPriority,
    AttractionRule,
    RuleSet,
    create_state_validator,
    DEFAULT_RULES
)
from src.glue.magnetic.field import (
    MagneticResource,
    AttractionStrength,
    ResourceState
)

# ==================== Fixtures ====================
@pytest.fixture
def resources():
    """Create test resources"""
    return [
        MagneticResource("r1", AttractionStrength.MEDIUM),
        MagneticResource("r2", AttractionStrength.STRONG),
        MagneticResource("r3", AttractionStrength.WEAK)
    ]

@pytest.fixture
def custom_validator():
    """Create a custom validation function"""
    def validator(source: MagneticResource, target: MagneticResource) -> bool:
        return source.name.startswith("r") and target.name.startswith("r")
    return validator

@pytest.fixture
def state_validator():
    """Create a state validation function"""
    return create_state_validator({ResourceState.IDLE, ResourceState.SHARED})

# ==================== Tests ====================
def test_attraction_rule_initialization():
    """Test basic rule initialization"""
    rule = AttractionRule(
        name="test_rule",
        policy=AttractionPolicy.ALLOW_ALL,
        priority=PolicyPriority.MEDIUM,
        description="Test rule"
    )
    assert rule.name == "test_rule"
    assert rule.policy == AttractionPolicy.ALLOW_ALL
    assert rule.priority == PolicyPriority.MEDIUM
    assert rule.enabled

def test_allow_all_policy(resources):
    """Test ALLOW_ALL policy"""
    rule = AttractionRule(
        name="allow_all",
        policy=AttractionPolicy.ALLOW_ALL
    )
    assert rule.validate(resources[0], resources[1])

def test_deny_all_policy(resources):
    """Test DENY_ALL policy"""
    rule = AttractionRule(
        name="deny_all",
        policy=AttractionPolicy.DENY_ALL
    )
    assert not rule.validate(resources[0], resources[1])

def test_strength_based_policy(resources):
    """Test STRENGTH_BASED policy"""
    rule = AttractionRule(
        name="strength_check",
        policy=AttractionPolicy.STRENGTH_BASED,
        min_strength=AttractionStrength.MEDIUM
    )
    
    # Should allow MEDIUM to STRONG
    assert rule.validate(resources[0], resources[1])
    
    # Should deny WEAK to MEDIUM
    assert not rule.validate(resources[2], resources[0])

def test_state_based_policy(resources, state_validator):
    """Test STATE_BASED policy"""
    rule = AttractionRule(
        name="state_check",
        policy=AttractionPolicy.STATE_BASED,
        state_validator=state_validator
    )
    
    # Both IDLE should be allowed
    assert rule.validate(resources[0], resources[1])
    
    # Change one to LOCKED
    resources[0]._state = ResourceState.LOCKED
    assert not rule.validate(resources[0], resources[1])

def test_custom_policy(resources, custom_validator):
    """Test CUSTOM policy"""
    rule = AttractionRule(
        name="custom_check",
        policy=AttractionPolicy.CUSTOM,
        custom_validator=custom_validator
    )
    
    # Both start with 'r', should allow
    assert rule.validate(resources[0], resources[1])
    
    # Change name to not start with 'r'
    resources[1].name = "test"
    assert not rule.validate(resources[0], resources[1])

def test_rule_priority():
    """Test rule priority handling"""
    rules = [
        AttractionRule("low", AttractionPolicy.ALLOW_ALL, PolicyPriority.LOW),
        AttractionRule("high", AttractionPolicy.DENY_ALL, PolicyPriority.HIGH),
        AttractionRule("medium", AttractionPolicy.ALLOW_ALL, PolicyPriority.MEDIUM)
    ]
    
    rule_set = RuleSet("test_set")
    for rule in rules:
        rule_set.add_rule(rule)
    
    # Rules should be sorted by priority (HIGH to LOW)
    assert rule_set.rules[0].priority == PolicyPriority.HIGH
    assert rule_set.rules[-1].priority == PolicyPriority.LOW

def test_rule_set_validation(resources):
    """Test rule set validation"""
    rule_set = RuleSet("test_set")
    
    # Add rules with different priorities
    rule_set.add_rule(AttractionRule(
        "allow",
        AttractionPolicy.ALLOW_ALL,
        PolicyPriority.LOW
    ))
    rule_set.add_rule(AttractionRule(
        "deny",
        AttractionPolicy.DENY_ALL,
        PolicyPriority.HIGH
    ))
    
    # High priority DENY_ALL should take precedence
    assert not rule_set.validate(resources[0], resources[1])

def test_system_priority_rules(resources):
    """Test system priority rules"""
    rule_set = RuleSet("test_set")
    
    # Add a system rule
    rule_set.add_rule(AttractionRule(
        "system_deny",
        AttractionPolicy.DENY_ALL,
        PolicyPriority.SYSTEM
    ))
    
    # Add other rules that would allow
    rule_set.add_rule(AttractionRule(
        "allow",
        AttractionPolicy.ALLOW_ALL,
        PolicyPriority.HIGH
    ))
    
    # System rule should override all others
    assert not rule_set.validate(resources[0], resources[1])

def test_default_rules(resources):
    """Test default rule set"""
    # Default rules should allow valid interactions
    assert DEFAULT_RULES.validate(resources[0], resources[1])  # MEDIUM to STRONG
    
    # Lock a resource
    resources[0]._state = ResourceState.LOCKED
    assert not DEFAULT_RULES.validate(resources[0], resources[1])

def test_rule_set_management():
    """Test rule set management operations"""
    rule_set = RuleSet("test_set")
    
    # Add rules
    rule_set.add_rule(AttractionRule("rule1", AttractionPolicy.ALLOW_ALL))
    rule_set.add_rule(AttractionRule("rule2", AttractionPolicy.DENY_ALL))
    assert len(rule_set.rules) == 2
    
    # Remove rule
    rule_set.remove_rule("rule1")
    assert len(rule_set.rules) == 1
    assert rule_set.rules[0].name == "rule2"

def test_disabled_rules(resources):
    """Test disabled rules and rule sets"""
    rule = AttractionRule(
        "deny",
        AttractionPolicy.DENY_ALL,
        enabled=False
    )
    assert rule.validate(resources[0], resources[1])  # Should pass when disabled
    
    rule_set = RuleSet("test_set", enabled=False)
    rule_set.add_rule(AttractionRule(
        "deny",
        AttractionPolicy.DENY_ALL
    ))
    assert rule_set.validate(resources[0], resources[1])  # Should pass when disabled

def test_state_validator_creation():
    """Test state validator creation"""
    validator = create_state_validator({
        ResourceState.IDLE,
        ResourceState.SHARED
    })
    
    assert validator(ResourceState.IDLE, ResourceState.IDLE)
    assert validator(ResourceState.IDLE, ResourceState.SHARED)
    assert not validator(ResourceState.IDLE, ResourceState.LOCKED)

def test_rule_description():
    """Test rule description handling"""
    rule = AttractionRule(
        name="test",
        policy=AttractionPolicy.ALLOW_ALL,
        description="Test description"
    )
    assert rule.description == "Test description"
    
    rule_set = RuleSet(
        name="test_set",
        description="Test set description"
    )
    assert rule_set.description == "Test set description"
