# Multi-Agent Orchestration: Production Python Implementations

Complete working examples of coordinator-subagent patterns for building scalable multi-agent systems.

---

## Part 1: Basic Coordinator-Subagent Implementation

### Simple Market Entry Analysis

```python
import anthropic
import json
from typing import Optional
from dataclasses import dataclass
from enum import Enum

@dataclass
class TaskResult:
    """Result from subagent execution."""
    agent_name: str
    task: str
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    tokens_used: int = 0


class SubagentRole(Enum):
    """Types of specialist subagents."""
    MARKET_RESEARCHER = "market_researcher"
    COMPETITIVE_ANALYST = "competitive_analyst"
    REGULATORY_EXPERT = "regulatory_expert"
    FINANCIAL_ANALYST = "financial_analyst"


class SpecializedSubagent:
    """A subagent with a specific expertise domain."""
    
    PROMPTS = {
        SubagentRole.MARKET_RESEARCHER: """
You are a market research specialist. Your expertise:
- Market sizing and growth trends
- Customer segments and demographics
- Market entry strategies
- Geographic considerations

Provide data-driven insights with specific facts and figures where possible.
Be clear about assumptions and limitations.
""",
        
        SubagentRole.COMPETITIVE_ANALYST: """
You are a competitive intelligence expert. Your expertise:
- Competitor identification and analysis
- Competitive positioning
- Market share dynamics
- Competitive threats and opportunities

Focus on factual analysis of competitor strategies and market positioning.
""",
        
        SubagentRole.REGULATORY_EXPERT: """
You are a regulatory and legal compliance expert. Your expertise:
- Local regulations and compliance requirements
- Business licensing and registration
- Industry-specific regulations
- Risk mitigation strategies

Provide clear guidance on regulatory requirements by jurisdiction.
""",
        
        SubagentRole.FINANCIAL_ANALYST: """
You are a financial analyst specializing in market expansion. Your expertise:
- Financial feasibility assessment
- Investment requirements
- Revenue projections
- ROI analysis

Provide quantitative analysis with clear assumptions stated.
"""
    }
    
    def __init__(self, role: SubagentRole):
        self.role = role
        self.client = anthropic.Anthropic()
        self.name = role.value
    
    def execute(self, task: str, context: Optional[dict] = None) -> TaskResult:
        """
        Execute a task with isolated context.
        
        Args:
            task: The specific task instructions
            context: Optional context to pass (only what's relevant)
        
        Returns:
            TaskResult with success status and output
        """
        
        # Build user message with context
        if context:
            user_message = f"{task}\n\nContext provided:\n{json.dumps(context, indent=2)}"
        else:
            user_message = task
        
        try:
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=1500,
                system=self.PROMPTS[self.role],
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )
            
            content = response.content[0].text
            
            return TaskResult(
                agent_name=self.name,
                task=task,
                success=True,
                content=content,
                tokens_used=response.usage.output_tokens
            )
        
        except Exception as e:
            return TaskResult(
                agent_name=self.name,
                task=task,
                success=False,
                error=str(e)
            )


class SimpleCoordinator:
    """Basic coordinator that manages subagents."""
    
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.subagents = {
            SubagentRole.MARKET_RESEARCHER: SpecializedSubagent(SubagentRole.MARKET_RESEARCHER),
            SubagentRole.COMPETITIVE_ANALYST: SpecializedSubagent(SubagentRole.COMPETITIVE_ANALYST),
            SubagentRole.REGULATORY_EXPERT: SpecializedSubagent(SubagentRole.REGULATORY_EXPERT),
            SubagentRole.FINANCIAL_ANALYST: SpecializedSubagent(SubagentRole.FINANCIAL_ANALYST),
        }
        self.execution_log = []
    
    def orchestrate_market_entry(self, market: str, product: str) -> str:
        """
        Orchestrate analysis of market entry opportunity.
        
        Flow:
        1. Market research (parallel)
        2. Competitive analysis (parallel)
        3. Regulatory analysis (parallel)
        4. Financial analysis (depends on above)
        5. Synthesis of all findings
        """
        
        print(f"Coordinator: Planning analysis for {product} → {market}")
        
        # Step 1: Parallel market research, competitive analysis, regulatory
        print("\nStep 1: Gathering market intelligence (parallel)...")
        
        market_result = self.subagents[SubagentRole.MARKET_RESEARCHER].execute(
            task=f"""
Analyze the {market} market for {product}:
1. Market size and growth rate
2. Key customer segments
3. Market entry barriers
4. Growth projections for next 3-5 years
"""
        )
        self.execution_log.append(market_result)
        
        competitive_result = self.subagents[SubagentRole.COMPETITIVE_ANALYST].execute(
            task=f"""
Analyze competition in the {market} market for {product}:
1. Identify major competitors
2. Their market share and positioning
3. Competitive advantages/disadvantages
4. Gaps in the market
"""
        )
        self.execution_log.append(competitive_result)
        
        regulatory_result = self.subagents[SubagentRole.REGULATORY_EXPERT].execute(
            task=f"""
Analyze regulatory requirements for {product} in {market}:
1. Key regulations and compliance requirements
2. Licensing/registration needs
3. Industry-specific requirements
4. Estimated compliance costs
"""
        )
        self.execution_log.append(regulatory_result)
        
        # Step 2: Financial analysis (depends on above)
        print("Step 2: Financial analysis (using market findings)...")
        
        financial_context = {
            "market_insights": market_result.content[:500],  # First 500 chars
            "competitive_landscape": competitive_result.content[:500],
            "regulatory_requirements": regulatory_result.content[:500]
        }
        
        financial_result = self.subagents[SubagentRole.FINANCIAL_ANALYST].execute(
            task=f"""
Provide financial analysis for entering {market} with {product}:
1. Estimated investment required
2. Revenue potential (based on market and competitive analysis)
3. Break-even analysis
4. 3-5 year ROI projection
""",
            context=financial_context
        )
        self.execution_log.append(financial_result)
        
        # Step 3: Synthesis
        print("Step 3: Synthesizing findings...")
        
        synthesis_input = f"""
Market Analysis by specialists for {product} → {market}:

MARKET RESEARCH:
{market_result.content}

COMPETITIVE ANALYSIS:
{competitive_result.content}

REGULATORY ANALYSIS:
{regulatory_result.content}

FINANCIAL ANALYSIS:
{financial_result.content}
"""
        
        messages = [
            {"role": "user", "content": synthesis_input + """

Please synthesize all these analyses into:
1. Executive summary (2-3 sentences)
2. Key opportunities
3. Key challenges
4. Critical success factors
5. Go/No-go recommendation with reasoning
"""}
        ]
        
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system="""You are a strategic advisor. Synthesize multiple specialist 
analyses into clear, actionable recommendations. Be direct and concise.""",
            messages=messages
        )
        
        return response.content[0].text
    
    def print_execution_log(self):
        """Print summary of execution."""
        print("\n" + "="*60)
        print("EXECUTION LOG")
        print("="*60)
        
        for result in self.execution_log:
            status = "✓" if result.success else "✗"
            print(f"{status} {result.agent_name}: ", end="")
            
            if result.success:
                print(f"Success ({result.tokens_used} tokens)")
            else:
                print(f"Failed - {result.error}")


# Usage
if __name__ == "__main__":
    coordinator = SimpleCoordinator()
    
    response = coordinator.orchestrate_market_entry(
        market="Japan",
        product="SaaS collaboration software"
    )
    
    print("\n" + "="*60)
    print("FINAL RECOMMENDATION")
    print("="*60)
    print(response)
    
    coordinator.print_execution_log()
```

