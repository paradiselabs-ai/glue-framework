"""Base tool implementation with Pydantic models and SmolAgents integration"""

from typing import Dict, Any, Optional, List, Union, Callable, ClassVar
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from prefect import task, flow

from ..core.logger import log_tool_event, ToolLogContext
from ..core.errors import ToolError, error_handler, ErrorSeverity
from ..core.types import AdhesiveType, ToolResult
from ..core.pydantic_models import SmolAgentsTool

class ToolConfig(BaseModel):
    """Tool configuration with validation"""
    required_permissions: List[str] = Field(default_factory=list)
    timeout: float = Field(default=30.0, gt=0)
    retry_count: int = Field(default=3, ge=0)
    cache_results: bool = Field(default=True)
    tool_specific_config: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

class ToolState(BaseModel):
    """Tool state tracking"""
    name: str
    active: bool = Field(default=True)
    last_used: Optional[datetime] = None
    call_count: int = Field(default=0)
    error_count: int = Field(default=0)
    average_latency: float = Field(default=0.0)
    cache: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(arbitrary_types_allowed=True)

class BaseTool(BaseModel):
    """
    Enhanced base tool implementation with Pydantic validation,
    SmolAgents integration, and Prefect orchestration.
    """
    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    config: ToolConfig = Field(default_factory=ToolConfig)
    state: ToolState = Field(default=None)
    smol_tool_instance: Optional[SmolAgentsTool] = Field(default=None)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, **data):
        super().__init__(**data)
        if not self.state:
            self.state = ToolState(name=self.name)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not v.isidentifier():
            raise ValueError(f"Invalid tool name: {v}. Must be a valid Python identifier")
        return v

    async def initialize(self) -> None:
        """Initialize tool resources"""
        log_tool_event(
            ToolLogContext(
                component="tool",
                action="initialize",
                tool_name=self.name,
                adhesive_type="none"
            ),
            f"Initializing tool: {self.name}"
        )

    async def cleanup(self) -> None:
        """Clean up tool resources"""
        log_tool_event(
            ToolLogContext(
                component="tool",
                action="cleanup",
                tool_name=self.name,
                adhesive_type="none"
            ),
            f"Cleaning up tool: {self.name}"
        )

    @error_handler
    async def execute(self, input_data: Any) -> Any:
        """
        Execute tool with error handling and logging.
        Override this in subclasses.
        """
        raise NotImplementedError("Tool must implement execute method")

    @error_handler
    async def _execute_with_adhesive(
        self,
        adhesive_type: AdhesiveType,
        input_data: Any,
        team_name: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> ToolResult:
        """Execute tool with adhesive binding and tracking"""
        start_time = datetime.now()

        try:
            # Log execution start
            log_tool_event(
                ToolLogContext(
                    component="tool",
                    action="execute",
                    tool_name=self.name,
                    adhesive_type=adhesive_type.value,
                    team_name=team_name,
                    model_name=model_name
                ),
                f"Executing tool: {self.name}"
            )

            # Check cache if enabled
            cache_key = str(input_data)
            if self.config.cache_results and cache_key in self.state.cache:
                result = self.state.cache[cache_key]
                log_tool_event(
                    ToolLogContext(
                        component="tool",
                        action="cache_hit",
                        tool_name=self.name,
                        adhesive_type=adhesive_type.value
                    ),
                    "Using cached result"
                )
            else:
                # Execute tool
                result = await self.execute(input_data)

                # Cache result if enabled
                if self.config.cache_results:
                    self.state.cache[cache_key] = result

            # Update metrics
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.state.call_count += 1
            self.state.last_used = end_time
            self.state.average_latency = (
                (self.state.average_latency * (self.state.call_count - 1) + duration)
                / self.state.call_count
            )

            # Create tool result
            tool_result = ToolResult(
                tool_name=self.name,
                result=result,
                adhesive=adhesive_type,
                timestamp=end_time,
                metadata={
                    "duration": duration,
                    "team_name": team_name,
                    "model_name": model_name
                }
            )

            log_tool_event(
                ToolLogContext(
                    component="tool",
                    action="success",
                    tool_name=self.name,
                    adhesive_type=adhesive_type.value
                ),
                f"Tool execution successful: {self.name}"
            )

            return tool_result

        except Exception as e:
            # Update error metrics
            self.state.error_count += 1
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            # Log error with context
            raise ToolError(
                message=str(e),
                tool_name=self.name,
                adhesive_type=adhesive_type.value,
                team_name=team_name,
                severity=ErrorSeverity.ERROR,
                metadata={
                    "duration": duration,
                    "input_data": str(input_data),
                    "error_count": self.state.error_count
                }
            ) from e

    @property
    def smol_tool(self) -> SmolAgentsTool:
        """Get SmolAgents tool wrapper"""
        if not self.smol_tool_instance:
            self.smol_tool_instance = SmolAgentsTool(
                name=self.name,
                description=self.description,
                inputs={
                    "input": {
                        "type": "string",
                        "description": "Tool input"
                    }
                },
                output_type="string",
                forward_func=self.execute
            )
        return self.smol_tool_instance

    def get_metrics(self) -> Dict[str, Any]:
        """Get tool performance metrics"""
        return {
            "name": self.name,
            "active": self.state.active,
            "call_count": self.state.call_count,
            "error_count": self.state.error_count,
            "error_rate": (
                self.state.error_count / self.state.call_count
                if self.state.call_count > 0
                else 0
            ),
            "average_latency": self.state.average_latency,
            "last_used": self.state.last_used,
            "cache_size": len(self.state.cache)
        }

    # Validate tool input - override in subclasses for specific validation
    validate_input: ClassVar[Callable] = task()(lambda self, input_data: None)

    # Validate tool output - override in subclasses for specific validation
    validate_output: ClassVar[Callable] = task()(lambda self, output_data: None)

    @flow(name="tool_execution")
    async def __call__(
        self,
        adhesive_type: AdhesiveType,
        input_data: Any,
        team_name: Optional[str] = None,
        model_name: Optional[str] = None
    ) -> ToolResult:
        """Execute tool with Prefect flow"""
        # Validate input
        await self.validate_input(input_data)

        # Execute with adhesive
        result = await self._execute_with_adhesive(
            adhesive_type,
            input_data,
            team_name,
            model_name
        )

        # Validate output
        await self.validate_output(result.result)

        return result
