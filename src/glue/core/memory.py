"""GLUE Memory Management System"""

from typing import Dict, Any, Optional, List, Set, TypeVar, Generic
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict
import json
import os
from pathlib import Path
from .context import ContextState, ComplexityLevel

@dataclass
class MemorySegment:
    """Represents a single memory segment"""
    content: Any
    created_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    context: Optional[ContextState] = None
    tags: Set[str] = field(default_factory=set)

@dataclass
class InteractionPattern:
    """Pattern recognized in interactions"""
    trigger: str  # What initiated this pattern
    sequence: List[str]  # Sequence of actions/responses
    success_rate: float
    usage_count: int
    complexities: Set[ComplexityLevel]  # Track what complexity levels work
    last_used: datetime

@dataclass
class LearningOutcome:
    """Records what was learned from an interaction"""
    pattern: str
    success: bool
    feedback: Optional[str]
    context: ContextState
    timestamp: datetime

class MemoryManager:
    """Manages different types of memory for models"""
    def __init__(self, persistence_dir: Optional[str] = None):
        # Memory stores
        self.short_term: Dict[str, MemorySegment] = {}
        self.long_term: Dict[str, MemorySegment] = {}
        self.working: Dict[str, MemorySegment] = {}
        self.shared: Dict[str, Dict[str, MemorySegment]] = {}
        
        # Learning components
        self.patterns: Dict[str, InteractionPattern] = {}
        self.outcomes: List[LearningOutcome] = []
        
        # Performance tracking
        self.recall_success: Dict[str, bool] = {}
        self.pattern_matches: Dict[str, int] = defaultdict(int)
        
        # Persistence
        self.persistence_dir = Path(persistence_dir) if persistence_dir else None
        if self.persistence_dir:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
            self._load_persistent_memory()
    
    async def store(
        self,
        key: str,
        content: Any,
        memory_type: str = "short_term",
        duration: Optional[timedelta] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ContextState] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """Store content in specified memory type"""
        expires_at = datetime.now() + duration if duration else None
        segment = MemorySegment(
            content=content,
            expires_at=expires_at,
            metadata=metadata or {},
            context=context,
            tags=tags or set()
        )
        
        if memory_type == "short_term":
            self.short_term[key] = segment
        elif memory_type == "long_term":
            self.long_term[key] = segment
            if self.persistence_dir:
                self._save_segment(key, segment)
        elif memory_type == "working":
            self.working[key] = segment
        else:
            raise ValueError(f"Unknown memory type: {memory_type}")

    def recall(
        self,
        key: str,
        memory_type: str = "short_term"
    ) -> Optional[Any]:
        """Retrieve content from specified memory type"""
        memory_store = self._get_memory_store(memory_type)
        
        if key not in memory_store:
            self.recall_success[key] = False
            return None
            
        segment = memory_store[key]
        
        # Check expiration
        if segment.expires_at and datetime.now() > segment.expires_at:
            del memory_store[key]
            self.recall_success[key] = False
            return None
            
        # Update access metadata
        segment.access_count += 1
        segment.last_accessed = datetime.now()
        self.recall_success[key] = True
        
        return segment.content

    def share(
        self,
        from_model: str,
        to_model: str,
        key: str,
        content: Any,
        duration: Optional[timedelta] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ContextState] = None,
        tags: Optional[Set[str]] = None
    ) -> None:
        """Share memory between models"""
        if from_model not in self.shared:
            self.shared[from_model] = {}
            
        expires_at = datetime.now() + duration if duration else None
        segment = MemorySegment(
            content=content,
            expires_at=expires_at,
            metadata=metadata or {},
            context=context,
            tags=tags or set()
        )
        
        self.shared[from_model][key] = segment
        
        # Create reverse lookup
        if to_model not in self.shared:
            self.shared[to_model] = {}
        self.shared[to_model][f"from_{from_model}_{key}"] = segment

    def forget(self, key: str, memory_type: str = "short_term") -> None:
        """Remove content from specified memory type"""
        memory_store = self._get_memory_store(memory_type)
        if key in memory_store:
            del memory_store[key]

    def clear(self, memory_type: Optional[str] = None) -> None:
        """Clear specified or all memory types"""
        if memory_type:
            memory_store = self._get_memory_store(memory_type)
            memory_store.clear()
        else:
            self.short_term.clear()
            self.long_term.clear()
            self.working.clear()
            self.shared.clear()
            self.patterns.clear()
            self.outcomes.clear()
            self.recall_success.clear()
            self.pattern_matches.clear()

    def _get_memory_store(self, memory_type: str) -> Dict[str, MemorySegment]:
        """Get the appropriate memory store"""
        if memory_type == "short_term":
            return self.short_term
        elif memory_type == "long_term":
            return self.long_term
        elif memory_type == "working":
            return self.working
        else:
            raise ValueError(f"Unknown memory type: {memory_type}")

    def cleanup_expired(self) -> None:
        """Remove all expired memory segments"""
        now = datetime.now()
        
        for memory_store in [self.short_term, self.long_term, self.working]:
            expired_keys = [
                key for key, segment in memory_store.items()
                if segment.expires_at and now > segment.expires_at
            ]
            for key in expired_keys:
                del memory_store[key]
                
        # Clean shared memories
        for model in list(self.shared.keys()):
            expired_keys = [
                key for key, segment in self.shared[model].items()
                if segment.expires_at and now > segment.expires_at
            ]
            for key in expired_keys:
                del self.shared[model][key]

    def learn_pattern(
        self,
        trigger: str,
        sequence: List[str],
        success: bool,
        context: ContextState
    ) -> None:
        """Learn a new interaction pattern"""
        pattern_key = f"{trigger}:{'->'.join(sequence)}"
        
        if pattern_key in self.patterns:
            pattern = self.patterns[pattern_key]
            # Update statistics
            pattern.usage_count += 1
            pattern.success_rate = (
                (pattern.success_rate * (pattern.usage_count - 1) + (1.0 if success else 0.0))
                / pattern.usage_count
            )
            pattern.complexities.add(context.complexity)
            pattern.last_used = datetime.now()
        else:
            # Create new pattern
            self.patterns[pattern_key] = InteractionPattern(
                trigger=trigger,
                sequence=sequence,
                success_rate=1.0 if success else 0.0,
                usage_count=1,
                complexities={context.complexity},
                last_used=datetime.now()
            )
        
        # Record learning outcome
        self.outcomes.append(LearningOutcome(
            pattern=pattern_key,
            success=success,
            feedback=None,
            context=context,
            timestamp=datetime.now()
        ))

    def find_similar_pattern(
        self,
        trigger: str,
        context: ContextState,
        min_similarity: float = 0.7
    ) -> Optional[InteractionPattern]:
        """Find a similar interaction pattern"""
        best_match = None
        best_score = min_similarity
        
        # Check patterns with same trigger at similar complexity
        for pattern in self.patterns.values():
            if pattern.trigger == trigger and context.complexity in pattern.complexities:
                score = pattern.success_rate
                if score > best_score:
                    best_match = pattern
                    best_score = score
        
        if best_match:
            self.pattern_matches[best_match.trigger] += 1
        
        return best_match

    def get_complexity_patterns(
        self,
        complexity: ComplexityLevel,
        min_success_rate: float = 0.5
    ) -> List[InteractionPattern]:
        """Get patterns that work well at a complexity level"""
        return [
            pattern for pattern in self.patterns.values()
            if (complexity in pattern.complexities and
                pattern.success_rate >= min_success_rate)
        ]

    def record_feedback(
        self,
        pattern: str,
        feedback: str,
        context: ContextState
    ) -> None:
        """Record feedback about a pattern"""
        self.outcomes.append(LearningOutcome(
            pattern=pattern,
            success=True,  # Feedback implies engagement
            feedback=feedback,
            context=context,
            timestamp=datetime.now()
        ))

    def get_learning_summary(
        self,
        time_window: Optional[timedelta] = None
    ) -> Dict[str, Any]:
        """Get summary of learning outcomes"""
        if time_window:
            cutoff = datetime.now() - time_window
            relevant_outcomes = [
                o for o in self.outcomes
                if o.timestamp > cutoff
            ]
        else:
            relevant_outcomes = self.outcomes
            
        return {
            "total_patterns": len(self.patterns),
            "pattern_usage": {
                pattern.trigger: pattern.usage_count
                for pattern in self.patterns.values()
            },
            "complexity_distribution": {
                complexity.name: len([
                    p for p in self.patterns.values()
                    if complexity in p.complexities
                ])
                for complexity in ComplexityLevel
            },
            "success_rate": (
                sum(1 for o in relevant_outcomes if o.success)
                / len(relevant_outcomes)
                if relevant_outcomes else 0.0
            ),
            "feedback_count": sum(
                1 for o in relevant_outcomes
                if o.feedback is not None
            )
        }

    def _save_segment(self, key: str, segment: MemorySegment) -> None:
        """Save a memory segment to disk"""
        if not self.persistence_dir:
            return
            
        file_path = self.persistence_dir / f"{key}.json"
        
        # Convert datetime objects to ISO format
        segment_data = {
            "content": segment.content,
            "created_at": segment.created_at.isoformat(),
            "expires_at": segment.expires_at.isoformat() if segment.expires_at else None,
            "metadata": segment.metadata,
            "access_count": segment.access_count,
            "last_accessed": (
                segment.last_accessed.isoformat()
                if segment.last_accessed else None
            ),
            "context": (
                {
                    **segment.context.__dict__,
                    "tools_required": list(segment.context.tools_required), # Convert set to list for serialization
                    "complexity": segment.context.complexity.name
                } if segment.context else None
            ),
            "tags": list(segment.tags)
        }
        
        with open(file_path, 'w') as f:
            json.dump(segment_data, f, indent=2, default=str)

    def _load_persistent_memory(self) -> None:
        """Load persistent memory from disk"""
        if not self.persistence_dir:
            return
            
        for file_path in self.persistence_dir.glob("*.json"):
            try:
                with open(file_path) as f:
                    data = json.load(f)
                
                # Convert ISO format strings back to datetime
                segment = MemorySegment(
                    content=data["content"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    expires_at=(
                        datetime.fromisoformat(data["expires_at"])
                        if data["expires_at"] else None
                    ),
                    metadata=data["metadata"],
                    access_count=data["access_count"],
                    last_accessed=(
                        datetime.fromisoformat(data["last_accessed"])
                        if data["last_accessed"] else None
                    ),
                    context=ContextState(**{
                        **data["context"], 
                        'complexity': ComplexityLevel[data["context"]["complexity"]],
                        'tools_required': set(data["context"]["tools_required"]) # Convert list back to set
                    }) if data["context"] else None,
                    tags=set(data["tags"])
                )
                
                key = file_path.stem
                self.long_term[key] = segment
                
            except Exception as e:
                print(f"Error loading {file_path}: {e}")

    def __str__(self) -> str:
        return (
            f"MemoryManager("
            f"short_term={len(self.short_term)}, "
            f"long_term={len(self.long_term)}, "
            f"working={len(self.working)}, "
            f"shared_spaces={len(self.shared)}, "
            f"patterns={len(self.patterns)})"
        )
