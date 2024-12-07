# examples/code_generator.py

"""Example: Code Generator using GLUE Expression Language"""

from src.glue.expressions import glue_app, field, magnetize
from src.glue.tools.code_interpreter import CodeInterpreterTool
from src.glue.tools.file_handler import FileHandlerTool

@glue_app("code_generator")
async def generate_code(spec: str, output_file: str = "generated_code.py"):
    """Generate code from specification and save it"""
    async with field("workspace"):
        # Create tools with specific configurations
        tools = magnetize({
            "interpreter": CodeInterpreterTool(
                name="interpreter",
                description="Code generator",
                strength="strong",
                supported_languages=["python"]
            ),
            "file": FileHandlerTool(
                name="file",
                description="File handler",
                strength="medium"
            )
        })
        
        # Create code generation chain
        chain = (
            tools["interpreter"]  # Generate code
            >> tools["file"]      # Save code
        )
        
        # Execute code generation
        result = await chain({
            "code": spec,
            "language": "python",
            "output_file": output_file
        })
        
        return result

# Example usage
if __name__ == "__main__":
    import asyncio
    
    # Example specification for a simple class
    SPEC = """
class Calculator:
    def __init__(self):
        self.value = 0
    
    def add(self, x):
        self.value += x
        return self.value
    
    def subtract(self, x):
        self.value -= x
        return self.value
    
    def get_value(self):
        return self.value
"""
    
    async def main():
        result = await generate_code(
            spec=SPEC,
            output_file="calculator.py"
        )
        print(f"Code generation completed: {result}")
    
    asyncio.run(main())
