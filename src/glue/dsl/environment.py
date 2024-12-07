# src/glue/dsl/environment.py

"""GLUE Environment Management"""

import os
from typing import Dict, Optional
from pathlib import Path
from dotenv import load_dotenv

class Environment:
    """GLUE Environment Manager"""
    
    def __init__(self):
        self.env_file = None
        self.env_vars = {}
    
    def load(self, env_file: Optional[str] = None) -> Dict[str, str]:
        """Load environment variables"""
        # Try to find .env file
        if env_file:
            self.env_file = Path(env_file)
        else:
            # Look in current and parent directories
            current = Path.cwd()
            while current != current.parent:
                env_path = current / ".env"
                if env_path.exists():
                    self.env_file = env_path
                    break
                current = current.parent
        
        # Load environment variables
        if self.env_file and self.env_file.exists():
            load_dotenv(self.env_file)
            
            # Store loaded variables
            with open(self.env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        self.env_vars[key.strip()] = value.strip()
        
        return self.env_vars
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get environment variable"""
        # Try environment first
        value = os.getenv(key)
        if value is not None:
            return value
            
        # Try loaded variables
        return self.env_vars.get(key, default)
    
    def set(self, key: str, value: str):
        """Set environment variable"""
        os.environ[key] = value
        self.env_vars[key] = value
    
    def require(self, key: str) -> str:
        """Get required environment variable"""
        value = self.get(key)
        if value is None:
            raise ValueError(
                f"Required environment variable {key} not found. "
                f"Please set it in your .env file or environment."
            )
        return value

# Global environment instance
_env = Environment()

def load_env(env_file: Optional[str] = None) -> Dict[str, str]:
    """Load environment variables"""
    return _env.load(env_file)

def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable"""
    return _env.get(key, default)

def set_env(key: str, value: str):
    """Set environment variable"""
    _env.set(key, value)

def require_env(key: str) -> str:
    """Get required environment variable"""
    return _env.require(key)
