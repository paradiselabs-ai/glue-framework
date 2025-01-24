# Contributing to GLUE Framework

We love your input! We want to make contributing to GLUE as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Development Process

We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

1. Fork the repo and create your branch from `main`
2. If you've added code that should be tested, add tests
3. If you've changed APIs, update the documentation
4. Ensure the test suite passes
5. Make sure your code lints
6. Issue that pull request!

## Any Contributions You Make Will Be Under the MIT License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](LICENSE) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report Bugs Using GitHub's [Issue Tracker](../../issues)

We use GitHub issues to track public bugs. Report a bug by [opening a new issue](../../issues/new); it's that easy!

## Write Bug Reports with Detail, Background, and Sample Code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## Use a Consistent Coding Style

* Use 4 spaces for indentation
* Use type hints for Python code
* Keep lines under 100 characters
* Sort imports with isort
* Format code with black

## Adding New Tools

1. Create a new tool class in `src/glue/tools/`
2. Inherit from `SimpleBaseTool`
3. Implement required methods
4. Add tests in `tests/tools/`
5. Update documentation

Example:
```python
from glue.tools.simple_base import SimpleBaseTool, ToolConfig, ToolPermission

class CustomTool(SimpleBaseTool):
    def __init__(
        self,
        name: str = "custom_tool",
        description: str = "Custom tool description",
        **config
    ):
        super().__init__(
            name=name,
            description=description,
            config=ToolConfig(
                required_permissions=[ToolPermission.READ],
                timeout=30.0
            )
        )
        self.config = config

    async def _execute(self, *args, **kwargs) -> Any:
        """Tool implementation"""
        pass
```

## Adding New Model Providers

1. Create a new provider in `src/glue/providers/`
2. Inherit from `BaseProvider`
3. Implement required methods
4. Add tests in `tests/providers/`
5. Update documentation

Example:
```python
from glue.providers.base import BaseProvider

class CustomProvider(BaseProvider):
    def __init__(self, api_key: str, **config):
        super().__init__(api_key=api_key, **config)
        
    async def generate(self, prompt: str) -> str:
        """Generate response"""
        pass
```

## Documentation

### Core Documentation
- Update relevant files in `docs/framework/`
- Keep examples up to date
- Add new sections as needed

### Code Documentation
- Add docstrings to all public methods
- Include type hints
- Explain complex logic
- Update README if needed

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/path/to/test_file.py

# Run with coverage
pytest --cov=glue
```

### Writing Tests
- Create test files in appropriate directories
- Use descriptive test names
- Test edge cases
- Add fixtures as needed

Example:
```python
import pytest
from glue.tools import CustomTool

def test_custom_tool_execution():
    tool = CustomTool()
    result = await tool.execute("test input")
    assert result is not None
```

## License
By contributing, you agree that your contributions will be licensed under its MIT License.
