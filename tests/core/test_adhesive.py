# tests/core/test_adhesive.py
import pytest
from datetime import datetime, timedelta
from src.glue.core.adhesive import (
    Adhesive,
    AdhesiveType,
    AdhesiveProperties,
    AdhesiveFactory
)

@pytest.fixture
def current_time():
    return datetime.now()

@pytest.fixture
def adhesive_factory():
    return AdhesiveFactory()

def test_adhesive_types(current_time):
    """Test all adhesive types can be created"""
    for adhesive_type in AdhesiveType:
        adhesive = Adhesive(adhesive_type, current_time)
        assert adhesive.type == adhesive_type
        assert adhesive.properties is not None
        assert adhesive.active is True

def test_adhesive_properties(current_time):
    """Test adhesive properties are set correctly"""
    glue = Adhesive(AdhesiveType.GLUE, current_time)
    assert glue.properties.strength == 0.8
    assert glue.properties.durability == 0.9
    assert glue.properties.flexibility == 0.3
    assert glue.properties.is_reusable is False

    tape = Adhesive(AdhesiveType.TAPE, current_time)
    assert tape.properties.duration is not None
    assert isinstance(tape.properties.duration, timedelta)

def test_adhesive_factory(current_time):
    """Test adhesive factory creates correct types"""
    factory = AdhesiveFactory()
    
    glue = factory.create("glue", current_time)
    assert isinstance(glue, Adhesive)
    assert glue.type == AdhesiveType.GLUE
    
    with pytest.raises(ValueError):
        factory.create("invalid_type")

def test_custom_properties(current_time):
    """Test creating adhesive with custom properties"""
    factory = AdhesiveFactory()
    properties = AdhesiveProperties(
        strength=0.5,
        durability=0.5,
        flexibility=0.5,
        duration=timedelta(minutes=30),
        is_reusable=True,
        max_uses=5
    )
    
    adhesive = factory.create_with_properties("tape", properties, current_time)
    assert adhesive.properties.strength == 0.5
    assert adhesive.properties.max_uses == 5

def test_temporary_binding(current_time):
    """Test temporary binding expiration"""
    properties = AdhesiveProperties(
        strength=1.0,
        durability=1.0,
        flexibility=1.0,
        duration=timedelta(minutes=5),
        is_reusable=False
    )
    
    adhesive = AdhesiveFactory.create_with_properties("tape", properties, current_time)
    assert adhesive.can_bind() is True
    
    # Test after expiration
    adhesive._current_time = current_time + timedelta(minutes=6)
    assert adhesive.can_bind() is False

def test_reusable_binding(current_time):
    """Test reusable binding behavior"""
    velcro = Adhesive(AdhesiveType.VELCRO, current_time)
    assert velcro.properties.is_reusable is True
    
    # Should be able to use multiple times
    assert velcro.use() is True
    assert velcro.use() is True
    assert velcro.active is True

def test_strength_calculation(current_time):
    """Test binding strength calculation"""
    # Test permanent binding
    glue = Adhesive(AdhesiveType.GLUE, current_time)
    assert glue.get_strength() == 0.8
    
    # Test temporary binding strength degradation
    properties = AdhesiveProperties(
        strength=1.0,
        durability=1.0,
        flexibility=1.0,
        duration=timedelta(minutes=10),
        is_reusable=False
    )
    
    tape = AdhesiveFactory.create_with_properties("tape", properties, current_time)
    initial_strength = tape.get_strength()
    
    # Test after some time has passed
    tape._current_time = current_time + timedelta(minutes=5)
    degraded_strength = tape.get_strength()
    assert degraded_strength < initial_strength