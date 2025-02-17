"""Feedback system for GLUE framework"""

from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from enum import Enum
from loguru import logger

class FeedbackType(str, Enum):
    """Types of feedback"""
    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    IMPROVEMENT = "improvement"
    QUESTION = "question"
    OTHER = "other"

class FeedbackSeverity(str, Enum):
    """Severity levels for feedback"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class FeedbackStatus(str, Enum):
    """Status of feedback items"""
    NEW = "new"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"

class Feedback(BaseModel):
    """Model for user feedback"""
    id: str = Field(..., description="Unique identifier for feedback")
    type: FeedbackType
    severity: FeedbackSeverity
    description: str
    component: str
    submitted_by: str
    submitted_at: datetime = Field(default_factory=datetime.now)
    status: FeedbackStatus = Field(default=FeedbackStatus.NEW)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None

class FeedbackManager:
    """Manages user feedback collection and tracking"""
    
    def __init__(self):
        self.feedback_items: Dict[str, Feedback] = {}
        logger.add("feedback.log", rotation="10 MB")
        
    def submit_feedback(
        self,
        type: FeedbackType,
        severity: FeedbackSeverity,
        description: str,
        component: str,
        submitted_by: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Feedback:
        """Submit new feedback"""
        feedback_id = f"FB_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{submitted_by}"
        
        feedback = Feedback(
            id=feedback_id,
            type=type,
            severity=severity,
            description=description,
            component=component,
            submitted_by=submitted_by,
            metadata=metadata or {}
        )
        
        self.feedback_items[feedback_id] = feedback
        
        logger.info(
            f"New feedback submitted: {feedback_id}",
            feedback=feedback.model_dump()
        )
        
        return feedback
        
    def update_status(
        self,
        feedback_id: str,
        status: FeedbackStatus,
        resolution: Optional[str] = None
    ) -> Optional[Feedback]:
        """Update feedback status"""
        if feedback_id not in self.feedback_items:
            logger.error(f"Feedback not found: {feedback_id}")
            return None
            
        feedback = self.feedback_items[feedback_id]
        feedback.status = status
        
        if status == FeedbackStatus.RESOLVED:
            feedback.resolution = resolution
            feedback.resolved_at = datetime.now()
            
        logger.info(
            f"Updated feedback status: {feedback_id}",
            feedback=feedback.model_dump()
        )
        
        return feedback
        
    def get_feedback(self, feedback_id: str) -> Optional[Feedback]:
        """Get feedback by ID"""
        return self.feedback_items.get(feedback_id)
        
    def get_all_feedback(
        self,
        status: Optional[FeedbackStatus] = None,
        type: Optional[FeedbackType] = None
    ) -> List[Feedback]:
        """Get all feedback, optionally filtered by status or type"""
        items = self.feedback_items.values()
        
        if status:
            items = [f for f in items if f.status == status]
        if type:
            items = [f for f in items if f.type == type]
            
        return sorted(
            items,
            key=lambda x: x.submitted_at,
            reverse=True
        )
        
    def get_feedback_summary(self) -> Dict[str, Any]:
        """Get summary of feedback"""
        total = len(self.feedback_items)
        by_status = {
            status: len([f for f in self.feedback_items.values() if f.status == status])
            for status in FeedbackStatus
        }
        by_type = {
            type: len([f for f in self.feedback_items.values() if f.type == type])
            for type in FeedbackType
        }
        by_severity = {
            severity: len([f for f in self.feedback_items.values() if f.severity == severity])
            for severity in FeedbackSeverity
        }
        
        return {
            "total": total,
            "by_status": by_status,
            "by_type": by_type,
            "by_severity": by_severity,
            "resolution_rate": (
                by_status[FeedbackStatus.RESOLVED] / total
                if total > 0 else 0
            )
        }
        
    def collect_feedback(self) -> Feedback:
        """Interactive feedback collection (for CLI use)"""
        try:
            print("\nGLUE Framework Feedback Collection")
            print("==================================")
            
            # Get feedback type
            print("\nFeedback Type:")
            for i, type in enumerate(FeedbackType):
                print(f"{i+1}. {type.value}")
            type_idx = int(input("Select type (1-5): ")) - 1
            type = list(FeedbackType)[type_idx]
            
            # Get severity
            print("\nSeverity Level:")
            for i, severity in enumerate(FeedbackSeverity):
                print(f"{i+1}. {severity.value}")
            severity_idx = int(input("Select severity (1-4): ")) - 1
            severity = list(FeedbackSeverity)[severity_idx]
            
            # Get description
            description = input("\nDescribe the issue/feedback: ")
            
            # Get component
            component = input("\nWhich component is this about? ")
            
            # Get metadata
            metadata = {}
            if input("\nAdd additional details? (y/n): ").lower() == 'y':
                while True:
                    key = input("Key (or enter to finish): ")
                    if not key:
                        break
                    value = input(f"Value for {key}: ")
                    metadata[key] = value
                    
            feedback = self.submit_feedback(
                type=type,
                severity=severity,
                description=description,
                component=component,
                submitted_by="cli_user",
                metadata=metadata
            )
            
            print(f"\nFeedback submitted successfully. ID: {feedback.id}")
            return feedback
            
        except Exception as e:
            logger.error(f"Error collecting feedback: {str(e)}")
            raise
