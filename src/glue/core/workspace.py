# src/glue/core/workspace.py

"""GLUE Workspace Management"""

import os
import json
import shutil
import hashlib
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager
from ..core.logger import get_logger
from ..magnetic.field import MagneticField

class WorkspaceError(Exception):
    """Base class for workspace errors"""
    pass

class Workspace:
    """Represents an active workspace"""
    def __init__(self, path: str, field: MagneticField):
        self.path = path
        self.field = field

class WorkspaceManager:
    """Manages GLUE workspaces with persistence support"""
    
    def __init__(self, base_dir: str = "workspaces"):
        """Initialize workspace manager"""
        self.base_dir = Path(base_dir)
        self.workspaces_file = self.base_dir / "workspaces.json"
        self.logger = get_logger()
        self._load_workspaces()
    
    def __enter__(self):
        """Enter context manager"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager"""
        self.cleanup_old_workspaces()
    
    async def __aenter__(self):
        """Enter async context manager"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager"""
        self.cleanup_old_workspaces()
    
    def _load_workspaces(self) -> None:
        """Load workspace registry"""
        self.workspaces = {}
        try:
            if self.workspaces_file.exists():
                with open(self.workspaces_file, 'r') as f:
                    self.workspaces = json.load(f)
                self.logger.debug(f"Loaded {len(self.workspaces)} workspaces")
        except Exception as e:
            self.logger.error(f"Error loading workspaces: {str(e)}")
            # Start fresh if file is corrupted
            self.workspaces = {}
    
    def _save_workspaces(self) -> None:
        """Save workspace registry"""
        try:
            os.makedirs(self.base_dir, exist_ok=True)
            with open(self.workspaces_file, 'w') as f:
                json.dump(self.workspaces, f, indent=2)
            self.logger.debug(f"Saved {len(self.workspaces)} workspaces")
        except Exception as e:
            self.logger.error(f"Error saving workspaces: {str(e)}")
            raise WorkspaceError(f"Failed to save workspaces: {str(e)}")
    
    def _generate_workspace_id(self, app_name: str) -> str:
        """Generate unique workspace ID from app name"""
        # Use app name and timestamp for uniqueness
        unique_string = f"{app_name}_{datetime.now().isoformat()}"
        return hashlib.sha256(unique_string.encode()).hexdigest()[:8]
    
    def get_workspace(self, app_name: str, sticky: bool = False) -> str:
        """Get workspace path for app"""
        self.logger.debug(f"Getting workspace for {app_name} (sticky={sticky})")
        
        # For non-sticky apps, always create new workspace
        if not sticky:
            workspace_id = self._generate_workspace_id(app_name)
            workspace_path = str(self.base_dir / workspace_id)
            try:
                os.makedirs(workspace_path, exist_ok=True)
                self.logger.debug(f"Created new workspace: {workspace_path}")
                return workspace_path
            except Exception as e:
                self.logger.error(f"Error creating workspace: {str(e)}")
                raise WorkspaceError(f"Failed to create workspace: {str(e)}")
        
        # For sticky apps, try to find existing workspace
        app_workspaces = {
            k: v for k, v in self.workspaces.items()
            if v["app_name"] == app_name
        }
        
        if app_workspaces:
            # Use most recently accessed workspace
            workspace_id = max(
                app_workspaces.keys(),
                key=lambda k: app_workspaces[k]["last_accessed"]
            )
            workspace_path = str(self.base_dir / workspace_id)
            
            # Update last accessed time
            self.workspaces[workspace_id]["last_accessed"] = datetime.now().isoformat()
            self._save_workspaces()
            
            self.logger.debug(f"Using existing workspace: {workspace_path}")
            return workspace_path
        
        # Create new workspace for sticky app
        workspace_id = self._generate_workspace_id(app_name)
        workspace_path = str(self.base_dir / workspace_id)
        try:
            os.makedirs(workspace_path, exist_ok=True)
            
            # Register workspace
            self.workspaces[workspace_id] = {
                "app_name": app_name,
                "created": datetime.now().isoformat(),
                "last_accessed": datetime.now().isoformat(),
                "sticky": True
            }
            self._save_workspaces()
            
            self.logger.debug(f"Created new sticky workspace: {workspace_path}")
            return workspace_path
        except Exception as e:
            self.logger.error(f"Error creating sticky workspace: {str(e)}")
            raise WorkspaceError(f"Failed to create sticky workspace: {str(e)}")
    
    def cleanup_workspace(self, workspace_path: str) -> None:
        """Clean up workspace if not sticky"""
        workspace_id = Path(workspace_path).name
        workspace = self.workspaces.get(workspace_id)
        
        if workspace and not workspace["sticky"]:
            try:
                # Remove workspace directory
                shutil.rmtree(workspace_path, ignore_errors=True)
                # Remove from registry
                del self.workspaces[workspace_id]
                self._save_workspaces()
                self.logger.debug(f"Cleaned up workspace: {workspace_path}")
            except Exception as e:
                self.logger.error(f"Error cleaning up workspace: {str(e)}")
    
    def cleanup_old_workspaces(self, max_age_days: int = 7) -> None:
        """Clean up old non-sticky workspaces"""
        now = datetime.now()
        cleaned = 0
        for workspace_id, workspace in list(self.workspaces.items()):
            if not workspace["sticky"]:
                last_accessed = datetime.fromisoformat(workspace["last_accessed"])
                age_days = (now - last_accessed).days
                if age_days > max_age_days:
                    workspace_path = self.base_dir / workspace_id
                    self.cleanup_workspace(str(workspace_path))
                    cleaned += 1
        if cleaned:
            self.logger.debug(f"Cleaned up {cleaned} old workspaces")
    
    def get_workspace_info(self, workspace_path: str) -> Optional[Dict[str, Any]]:
        """Get information about a workspace"""
        workspace_id = Path(workspace_path).name
        return self.workspaces.get(workspace_id)
    
    def is_sticky(self, workspace_path: str) -> bool:
        """Check if workspace is sticky"""
        info = self.get_workspace_info(workspace_path)
        return info is not None and info.get("sticky", False)
    
    def get_workspace_age(self, workspace_path: str) -> Optional[int]:
        """Get workspace age in days"""
        info = self.get_workspace_info(workspace_path)
        if info and "last_accessed" in info:
            last_accessed = datetime.fromisoformat(info["last_accessed"])
            age = datetime.now() - last_accessed
            return age.days
        return None

@asynccontextmanager
async def workspace_context(name: str, registry: Optional['ResourceRegistry'] = None):
    """Context manager for workspaces"""
    # Create workspace manager
    manager = WorkspaceManager()
    
    # Get workspace path
    workspace_path = manager.get_workspace(name)
    
    # Create magnetic field for workspace
    field = MagneticField(name, registry)
    
    # Create workspace object
    workspace = Workspace(workspace_path, field)
    
    try:
        yield workspace
    finally:
        # Cleanup non-sticky workspace
        if not manager.is_sticky(workspace_path):
            manager.cleanup_workspace(workspace_path)