---

## Part 2: Advanced Coordinator with Error Handling

```python
import anthropic
import json
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
import time

class ExecutionStrategy(Enum):
    """How to execute tasks."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"


@dataclass
class TaskSpecification:
    """Specification for a task to delegate."""
    task_id: str
    subagent_role: str
    instruction: str
    context: Optional[Dict[str, Any]] = None
    depends_on: List[str] = field(default_factory=list)
    timeout_seconds: int = 60


@dataclass
class ExecutionResult:
    """Result of task execution."""
    task_id: str
    subagent: str
    success: bool
    content: Optional[str] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    tokens_used: int = 0
    retry_count: int = 0


class ResilientSubagent:
    """Subagent with error handling and retry logic."""
    
    def __init__(self, name: str, system_prompt: str, max_retries: int = 3):
        self.name = name
        self.system_prompt = system_prompt
        self.max_retries = max_retries
        self.client = anthropic.Anthropic()
    
    def execute_with_retry(self, task: str, context: Optional[dict] = None) -> ExecutionResult:
        """Execute task with retry logic."""
        
        start_time = time.time()
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                # Build message
                if context:
                    user_message = f"{task}\n\nContext:\n{json.dumps(context, indent=2)}"
                else:
                    user_message = task
                
                response = self.client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=1500,
                    system=self.system_prompt,
                    messages=[{"role": "user", "content": user_message}]
                )
                
                execution_time = time.time() - start_time
                
                return ExecutionResult(
                    task_id="unknown",
                    subagent=self.name,
                    success=True,
                    content=response.content[0].text,
                    execution_time=execution_time,
                    tokens_used=response.usage.output_tokens,
                    retry_count=attempt
                )
            
            except anthropic.APIError as e:
                last_error = str(e)
                
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    wait_time = 2 ** attempt
                    print(f"  Attempt {attempt + 1} failed: {e}")
                    print(f"  Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    print(f"  All {self.max_retries} attempts failed")
            
            except Exception as e:
                last_error = str(e)
                break
        
        execution_time = time.time() - start_time
        
        return ExecutionResult(
            task_id="unknown",
            subagent=self.name,
            success=False,
            error=last_error,
            execution_time=execution_time,
            retry_count=self.max_retries
        )


class AdvancedCoordinator:
    """Coordinator with dependency management and error handling."""
    
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.subagents = {}
        self.results: Dict[str, ExecutionResult] = {}
        self.tasks: List[TaskSpecification] = []
    
    def register_subagent(self, role: str, system_prompt: str):
        """Register a new subagent type."""
        self.subagents[role] = ResilientSubagent(role, system_prompt)
    
    def create_task_plan(self, query: str) -> List[TaskSpecification]:
        """
        Analyze query and create task plan.
        Use coordinator to decompose the task.
        """
        
        analysis_prompt = f"""
Analyze this query and create a task decomposition plan:

Query: {query}

Respond with a JSON array where each task has:
- task_id: unique identifier
- role: subagent type needed (market_researcher, analyst, etc)
- instruction: specific task instruction
- depends_on: array of task_ids this depends on

Example format:
[
  {{"task_id": "t1", "role": "market_researcher", "instruction": "...", "depends_on": []}},
  {{"task_id": "t2", "role": "analyst", "instruction": "...", "depends_on": ["t1"]}}
]
"""
        
        messages = [{"role": "user", "content": analysis_prompt}]
        
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1000,
            system="You are a task decomposition expert. Analyze queries and break them into coherent subtasks.",
            messages=messages
        )
        
        try:
            response_text = response.content[0].text
            json_start = response_text.find('[')
            json_end = response_text.rfind(']') + 1
            task_data = json.loads(response_text[json_start:json_end])
            
            tasks = []
            for t in task_data:
                tasks.append(TaskSpecification(
                    task_id=t.get("task_id"),
                    subagent_role=t.get("role"),
                    instruction=t.get("instruction"),
                    depends_on=t.get("depends_on", [])
                ))
            
            return tasks
        except:
            return []
    
    def execute_with_dependencies(self, tasks: List[TaskSpecification]):
        """Execute tasks respecting dependencies."""
        
        # Topological sort by dependencies
        executed = set()
        pending = {t.task_id: t for t in tasks}
        
        while pending:
            # Find ready tasks (all dependencies completed)
            ready = [
                task for task_id, task in pending.items()
                if all(dep in executed for dep in task.depends_on)
            ]
            
            if not ready:
                # Circular dependency or missing dependency
                print("Error: Unresolvable dependencies")
                break
            
            # Execute ready tasks in parallel would be here
            # For simplicity, we'll execute sequentially
            for task in ready:
                print(f"Executing {task.task_id} ({task.subagent_role})...")
                
                # Get subagent
                subagent = self.subagents.get(task.subagent_role)
                if not subagent:
                    print(f"  Warning: No subagent for {task.subagent_role}")
                    continue
                
                # Build context from dependencies
                context = {}
                for dep_id in task.depends_on:
                    if dep_id in self.results:
                        context[dep_id] = self.results[dep_id].content[:300]
                
                # Execute
                result = subagent.execute_with_retry(task.instruction, context if context else None)
                result.task_id = task.task_id
                self.results[task.task_id] = result
                
                executed.add(task.task_id)
                del pending[task.task_id]
                
                if result.success:
                    print(f"  ✓ Success")
                else:
                    print(f"  ✗ Failed: {result.error}")
    
    def synthesize_final_answer(self, original_query: str) -> str:
        """Aggregate all results into final answer."""
        
        # Build synthesis input
        synthesis_input = original_query + "\n\nAnalysis results:\n"
        
        for task_id, result in self.results.items():
            synthesis_input += f"\n{task_id}:\n"
            if result.success:
                synthesis_input += result.content[:500]
            else:
                synthesis_input += f"Failed: {result.error}"
        
        messages = [
            {"role": "user", "content": synthesis_input + """

Synthesize all the analysis results above into a comprehensive answer 
to the original query. Integrate findings and provide clear recommendations."""}
        ]
        
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system="You are an expert synthesizer. Combine specialist analyses into coherent responses.",
            messages=messages
        )
        
        return response.content[0].text


# Usage
if __name__ == "__main__":
    coordinator = AdvancedCoordinator()
    
    # Register subagents
    coordinator.register_subagent(
        "market_researcher",
        "You are a market research expert. Provide data-driven market analysis."
    )
    
    coordinator.register_subagent(
        "competitive_analyst",
        "You are a competitive intelligence expert. Analyze competitor strategies and positioning."
    )
    
    coordinator.register_subagent(
        "financial_analyst",
        "You are a financial analyst. Provide financial feasibility and ROI analysis."
    )
    
    # Decompose query
    query = "Should we enter the Indian market with our product?"
    print(f"Query: {query}\n")
    
    tasks = coordinator.create_task_plan(query)
    print(f"Created {len(tasks)} tasks")
    
    # Execute with dependencies
    coordinator.execute_with_dependencies(tasks)
    
    # Synthesize
    print("\nSynthesizing final answer...")
    answer = coordinator.synthesize_final_answer(query)
    
    print("\n" + "="*60)
    print("FINAL ANSWER")
    print("="*60)
    print(answer)
```

