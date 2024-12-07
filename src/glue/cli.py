# src/glue/cli.py

"""GLUE Command Line Interface"""

import sys
import asyncio
from pathlib import Path
from typing import Optional
from glue.dsl import parse_glue_file, execute_glue_app, load_env

async def run_glue_app(file_path: str):
    """Run GLUE application"""
    # Load environment
    load_env()
    
    # Parse GLUE file
    app = parse_glue_file(file_path)
    
    # Execute application
    result = await execute_glue_app(app)
    print(f"Application completed: {result}")

def main():
    """Main CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: glue <app.glue>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    if not Path(file_path).exists():
        print(f"Error: File {file_path} not found")
        sys.exit(1)
    
    asyncio.run(run_glue_app(file_path))

if __name__ == "__main__":
    main()
