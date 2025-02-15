"""Implicit workflow orchestration for GLUE applications"""

from typing import Dict, Set, Any, Optional, List
from datetime import datetime
from prefect import flow, task
from pydantic import BaseModel, Field
from .types import AdhesiveType, ToolResult
from .team import Team, TeamRole
from .model import Model
from .logger import get_logger

logger = get_logger("orchestrator")

# ==================== Pydantic Models ====================
class ToolCapabilities(BaseModel):
    """Tool capabilities and requirements"""
    async_support: bool = Field(default=False, description="Whether tool supports async execution")
    stateful: bool = Field(default=False, description="Whether tool maintains state")
    memory: bool = Field(default=False, description="Whether tool uses memory")
    adhesives: Set[str] = Field(default_factory=set, description="Supported adhesive types")
    parallel_safe: bool = Field(default=True, description="Whether tool can run in parallel")
    dependencies: Set[str] = Field(default_factory=set, description="Required dependencies")
    dynamic: bool = Field(default=False, description="Whether tool is dynamically created")

class TeamCapabilities(BaseModel):
    """Team capabilities analysis"""
    tools: Dict[str, ToolCapabilities] = Field(default_factory=dict, description="Tool capabilities")
    models: Dict[str, Any] = Field(default_factory=dict, description="Model capabilities")
    adhesives: Set[str] = Field(default_factory=set, description="Supported adhesives")
    memory: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Memory capabilities")
    dynamic: bool = Field(default=False, description="Whether team supports dynamic tools")
    parallel_safe: bool = Field(default=True, description="Whether team supports parallel execution")

class MemoryRequirements(BaseModel):
    """Memory requirements for execution"""
    shared: Set[str] = Field(default_factory=set, description="Shared memory types")
    private: Set[str] = Field(default_factory=set, description="Private memory types")
    persistent: Set[str] = Field(default_factory=set, description="Persistent storage needs")
    temporary: Set[str] = Field(default_factory=set, description="Temporary storage needs")

class RoutingStrategy(BaseModel):
    """Result routing configuration"""
    push: Set[str] = Field(default_factory=set, description="Push targets")
    pull: Set[str] = Field(default_factory=set, description="Pull sources")
    broadcast: Set[str] = Field(default_factory=set, description="Broadcast targets")
    direct: Set[str] = Field(default_factory=set, description="Direct routing")

class FallbackStrategy(BaseModel):
    """Fallback handling configuration"""
    type: str = Field(..., description="Type of fallback")
    priority: int = Field(..., description="Priority level")
    config: Dict[str, Any] = Field(default_factory=dict, description="Additional configuration")

class ExecutionStrategy(BaseModel):
    """Complete execution strategy"""
    parallel: bool = Field(default=False, description="Whether to execute in parallel")
    memory: MemoryRequirements = Field(default_factory=MemoryRequirements, description="Memory requirements")
    routing: RoutingStrategy = Field(default_factory=RoutingStrategy, description="Routing strategy")
    fallbacks: List[FallbackStrategy] = Field(default_factory=list, description="Fallback strategies")
    adhesives: Dict[str, Set[str]] = Field(default_factory=dict, description="Adhesive requirements")
    dynamic: bool = Field(default=False, description="Whether to allow dynamic creation")

class AnalysisResult(BaseModel):
    """Complete analysis result"""
    tools: Set[str] = Field(default_factory=set, description="Required tools")
    dependencies: Dict[str, Set[str]] = Field(default_factory=dict, description="Tool dependencies")
    relationships: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Team relationships")
    strategy: Dict[str, ExecutionStrategy] = Field(default_factory=dict, description="Execution strategies")

class WorkflowContext(BaseModel):
    class Config:
        arbitrary_types_allowed = True
    """Context for workflow execution"""
    prompt: str = Field(..., description="The prompt to execute")
    teams: Dict[str, Team] = Field(..., description="Available teams")
    tools: Dict[str, Set[str]] = Field(..., description="Team to tool names mapping")
    models: Dict[str, Model] = Field(..., description="Available models")
    adhesives: Dict[str, Set[AdhesiveType]] = Field(..., description="Model to adhesive types mapping")
    timestamp: datetime = Field(default_factory=datetime.now, description="Execution timestamp")