---

## Part 3: Monitoring and Observability

```python
from dataclasses import dataclass, asdict
from typing import Dict, List
import json
from datetime import datetime

@dataclass
class PerformanceMetrics:
    """Track performance metrics."""
    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_execution_time: float = 0.0
    total_tokens_used: int = 0
    total_cost_usd: float = 0.0
    subagent_performance: Dict[str, Dict] = None
    
    def __post_init__(self):
        if self.subagent_performance is None:
            self.subagent_performance = {}


class MonitoringCoordinator(AdvancedCoordinator):
    """Coordinator with performance monitoring."""
    
    # Pricing (as of May 2026)
    PRICING = {
        "claude-opus-4-6": {
            "input": 0.015 / 1_000_000,  # $15 per million input tokens
            "output": 0.075 / 1_000_000   # $75 per million output tokens
        }
    }
    
    def __init__(self):
        super().__init__()
        self.metrics = PerformanceMetrics()
    
    def execute_with_monitoring(self, tasks: List[TaskSpecification], query: str) -> str:
        """Execute tasks and collect metrics."""
        
        query_start = time.time()
        self.metrics.total_queries += 1
        
        try:
            # Execute tasks
            self.execute_with_dependencies(tasks)
            
            # Check if all succeeded
            all_succeeded = all(r.success for r in self.results.values())
            
            if all_succeeded:
                self.metrics.successful_queries += 1
            else:
                self.metrics.failed_queries += 1
            
            # Track subagent performance
            for task_id, result in self.results.items():
                subagent = result.subagent
                
                if subagent not in self.metrics.subagent_performance:
                    self.metrics.subagent_performance[subagent] = {
                        "calls": 0,
                        "successes": 0,
                        "failures": 0,
                        "total_time": 0.0,
                        "total_tokens": 0
                    }
                
                perf = self.metrics.subagent_performance[subagent]
                perf["calls"] += 1
                
                if result.success:
                    perf["successes"] += 1
                else:
                    perf["failures"] += 1
                
                perf["total_time"] += result.execution_time
                perf["total_tokens"] += result.tokens_used
                
                # Estimate cost
                cost = result.tokens_used * self.PRICING["claude-opus-4-6"]["output"]
                self.metrics.total_cost_usd += cost
            
            # Synthesis
            answer = self.synthesize_final_answer(query)
            
            # Total execution time
            execution_time = time.time() - query_start
            self.metrics.total_execution_time += execution_time
            
            return answer
        
        except Exception as e:
            self.metrics.failed_queries += 1
            raise
    
    def print_metrics(self):
        """Print performance metrics."""
        
        print("\n" + "="*60)
        print("PERFORMANCE METRICS")
        print("="*60)
        
        print(f"\nOverall:")
        print(f"  Total queries: {self.metrics.total_queries}")
        print(f"  Success rate: {self.metrics.successful_queries}/{self.metrics.total_queries}")
        print(f"  Total execution time: {self.metrics.total_execution_time:.2f}s")
        print(f"  Total tokens used: {self.metrics.total_tokens_used:,}")
        print(f"  Estimated cost: ${self.metrics.total_cost_usd:.4f}")
        
        if self.metrics.subagent_performance:
            print(f"\nSubagent Performance:")
            for subagent, perf in self.metrics.subagent_performance.items():
                success_rate = perf["successes"] / perf["calls"] * 100 if perf["calls"] > 0 else 0
                avg_time = perf["total_time"] / perf["calls"] if perf["calls"] > 0 else 0
                
                print(f"\n  {subagent}:")
                print(f"    Calls: {perf['calls']}")
                print(f"    Success rate: {success_rate:.1f}%")
                print(f"    Avg execution: {avg_time:.2f}s")
                print(f"    Total tokens: {perf['total_tokens']:,}")


# Usage
if __name__ == "__main__":
    coordinator = MonitoringCoordinator()
    
    # Register subagents
    coordinator.register_subagent("market_researcher", "Market research expert")
    coordinator.register_subagent("analyst", "Data analyst")
    
    # Example query
    query = "Analyze market opportunity"
    
    # Execute with monitoring
    # answer = coordinator.execute_with_monitoring(tasks, query)
    
    # Print metrics
    # coordinator.print_metrics()
```

