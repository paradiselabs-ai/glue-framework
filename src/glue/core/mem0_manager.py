"""Mem0-based memory management for GLUE framework"""

import os
from typing import Dict, Any, Optional, List, Set
from datetime import datetime
from pydantic import BaseModel, Field
from loguru import logger
from mem0 import Memory

from .types import AdhesiveType
from .context import ContextState, ComplexityLevel

class Mem0Config(BaseModel):
    """Configuration for Mem0"""
    collection_name: str = Field(default="glue_memory")
    host: str = Field(default="localhost")
    port: int = Field(default=6333)
    openai_api_key: Optional[str] = None

class Mem0Manager:
    """Mem0-based memory management for semantic storage and retrieval"""
    
    def __init__(self, config: Optional[Mem0Config] = None):
        self.config = config or Mem0Config()
        
        # Set OpenAI API key if provided
        if self.config.openai_api_key:
            os.environ["OPENAI_API_KEY"] = self.config.openai_api_key
            
        # Initialize Mem0
        self.mem0_config = {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": self.config.collection_name,
                    "host": self.config.host,
                    "port": self.config.port,
                }
            }
        }
        
        self.memory = Memory.from_config(self.mem0_config)
        logger.add("mem0_manager.log", rotation="10 MB")
        logger.info("Initialized Mem0 manager")
        
    async def store(
        self,
        content: Any,
        adhesive_type: AdhesiveType,
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[ContextState] = None,
        tags: Optional[Set[str]] = None
    ) -> str:
        """Store content with Mem0"""
        try:
            # Prepare metadata
            meta = metadata or {}
            meta.update({
                "adhesive_type": adhesive_type.value,
                "stored_at": datetime.now().isoformat(),
                "context_complexity": context.complexity.value if context else None,
                "tags": list(tags) if tags else []
            })
            
            # Store in Mem0
            memory_id = self.memory.add(
                str(content),
                user_id=user_id,
                metadata=meta
            )
            
            logger.info(
                f"Stored content in Mem0",
                memory_id=memory_id,
                user_id=user_id,
                adhesive=adhesive_type.value
            )
            
            return memory_id
            
        except Exception as e:
            logger.error(
                f"Failed to store content in Mem0: {str(e)}",
                user_id=user_id,
                adhesive=adhesive_type.value
            )
            raise
            
    async def retrieve(
        self,
        query: str,
        user_id: str,
        adhesive_type: Optional[AdhesiveType] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve content from Mem0 using semantic search"""
        try:
            # Build filter based on adhesive type
            filter_params = {}
            if adhesive_type:
                filter_params["adhesive_type"] = adhesive_type.value
                
            # Search Mem0
            memories = self.memory.search(
                query=query,
                user_id=user_id,
                metadata_filter=filter_params,
                limit=limit
            )
            
            logger.info(
                f"Retrieved memories from Mem0",
                query=query,
                user_id=user_id,
                count=len(memories)
            )
            
            return memories
            
        except Exception as e:
            logger.error(
                f"Failed to retrieve from Mem0: {str(e)}",
                query=query,
                user_id=user_id
            )
            raise
            
    async def update(
        self,
        memory_id: str,
        content: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Update existing memory in Mem0"""
        try:
            success = self.memory.update(
                memory_id=memory_id,
                data=str(content),
                metadata=metadata
            )
            
            if success:
                logger.info(
                    f"Updated memory in Mem0",
                    memory_id=memory_id
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Failed to update memory in Mem0: {str(e)}",
                memory_id=memory_id
            )
            raise
            
    async def delete(self, memory_id: str) -> bool:
        """Delete memory from Mem0"""
        try:
            success = self.memory.delete(memory_id)
            
            if success:
                logger.info(
                    f"Deleted memory from Mem0",
                    memory_id=memory_id
                )
            
            return success
            
        except Exception as e:
            logger.error(
                f"Failed to delete memory from Mem0: {str(e)}",
                memory_id=memory_id
            )
            raise
            
    async def get_history(self, memory_id: str) -> List[Dict[str, Any]]:
        """Get history of a memory's changes"""
        try:
            history = self.memory.history(memory_id)
            
            logger.info(
                f"Retrieved memory history from Mem0",
                memory_id=memory_id,
                changes=len(history)
            )
            
            return history
            
        except Exception as e:
            logger.error(
                f"Failed to get memory history from Mem0: {str(e)}",
                memory_id=memory_id
            )
            raise
            
    async def get_user_memories(
        self,
        user_id: str,
        adhesive_type: Optional[AdhesiveType] = None
    ) -> List[Dict[str, Any]]:
        """Get all memories for a user"""
        try:
            # Build filter
            filter_params = {}
            if adhesive_type:
                filter_params["adhesive_type"] = adhesive_type.value
                
            memories = self.memory.get_all(
                user_id=user_id,
                metadata_filter=filter_params
            )
            
            logger.info(
                f"Retrieved user memories from Mem0",
                user_id=user_id,
                count=len(memories)
            )
            
            return memories
            
        except Exception as e:
            logger.error(
                f"Failed to get user memories from Mem0: {str(e)}",
                user_id=user_id
            )
            raise
            
    async def cleanup(self) -> None:
        """Clean up Mem0 resources"""
        try:
            # Mem0 will handle cleanup internally
            logger.info("Cleaned up Mem0 manager")
        except Exception as e:
            logger.error(f"Error during Mem0 cleanup: {str(e)}")
            raise