class ExecutionStep(BaseModel):
    """Single step in execution plan"""
    team: str = Field(..., description="Team executing this step")
    tools: Set[str] = Field(default_factory=set, description="Tools to execute")
    parallel: bool = Field(default=False, description="Whether tools can run in parallel")
    memory: Dict[str, Any] = Field(default_factory=dict, description="Memory requirements")
    routing: Dict[str, Any] = Field(default_factory=dict, description="Result routing strategy")
    fallbacks: List[Dict[str, Any]] = Field(default_factory=list, description="Fallback strategies")
    requires: Set[str] = Field(default_factory=set, description="Required teams")

class ExecutionPlan(BaseModel):
    """Complete execution plan"""
    steps: List[ExecutionStep] = Field(default_factory=list, description="Ordered execution steps")
    dependencies: Dict[str, Set[str]] = Field(default_factory=dict, description="Team dependencies")
    strategy: Dict[str, Any] = Field(default_factory=dict, description="Global execution strategy")

class GlueOrchestrator:
    """
    Implicit workflow orchestrator that:
    1. Routes prompts to appropriate teams based on tool requirements
    2. Manages cross-team data flow
    3. Handles tool dependencies
    4. Ensures proper execution order
    
    This is completely invisible to users - they just write normal GLUE apps
    and the orchestrator handles the complexity automatically.
    """
    
    def __init__(self):
        self._tool_mapping: Dict[str, str] = {}  # tool_name -> team_name
        self._team_tools: Dict[str, Set[str]] = {}  # team_name -> tool_names
        self._active_flows: Dict[str, WorkflowContext] = {}
        
    def register_team(self, team: Team) -> None:
        """Register a team and its tools"""
        self._team_tools[team.name] = set()
        for tool_name in team.tools:
            self._tool_mapping[tool_name] = team.name
            self._team_tools[team.name].add(tool_name)
            
    @task(retries=3, retry_delay_seconds=10)
    async def _execute_tool(
        self,
        team: Team,
        tool_name: str,
        input_data: Any,
        adhesive: AdhesiveType
    ) -> ToolResult:
        """Execute a tool with proper team context"""
        # Get model with tool access
        model = next(
            (m for m in team.models.values() if tool_name in m._tools),
            None
        )
        if not model:
            raise ValueError(f"No model in team {team.name} has access to {tool_name}")
            
        # Execute tool
        return await model.use_tool(tool_name, adhesive, input_data)
        
    @task
    async def _share_result(
        self,
        source_team: Team,
        target_team: Team,
        result: ToolResult
    ) -> None:
        """Share result between teams"""
        await source_team.push_to(target_team, {result.tool_name: result})
        
    @flow
    async def execute_prompt(self, prompt: str, app_context: Dict[str, Any]) -> str:
        """
        Execute a prompt with automatic workflow orchestration.
        
        This:
        1. Analyzes prompt for required tools
        2. Routes to appropriate teams
        3. Manages data flow between teams
        4. Ensures proper execution order
        5. Handles errors and retries
        """
        try:
            # Create and validate workflow context
            context = WorkflowContext(
                prompt=prompt,
                teams=app_context["teams"],
                tools=self._team_tools,
                models=app_context["models"],
                adhesives=app_context["adhesives"]
            )
            
            # Analyze prompt for tool requirements
            required_tools = await self._analyze_tool_requirements(prompt, context)
            
            # Map tools to teams
            team_tasks = {}
            for tool_name in required_tools.tools:
                team_name = self._tool_mapping.get(tool_name)
                if not team_name:
                    continue
                if team_name not in team_tasks:
                    team_tasks[team_name] = set()
                team_tasks[team_name].add(tool_name)
            
            # Create and validate execution plan
            plan = ExecutionPlan(
                steps=[],
                dependencies=required_tools.dependencies,
                strategy=required_tools.strategy
            )
            
            # Build execution steps
            execution_steps = await self._create_execution_plan(
                team_tasks,
                context
            )
            
            # Validate and add steps to plan
            plan.steps = [
                ExecutionStep(**step) for step in execution_steps
            ]
            
            # Execute plan
            results = []
            for step in plan.steps:
                result = await self._execute_step(step, context)
                results.append(result)
                
            # Combine results
            return await self._combine_results(results, context)
            
        except Exception as e:
            # Log the error
            logger.error(f"Error executing prompt: {str(e)}")
            raise RuntimeError(f"Failed to execute prompt: {str(e)}")
        
    async def _analyze_tool_requirements(self, prompt: str, context: WorkflowContext) -> AnalysisResult:
        """
        Analyze prompt to determine required tools, dependencies, and execution strategy.
        Uses SmolAgents for initial parsing but adds sophisticated analysis.
        """
        from ..tools.executor import SmolAgentsToolExecutor
        from ..magnetic.field import MagneticField
        
        # Get initial tool intent using first available team
        first_team = next(iter(self._team_tools.keys()), None)
        if not first_team or first_team not in context.teams:
            return AnalysisResult()
            
        team = context.teams[first_team]
        executor = SmolAgentsToolExecutor(
            team=team,
            available_adhesives=set().union(*(
                m.available_adhesives 
                for m in team.models.values()
            ))
        )
        intent = await executor._parse_tool_intent(prompt)
        
        # Analyze dependencies and relationships
        dependencies = {}
        relationships = {}
        execution_strategy = {}
        
        for team_name, team in self._team_tools.items():
            # Analyze team capabilities
            capabilities = self._analyze_team_capabilities(team)
            
            # Check tool dependencies
            for tool in team:
                deps = self._get_tool_dependencies(tool)
                if deps:
                    dependencies[tool] = deps
                    
            # Check magnetic relationships
            field = MagneticField.get_field(team_name)
            if field:
                relationships[team_name] = field.get_relationships()
                
            # Determine execution strategy
            strategy = self._determine_strategy(
                team,
                capabilities,
                dependencies,
                relationships
            )
            execution_strategy[team_name] = strategy
            
        return AnalysisResult(
            tools={intent.tool_name} if intent else set(),
            dependencies=dependencies,
            relationships=relationships,
            strategy=execution_strategy
        )
        
    def _analyze_team_capabilities(self, team: Set[str]) -> TeamCapabilities:
        """Analyze what a team can do based on its tools and models"""
        from ..tools.base import BaseTool
        from ..tools.dynamic_tool_factory import DynamicToolFactory
        
        team_caps = TeamCapabilities()
        
        for tool_name in team:
            # Get tool class
            tool_cls = DynamicToolFactory.get_tool_class(tool_name)
            if not tool_cls:
                continue
                
            # Create and validate tool capabilities
            tool_caps = ToolCapabilities(
                async_support=hasattr(tool_cls, "aexecute"),
                stateful=hasattr(tool_cls, "state"),
                memory=hasattr(tool_cls, "memory"),
                adhesives=getattr(tool_cls, "supported_adhesives", set()),
                parallel_safe=getattr(tool_cls, "parallel_safe", True),
                dependencies=getattr(tool_cls, "dependencies", set()),
                dynamic=issubclass(tool_cls, DynamicToolFactory)
            )
            
            # Add tool capabilities
            team_caps.tools[tool_name] = tool_caps
            team_caps.dynamic |= tool_caps.dynamic
            team_caps.parallel_safe &= tool_caps.parallel_safe
            
            # Track memory capabilities
            if tool_caps.memory:
                team_caps.memory[tool_name] = {
                    "type": getattr(tool_cls, "memory_type", None),
                    "shared": getattr(tool_cls, "shared_memory", False)
                }
                
            # Track adhesive support
            if tool_caps.adhesives:
                team_caps.adhesives.update(tool_caps.adhesives)
                
        return team_caps
        
    def _get_tool_dependencies(self, tool_name: str) -> Set[str]:
        """Get complete tool dependencies including dynamic ones"""
        from ..tools.base import BaseTool
        from ..tools.dynamic_tool_factory import DynamicToolFactory
        
        deps = set()
        
        # Get tool class
        tool_cls = DynamicToolFactory.get_tool_class(tool_name)
        if not tool_cls:
            return deps
            
        # Get static dependencies
        deps.update(getattr(tool_cls, "dependencies", set()))
        
        # Get dynamic dependencies
        if issubclass(tool_cls, DynamicToolFactory):
            dynamic_deps = tool_cls.get_dynamic_dependencies()
            deps.update(dynamic_deps)
            
        # Get memory dependencies
        if hasattr(tool_cls, "memory"):
            memory_type = getattr(tool_cls, "memory_type", None)
            if memory_type:
                deps.add(f"memory.{memory_type}")
                
        # Get adhesive dependencies
        adhesives = getattr(tool_cls, "supported_adhesives", set())
        for adhesive in adhesives:
            deps.add(f"adhesive.{adhesive.name}")
            
        return deps
        
    def _determine_strategy(
        self,
        team: Set[str],
        capabilities: TeamCapabilities,
        dependencies: Dict[str, Set[str]],
        relationships: Dict[str, Any]
    ) -> ExecutionStrategy:
        """Determine optimal execution strategy"""
        from ..magnetic.rules import MagneticRules
        
        # Create base strategy with validated components
        strategy = ExecutionStrategy(
            parallel=self._can_execute_parallel(team, capabilities),
            memory=MemoryRequirements(**self._memory_requirements(capabilities)),
            routing=RoutingStrategy(**self._determine_routing(capabilities, relationships)),
            fallbacks=[
                FallbackStrategy(**fallback)
                for fallback in self._determine_fallbacks(capabilities)
            ],
            adhesives=self._determine_adhesives(capabilities),
            dynamic=capabilities.dynamic
        )
        
        # Apply magnetic rules
        rule_set = MagneticRules.get_rules()
        for rule in rule_set.rules:
            rule.apply(strategy.dict(), capabilities.dict(), relationships)
            
        return strategy
        
    async def _create_execution_plan(
        self,
        team_tasks: Dict[str, Set[str]],
        context: WorkflowContext
    ) -> List[Dict[str, Any]]:
        """Create dynamic execution plan based on analysis"""
        # Get full analysis
        analysis = await self._analyze_tool_requirements(context.prompt, context)
        
        # Build DAG of dependencies
        dag = self._build_dependency_dag(
            team_tasks,
            analysis.dependencies
        )
        
        # Optimize execution plan
        plan = self._optimize_plan(
            dag,
            analysis.strategy,
            context
        )
        
        return plan
        
    def _build_dependency_dag(
        self,
        team_tasks: Dict[str, Set[str]],
        dependencies: Dict[str, Set[str]]
    ) -> Dict[str, Any]:
        """Build directed acyclic graph of dependencies"""
        from collections import defaultdict
        
        # Build graph
        graph = defaultdict(set)
        for team, tools in team_tasks.items():
            for tool in tools:
                deps = dependencies.get(tool, set())
                for dep in deps:
                    # Find team with dependency
                    dep_team = self._tool_mapping.get(dep)
                    if dep_team:
                        graph[team].add(dep_team)
                        
        return dict(graph)
        
    def _optimize_plan(
        self,
        dag: Dict[str, Set[str]],
        strategy: Dict[str, Any],
        context: WorkflowContext
    ) -> List[Dict[str, Any]]:
        """Create optimized execution plan"""
        from collections import deque
        
        # Topological sort for dependencies
        sorted_teams = self._topological_sort(dag)
        
        # Create optimized plan
        plan = []
        for team in sorted_teams:
            if team not in context.teams:
                continue
                
            team_strategy = strategy.get(team, {})
            step = {
                "team": team,
                "tools": context.tools.get(team, set()),
                "parallel": team_strategy.get("parallel", False),
                "memory": team_strategy.get("memory", {}),
                "routing": team_strategy.get("routing", {}),
                "fallbacks": team_strategy.get("fallbacks", []),
                "requires": dag.get(team, set())
            }
            plan.append(step)
            
        return plan
        
    def _topological_sort(self, dag: Dict[str, Set[str]]) -> List[str]:
        """Topologically sort teams based on dependencies"""
        from collections import deque
        
        # Calculate in-degrees
        in_degree = {node: 0 for node in dag}
        for node in dag:
            for neighbor in dag[node]:
                in_degree[neighbor] = in_degree.get(neighbor, 0) + 1
                
        # Initialize queue with nodes having no dependencies
        queue = deque([node for node, degree in in_degree.items() if degree == 0])
        
        result = []
        while queue:
            node = queue.popleft()
            result.append(node)
            
            # Update in-degrees
            for neighbor in dag.get(node, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
                    
        return result
        
    def _can_execute_parallel(self, team: Set[str], capabilities: TeamCapabilities) -> bool:
        """Check if tools can be executed in parallel"""
        if not capabilities.parallel_safe:
            return False
            
        # Check tool interactions
        for tool_name, tool_caps in capabilities.tools.items():
            if not tool_caps.parallel_safe:
                return False
                
            # Check memory interactions
            if tool_caps.memory and tool_name in capabilities.memory:
                memory_info = capabilities.memory[tool_name]
                if memory_info.get("shared", False):
                    return False
                    
        return True
        
    def _memory_requirements(self, capabilities: TeamCapabilities) -> Dict[str, Any]:
        """Determine memory requirements"""
        requirements = MemoryRequirements()
        
        for tool_name, memory_info in capabilities.memory.items():
            memory_type = memory_info.get("type")
            if not memory_type:
                continue
                
            if memory_info.get("shared", False):
                requirements.shared.add(memory_type)
            else:
                requirements.private.add(memory_type)
                
            if memory_type in {"vector", "knowledge_base"}:
                requirements.persistent.add(tool_name)
            else:
                requirements.temporary.add(tool_name)
                
        return requirements.dict()
        
    def _determine_routing(
        self,
        capabilities: TeamCapabilities,
        relationships: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Determine result routing strategy"""
        routing = RoutingStrategy()
        
        # Check relationship types
        for team, rel in relationships.items():
            if rel.get("bidirectional"):
                routing.broadcast.add(team)
            elif rel.get("pull_enabled"):
                routing.pull.add(team)
            else:
                routing.push.add(team)
                
        # Check tool routing needs
        for tool_name, tool_caps in capabilities.tools.items():
            if tool_name in capabilities.memory and capabilities.memory[tool_name].get("shared", False):
                routing.broadcast.add(tool_name)
            else:
                routing.direct.add(tool_name)
                
        return routing.dict()
        
    def _determine_fallbacks(self, capabilities: TeamCapabilities) -> List[Dict[str, Any]]:
        """Determine fallback strategies"""
        fallbacks = []
        
        # Add dynamic tool creation fallback if supported
        if capabilities.dynamic:
            fallbacks.append(FallbackStrategy(
                type="dynamic_creation",
                priority=1
            ).dict())
            
        # Add memory fallbacks
        memory_reqs = self._memory_requirements(capabilities)
        if memory_reqs["persistent"]:
            fallbacks.append(FallbackStrategy(
                type="persistent_memory",
                priority=2
            ).dict())
            
        # Add routing fallbacks
        routing = self._determine_routing(capabilities, {})
        if routing["broadcast"]:
            fallbacks.append(FallbackStrategy(
                type="broadcast_retry",
                priority=3
            ).dict())
            
        return sorted(fallbacks, key=lambda x: x["priority"])
        
    def _determine_adhesives(self, capabilities: TeamCapabilities) -> Dict[str, Set[str]]:
        """Determine optimal adhesive usage"""
        usage = {
            "required": set(),
            "optional": set(),
            "forbidden": set()
        }
        
        for tool_name, tool_caps in capabilities.tools.items():
            # Check required adhesives
            if tool_name in capabilities.memory and capabilities.memory[tool_name].get("shared", False):
                usage["required"].update(
                    a for a in tool_caps.adhesives 
                    if a in {"GLUE", "VELCRO"}
                )
            else:
                usage["optional"].update(tool_caps.adhesives)
                
            # Check forbidden adhesives
            if not tool_caps.parallel_safe:
                usage["forbidden"].add("TAPE")
                
        return usage
        
    async def _setup_step_context(self, step: Dict[str, Any], team: Team) -> None:
        """Set up execution context for a step"""
        # Initialize memory if needed
        memory_reqs = step["memory"]
        if memory_reqs["persistent"]:
            await team.initialize_memory(memory_reqs["persistent"])
            
        # Set up routing
        routing = step["routing"]
        if routing["broadcast"]:
            await team.enable_broadcasting()
            
    async def _handle_dependencies(
        self,
        step: Dict[str, Any],
        team: Team,
        context: WorkflowContext
    ) -> None:
        """Handle step dependencies"""
        for req_team in step["requires"]:
            target = context.teams[req_team]
            
            # Handle memory dependencies
            if step["memory"]["shared"]:
                await target.share_memory(team)
                
            # Handle result dependencies
            await target.share_results_with(team)
            
    async def _execute_step(
        self,
        step: ExecutionStep,
        context: WorkflowContext
    ) -> Dict[str, Any]:
        """Execute a single step in the execution plan"""
        try:
            # Get team for this step
            team = context.teams[step.team]
            
            # Set up step context
            await self._setup_step_context(step.dict(), team)
            
            # Handle dependencies
            await self._handle_dependencies(step.dict(), team, context)
            
            # Execute tools
            if step.parallel:
                results = await self._execute_parallel(step.dict(), team, context)
            else:
                results = await self._execute_sequential(step.dict(), team, context)
                
            # Handle results
            await self._handle_results(step.dict(), results, team)
            
            return {
                "team": step.team,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error executing step {step.team}: {str(e)}")
            raise RuntimeError(f"Step execution failed: {str(e)}")

    async def _execute_parallel(
        self,
        step: Dict[str, Any],
        team: Team,
        context: WorkflowContext
    ) -> Dict[str, Any]:
        """Execute tools in parallel"""
        import asyncio
        
        tasks = []
        for tool_name in step["tools"]:
            model = self._get_tool_model(team, tool_name)
            if model:
                adhesive = self._get_optimal_adhesive(
                    model,
                    step["adhesives"]
                )
                task = self._execute_tool(
                    team,
                    tool_name,
                    context.prompt,
                    adhesive
                )
                tasks.append(task)
                
        results = await asyncio.gather(*tasks)
        return {
            t.tool_name: t for t in results
        }
        
    async def _execute_sequential(
        self,
        step: Dict[str, Any],
        team: Team,
        context: WorkflowContext
    ) -> Dict[str, Any]:
        """Execute tools sequentially"""
        results = {}
        for tool_name in step["tools"]:
            model = self._get_tool_model(team, tool_name)
            if model:
                adhesive = self._get_optimal_adhesive(
                    model,
                    step["adhesives"]
                )
                result = await self._execute_tool(
                    team,
                    tool_name,
                    context.prompt,
                    adhesive
                )
                results[tool_name] = result
                
        return results
        
    async def _handle_results(
        self,
        step: Dict[str, Any],
        results: Dict[str, Any],
        team: Team
    ) -> None:
        """Handle step results based on routing strategy"""
        routing = step["routing"]
        
        # Handle broadcasts
        if routing["broadcast"]:
            await team.broadcast_results(results)
            return
            
        # Handle direct routing
        for tool_name in routing["direct"]:
            if tool_name in results:
                await team.handle_result(
                    tool_name,
                    results[tool_name]
                )
                
    def _get_tool_model(self, team: Team, tool_name: str) -> Optional[Model]:
        """Get model with access to tool"""
        return next(
            (m for m in team.models.values() if tool_name in m._tools),
            None
        )
        
    def _get_optimal_adhesive(
        self,
        model: Model,
        adhesive_info: Dict[str, Set[str]]
    ) -> AdhesiveType:
        """Get optimal adhesive based on requirements"""
        # Try required adhesives first
        for adhesive in model.available_adhesives:
            if adhesive.name in adhesive_info["required"]:
                return adhesive
                
        # Try optional adhesives
        for adhesive in model.available_adhesives:
            if (adhesive.name in adhesive_info["optional"] and
                adhesive.name not in adhesive_info["forbidden"]):
                return adhesive
                
        # Default to first available
        return next(iter(model.available_adhesives))
        
    async def _combine_results(
        self,
        results: List[Dict[str, Any]],
        context: WorkflowContext
    ) -> str:
        """Combine results into final response"""
        # Use last team's model to combine results
        if not results:
            return "Error: No results generated during prompt execution"
            
        last_step = results[-1]
        team = context.teams[last_step["team"]]
        model = next(iter(team.models.values()))
        
        # Format results for model
        formatted = "\n\n".join([
            f"Team {r['team']} results:\n" + 
            "\n".join(f"- {t}: {res.result}" 
                     for t, res in r["results"].items())
            for r in results
        ])
        
        # Let model generate final response
        return await model.generate(
            f"Based on these results:\n\n{formatted}\n\n"
            f"Generate a complete response to: {context.prompt}"
        )