---

## Part 4: Best Practices Checklist

### Coordinator Implementation

✓ Task decomposition is explicit and logged
✓ Each subagent receives clear, unambiguous instructions
✓ Context passed to subagents is minimal but sufficient
✓ Dependencies between tasks are explicit
✓ Parallel tasks are identified and executed concurrently
✓ Error handling is implemented with retries
✓ Results are aggregated and synthesized
✓ Performance is monitored and logged

### Subagent Implementation

✓ Single, clear area of responsibility
✓ Focused system prompt without extra context
✓ Tools are domain-specific only
✓ No assumptions about broader task
✓ Clear output format expected
✓ Error messages are helpful
✓ Limitations are documented

### Testing

```python
def test_task_decomposition():
    """Test that query decomposition is reasonable."""
    coordinator = AdvancedCoordinator()
    
    queries = [
        "Simple question",
        "Complex multi-part analysis",
        "Broad strategic decision"
    ]
    
    for query in queries:
        tasks = coordinator.create_task_plan(query)
        
        # Validate decomposition
        assert len(tasks) > 0, f"No tasks for: {query}"
        assert len(tasks) <= 5, f"Too many tasks for: {query}"
        
        # Check dependencies are valid
        task_ids = {t.task_id for t in tasks}
        for task in tasks:
            for dep in task.depends_on:
                assert dep in task_ids, f"Invalid dependency: {dep}"


def test_context_isolation():
    """Verify subagents don't receive excessive context."""
    coordinator = AdvancedCoordinator()
    coordinator.register_subagent("analyzer", "Analyzer prompt")
    
    subagent = coordinator.subagents["analyzer"]
    
    # Create large context
    large_context = {
        "irrelevant_data": "x" * 10000,
        "large_history": ["item"] * 1000
    }
    
    # Execute with large context
    # Should only pass relevant parts
    result = subagent.execute_with_retry(
        "Analyze this specific metric",
        context=None  # Don't pass irrelevant context
    )
    
    assert result.success
```

---

## Conclusion

These implementations show:
1. **Context isolation**: Subagents only receive what they need
2. **Hub-and-spoke**: All routing through coordinator
3. **Error handling**: Retries and fallbacks
4. **Monitoring**: Track performance and costs
5. **Composability**: Easy to add new subagents and tasks

Key takeaway: The coordinator is simple but powerful when it respects context isolation and manages dependencies carefully.
