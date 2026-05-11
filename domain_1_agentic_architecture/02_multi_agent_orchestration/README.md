# Multi-Agent Orchestration: Coordinator-Subagent Patterns
## Claude Architect Certification Guide

A comprehensive guide to building scalable, resilient multi-agent systems using coordinator-subagent architecture patterns.

---

## Table of Contents

1. [Core Concepts](#core-concepts)
2. [Hub-and-Spoke Architecture](#hub-and-spoke-architecture)
3. [Context Isolation Principle](#context-isolation-principle)
4. [Coordinator Responsibilities](#coordinator-responsibilities)
5. [Subagent Patterns](#subagent-patterns)
6. [Task Decomposition Strategies](#task-decomposition-strategies)
7. [Implementation Patterns (Python)](#implementation-patterns-python)
8. [Production Considerations](#production-considerations)
9. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)

---

## Core Concepts

### What Is Multi-Agent Orchestration?

Multi-agent orchestration is the coordination of multiple specialized AI agents to solve complex problems that are beyond the scope of a single agent. The key insight is that complex tasks often benefit from **specialization and parallel processing**.

**Single Agent Challenges**:
- Context window exhaustion with large tasks
- Inability to parallelize independent subtasks
- Difficulty handling multiple specialized domains
- Context switching overhead

**Multi-Agent Benefits**:
- Specialized agents for specific domains
- Parallel task execution
- Independent context windows
- Clear responsibility boundaries
- Better error isolation

### Coordinator-Subagent Model

```
┌─────────────────────────────────────────┐
│                                         │
│         COORDINATOR AGENT               │
│  (Task decomposition & routing)         │
│                                         │
│  - Parse user query                     │
│  - Decompose into subtasks             │
│  - Delegate to subagents               │
│  - Aggregate results                   │
│  - Synthesize final response           │
│                                         │
└──────────────┬──────────────────────────┘
               │
        ┌──────┼──────┐
        │      │      │
        ▼      ▼      ▼
    ┌─────┐ ┌─────┐ ┌─────┐
    │ SA1 │ │ SA2 │ │ SA3 │
    │     │ │     │ │     │
    │Data │ │Code │ │API  │
    │Anal │ │Expert│ │Spec │
    └─────┘ └─────┘ └─────┘
```

---

## Hub-and-Spoke Architecture

### Architecture Overview

The hub-and-spoke pattern centralizes all communication, coordination, and routing through a single coordinator agent (the hub), with specialized subagents (the spokes) handling specific domains.

### Key Characteristics

**Centralized Control**:
- Coordinator acts as traffic controller
- All routing decisions made by coordinator
- Single point of task decomposition
- Centralized result aggregation

**Subagent Isolation**:
- Each subagent has its own context window
- No direct inter-subagent communication
- Independent system prompts and tools
- Isolated error handling

**Information Flow**:
```
User Query
    │
    ▼
Coordinator (receives full query)
    │
    ├─> Decompose into subtasks
    │
    ├─> Decide which subagents to invoke
    │
    ├─┬────────────────────┬────────────────┐
    │ │                    │                │
    ▼ ▼                    ▼                ▼
  [Task 1]            [Task 2]          [Task 3]
  Send to SA1         Send to SA2       Send to SA3
  Full context        Full context      Full context
  (isolated)          (isolated)        (isolated)
    │                  │                 │
    ▼                  ▼                 ▼
  Result 1           Result 2          Result 3
  (back to           (back to         (back to
   coordinator)      coordinator)     coordinator)
    │
    └────────────────┬─────────────────┘
                     │
                     ▼
            Coordinator aggregates
            results and synthesizes
            final response
                     │
                     ▼
                Final Answer
```

### Why Hub-and-Spoke?

1. **Clear Communication Patterns**
   - Single coordinator knows all routing rules
   - Easy to add/remove subagents
   - Centralized monitoring and logging

2. **Failure Isolation**
   - One subagent failure doesn't cascade
   - Coordinator can retry or fallback
   - Clear error handling boundaries

3. **Context Efficiency**
   - Each agent has focused context window
   - No unnecessary shared history
   - Parallel execution possible

4. **Task Decomposition Control**
   - Coordinator ensures complete coverage
   - Prevents duplicate work
   - Manages dependencies between subtasks

---

## Context Isolation Principle

### What Context Isolation Means

**Critical Insight**: Subagents do NOT automatically inherit the coordinator's conversation history or context. Each subagent starts with:
- ✓ The specific subtask instructions
- ✓ Any context explicitly passed by the coordinator
- ✗ No coordinator conversation history
- ✗ No other subagents' results (unless shared by coordinator)
- ✗ No implicit understanding of the broader task

### Why This Design?

**Benefits**:
1. **Clean Separation of Concerns**
   - Subagent focuses only on its subtask
   - No cognitive load from irrelevant context
   - Clearer task boundaries

2. **Context Window Efficiency**
   - Subagent context used only for its domain
   - No wasted tokens on unrelated information
   - Smaller context = faster responses

3. **Failure Isolation**
   - If subagent misunderstands task, only that subtask fails
   - Doesn't pollute coordinator's context
   - Easier to recover and retry

4. **Reproducibility**
   - Same subtask input = same output
   - No dependency on coordinator's thinking process
   - Easier to test subagents independently

### Implementation Example

```python
# COORDINATOR knows:
# - Full original query
# - All conversation history
# - What other subagents are doing

coordinator_context = {
    "original_query": "Analyze sales data and generate 3 strategic recommendations...",
    "conversation_history": [...],  # Full history
    "current_turn": 5,
    "pending_subagents": ["data_analyst", "market_expert"]
}

# SUBAGENT (DataAnalyst) receives ONLY:
subagent_task = {
    "task": "Analyze Q3 sales data and provide key metrics",
    "sales_data": "Q3 revenue: $2.5M, growth: 15%, top products: [...], customer segments: [...]",
    "instruction": "Focus on: (1) Revenue trends, (2) Product performance, (3) Customer segments",
    "output_format": "Structured JSON with metrics and insights"
}

# DataAnalyst does NOT receive:
# ✗ coordinator's full conversation history
# ✗ what MarketExpert is doing
# ✗ what recommendations were already made
# ✗ the original broader strategic question

# If DataAnalyst needs context, coordinator must explicitly provide it
```

### How to Pass Context to Subagents

```python
def delegate_to_subagent(subagent_name, task_description, relevant_context):
    """
    Explicitly pass only needed context to subagent.
    
    Args:
        subagent_name: Which subagent to invoke
        task_description: Clear, specific instruction
        relevant_context: Only what THIS subagent needs
    """
    
    subagent_instruction = f"""
You are a {subagent_name} assistant. You have been given a specific task.

TASK: {task_description}

CONTEXT PROVIDED:
{relevant_context}

IMPORTANT:
- Focus only on this specific task
- You are part of a larger analysis (but don't need those details)
- Return your findings in the requested format
- Note any limitations or uncertainties
"""
    
    return invoke_subagent(subagent_name, subagent_instruction)
```

---

## Coordinator Responsibilities

### 1. Task Decomposition

**Definition**: Breaking a complex user query into actionable subtasks.

**Process**:
```
User Query
    │
    ├─> Identify key themes
    ├─> Determine required expertise
    ├─> Identify dependencies between tasks
    ├─> Plan execution order
    └─> Create subtask specifications
```

**Example: Strategic Analysis Query**

```
Original Query: "We're entering the Asian market. Analyze market opportunities, 
competition, regulatory environment, and provide strategic recommendations."

Decomposition:
├─ Task 1 (Market Research): Analyze market size, growth trends, customer segments
├─ Task 2 (Competitive Analysis): Research key competitors, their strategies, market share
├─ Task 3 (Regulatory Expert): Analyze legal/regulatory requirements by country
└─ Task 4 (Strategy Synthesizer): Combine findings and generate recommendations
    (Depends on: Tasks 1, 2, 3)
```

**Decomposition Strategy Decision Tree**:

```
Should I create a subagent for this?
├─ Is it a specialized domain?
│  ├─ YES: Consider subagent
│  └─ NO: Coordinator handles it
├─ Can it run in parallel?
│  ├─ YES: Subagent benefits
│  └─ NO: Coordinator chains them
├─ Does it need focused context?
│  ├─ YES: Subagent isolation helps
│  └─ NO: Coordinator can handle
└─ Expected size (context needed)?
   ├─ Large: Subagent gets own window
   └─ Small: Coordinator handles
```

### 2. Subagent Selection and Delegation

**Coordinator must decide**:
- Which subagents are needed
- What instructions to give them
- What context to provide
- In what order to invoke them (dependencies)
- Which are parallel vs sequential

**Pattern: Conditional Subagent Invocation**

```python
class Coordinator:
    def __init__(self):
        self.subagents = {
            "data_analyst": DataAnalystAgent(),
            "code_expert": CodeExpertAgent(),
            "api_specialist": APISpecialistAgent(),
            "security_auditor": SecurityAuditorAgent(),
        }
    
    def decompose_and_delegate(self, user_query):
        """Analyze query and delegate to appropriate subagents."""
        
        # Analyze what's needed
        needs = self.analyze_requirements(user_query)
        # Returns: {"data": True, "code": False, "api": True, "security": True}
        
        subagent_results = {}
        
        # Invoke only needed subagents
        if needs.get("data"):
            subagent_results["data"] = self.subagents["data_analyst"].analyze(
                task="Analyze data patterns",
                data=self.extract_data_from_query(user_query),
                constraints=self.extract_data_constraints(user_query)
            )
        
        if needs.get("api"):
            subagent_results["api"] = self.subagents["api_specialist"].design(
                task="Design API structure",
                requirements=self.extract_api_requirements(user_query),
                data_schema=subagent_results["data"].schema  # Use previous result
            )
        
        if needs.get("security"):
            subagent_results["security"] = self.subagents["security_auditor"].audit(
                task="Audit security implications",
                api_design=subagent_results.get("api"),
                data_sensitivity=self.assess_sensitivity(user_query)
            )
        
        return subagent_results
```

### 3. Result Aggregation

**Coordinator must**:
- Collect results from all subagents
- Resolve conflicts between subagents
- Fill any gaps not covered
- Synthesize into coherent response

**Pattern: Result Integration**

```python
def aggregate_results(self, subagent_results):
    """
    Combine results from multiple subagents.
    Handle conflicts, overlaps, and gaps.
    """
    
    aggregated = {
        "data_insights": subagent_results["data"].get("insights"),
        "api_design": subagent_results["api"].get("design"),
        "security_review": subagent_results["security"].get("review"),
        "conflicts": [],
        "gaps": [],
        "recommendations": []
    }
    
    # Check for conflicts
    if (subagent_results["api"].get("data_format") != 
        subagent_results["data"].get("recommended_format")):
        aggregated["conflicts"].append({
            "type": "data_format_mismatch",
            "api_wants": subagent_results["api"].get("data_format"),
            "data_analyst_recommends": subagent_results["data"].get("recommended_format"),
            "resolution": "Follow data analyst recommendation for efficiency"
        })
    
    # Check for gaps
    if not subagent_results["security"].get("compliance_reviewed"):
        aggregated["gaps"].append("Compliance review incomplete")
    
    # Generate recommendations
    aggregated["recommendations"] = self.synthesize_recommendations(
        data_insights=aggregated["data_insights"],
        api_design=aggregated["api_design"],
        security_review=aggregated["security_review"]
    )
    
    return aggregated
```

### 4. Error Handling and Fallback

**Coordinator must handle**:
- Subagent failures
- Partial results
- Conflicting recommendations
- Ambiguous outputs
- Retry strategies

**Pattern: Resilient Delegation**

```python
def delegate_with_fallback(self, subagent_name, task, max_retries=3):
    """Delegate with fallback strategy."""
    
    for attempt in range(max_retries):
        try:
            result = self.subagents[subagent_name].execute(task)
            
            # Validate result
            if self.validate_result(result, task):
                return result
            else:
                raise ValueError("Invalid result format")
        
        except ValueError as e:
            if attempt < max_retries - 1:
                # Retry with refined task
                task["retry_note"] = f"Previous attempt failed: {e}"
                continue
            else:
                # Final attempt failed, try fallback
                return self.invoke_fallback_subagent(subagent_name, task)
        
        except Exception as e:
            # Unexpected error
            self.log_error(subagent_name, e)
            return self.generate_default_response(task)
```

---

## Subagent Patterns

### 1. Specialized Subagent Design

Each subagent should have:
- **Clear specialty**: Exactly what domain/task it handles
- **Focused system prompt**: Specific expertise and constraints
- **Dedicated tools**: Tools relevant to its domain only
- **Isolated context**: Independent conversation history per invocation

**Example: Data Analyst Subagent**

```python
class DataAnalystSubagent:
    def __init__(self):
        self.name = "DataAnalyst"
        self.system_prompt = """
You are an expert data analyst. Your role is to:
- Analyze datasets and identify patterns
- Calculate metrics and statistics
- Provide data-driven insights
- Highlight data quality issues
- Recommend data transformations

You have access to data analysis tools only (SQL, visualization, statistics).
You do NOT handle business strategy or implementation - other specialists will.

When analyzing:
1. Start with data overview (shape, types, quality)
2. Calculate key metrics
3. Identify patterns and outliers
4. Suggest further analysis if needed
5. Be clear about limitations and assumptions
"""
        
        self.tools = [
            self.tool_query_database,
            self.tool_statistical_analysis,
            self.tool_data_validation,
            self.tool_visualization
        ]
    
    def execute(self, task_description, data_context):
        """Execute analysis with isolated context."""
        
        messages = [
            {
                "role": "user",
                "content": f"""
{task_description}

Data Context: {data_context}

Please analyze this data and provide insights.
"""
            }
        ]
        
        # Invoke Claude with this subagent's tools
        response = self.call_claude(
            messages=messages,
            system_prompt=self.system_prompt,
            tools=self.tools
        )
        
        return self._parse_response(response)
```

### 2. Subagent Execution Patterns

**Sequential Execution** (when dependent):
```python
def execute_sequential(self, tasks):
    """Execute tasks where output of one feeds into next."""
    
    results = {}
    
    # Task 1: Data Analysis
    results["data"] = self.subagents["data_analyst"].analyze(tasks["data"])
    
    # Task 2: Strategy (depends on data)
    results["strategy"] = self.subagents["strategist"].synthesize(
        task=tasks["strategy"],
        data_findings=results["data"]  # Pass previous result
    )
    
    # Task 3: Implementation (depends on strategy)
    results["implementation"] = self.subagents["implementer"].plan(
        task=tasks["implementation"],
        strategy=results["strategy"]  # Pass previous result
    )
    
    return results
```

**Parallel Execution** (when independent):
```python
async def execute_parallel(self, tasks):
    """Execute independent tasks concurrently."""
    
    # These tasks don't depend on each other
    tasks_to_run = [
        self.subagents["market_research"].research(tasks["market"]),
        self.subagents["competitor_analysis"].analyze(tasks["competitors"]),
        self.subagents["regulatory_expert"].assess(tasks["regulations"]),
    ]
    
    # Run concurrently
    results = await asyncio.gather(*tasks_to_run)
    
    return {
        "market": results[0],
        "competitors": results[1],
        "regulations": results[2]
    }
```

**Conditional Execution** (based on query analysis):
```python
def execute_conditional(self, user_query):
    """Invoke subagents only if needed."""
    
    # Analyze what's actually needed
    if "code" in user_query.lower():
        code_result = self.subagents["code_expert"].help(user_query)
    else:
        code_result = None
    
    if "database" in user_query.lower() or "data" in user_query.lower():
        data_result = self.subagents["data_analyst"].help(user_query)
    else:
        data_result = None
    
    if "security" in user_query.lower() or "vulnerability" in user_query.lower():
        security_result = self.subagents["security_expert"].audit(user_query)
    else:
        security_result = None
    
    return {
        "code": code_result,
        "data": data_result,
        "security": security_result
    }
```

---

## Task Decomposition Strategies

### Strategy 1: Domain-Based Decomposition

Split by expertise domain.

**When to use**: When query spans multiple specialized domains.

**Example**:
```
Query: "Implement a machine learning pipeline for fraud detection"

Domains:
├─ Data Engineering: Prepare data, handle missing values, feature engineering
├─ ML Expert: Choose algorithms, train models, optimize
├─ Security Expert: Implement safeguards, privacy controls
└─ DevOps: Deploy, monitor, maintain pipeline
```

**Implementation**:
```python
def decompose_by_domain(query):
    """Identify which domains are needed."""
    
    domains_needed = {
        "data_engineering": False,
        "ml": False,
        "security": False,
        "devops": False,
    }
    
    query_lower = query.lower()
    
    if any(word in query_lower for word in ["data", "pipeline", "prepare", "transform"]):
        domains_needed["data_engineering"] = True
    
    if any(word in query_lower for word in ["model", "algorithm", "train", "optimize", "ml"]):
        domains_needed["ml"] = True
    
    if any(word in query_lower for word in ["security", "privacy", "fraud", "anomaly"]):
        domains_needed["security"] = True
    
    if any(word in query_lower for word in ["deploy", "production", "monitor", "devops"]):
        domains_needed["devops"] = True
    
    return {k: v for k, v in domains_needed.items() if v}
```

### Strategy 2: Process-Based Decomposition

Split by steps in a process.

**When to use**: When there's a natural workflow or sequence.

**Example**:
```
Query: "Conduct competitive analysis for entering a new market"

Process Steps:
├─ Phase 1 (Research): Identify competitors, gather information
├─ Phase 2 (Analysis): Analyze strengths/weaknesses, market positioning
├─ Phase 3 (Synthesis): Compare findings, identify opportunities
└─ Phase 4 (Strategy): Generate recommendations and action items
```

**Implementation**:
```python
def decompose_by_process(query):
    """Break into logical process steps."""
    
    return {
        "research": {
            "task": "Identify and gather information about competitors",
            "subagent": "market_researcher",
            "depends_on": []
        },
        "analysis": {
            "task": "Analyze competitor strengths, weaknesses, strategies",
            "subagent": "competitive_analyst",
            "depends_on": ["research"]
        },
        "synthesis": {
            "task": "Synthesize findings and identify opportunities",
            "subagent": "strategist",
            "depends_on": ["analysis"]
        },
        "recommendations": {
            "task": "Generate strategic recommendations",
            "subagent": "strategy_recommender",
            "depends_on": ["synthesis"]
        }
    }
```

### Strategy 3: Data-Based Decomposition

Split by different data sources or datasets.

**When to use**: When processing multiple independent datasets.

**Example**:
```
Query: "Analyze sales, marketing, and operational metrics for Q3"

Data Sources:
├─ Sales Data: Revenue, transactions, customer acquisition
├─ Marketing Data: Campaign performance, ROI, engagement
└─ Operations Data: Costs, efficiency, resource utilization
```

### ⚠️ THE RISK: Overly Narrow Decomposition

**THE PROBLEM**:

If coordinator decomposes too narrowly, subtasks become disconnected and miss the bigger picture.

**Example of Bad Decomposition**:

```python
# ❌ WRONG: Too narrow, loses context
tasks = {
    "task1": "Extract revenue numbers from Q3",
    "task2": "Extract customer count from Q3",
    "task3": "Extract expenses from Q3",
    "task4": "Calculate gross profit",
    "task5": "Compare to Q2",
    "task6": "Identify top products"
}
# Result: 6 disconnected analyses with no synthesis
```

**Why This Fails**:
- Subagents don't see the bigger story
- No one connects the dots
- Results are a list of facts, not insights
- Missing holistic understanding
- Coordinator becomes bottleneck (must synthesize everything)

**Example of Good Decomposition**:

```python
# ✓ CORRECT: Balanced scope with clear ownership
tasks = {
    "financial_analysis": {
        "task": "Analyze Q3 financial performance including revenue trends, expense patterns, and profitability",
        "subagent": "financial_analyst",
        "includes": ["revenue analysis", "cost analysis", "profit margins", "q2/q3 comparison"]
    },
    "product_analysis": {
        "task": "Identify top-performing products and their contribution to revenue",
        "subagent": "product_analyst",
        "includes": ["product sales", "growth rates", "customer segments buying them"]
    },
    "insights": {
        "task": "Synthesize financial and product findings into business insights",
        "subagent": "business_analyst",
        "depends_on": ["financial_analysis", "product_analysis"]
    }
}
```

### How to Get Decomposition Right

**The Balance**:

```
Too Narrow (Bad)        Just Right (Good)       Too Broad (Bad)
─────────────           ──────────────          ───────────────
6+ small tasks          3-4 focused tasks       1-2 huge tasks

- Fragments             - Clear boundaries      - Overloads context
- Loses context         - Maintains context     - Can't parallelize
- Over-coordination     - Balanced load         - Single point of failure
- Hard to synthesize    - Easy synthesis        - No specialization

Task 1: Extract #       Task 1: Analyze         Task: Do everything
Task 2: Extract #       financial
Task 3: Extract #       performance
Task 4: Extract #
Task 5: Compare         Task 2: Analyze
Task 6: Identify        market trends
```

**Decision Framework**:

```python
def is_decomposition_good(tasks):
    """Evaluate if decomposition is appropriate."""
    
    # Too narrow: > 5 atomic tasks
    if len(tasks) > 5:
        return False, "Too many small tasks - over-decomposed"
    
    # Too broad: single large task
    if len(tasks) == 1:
        return False, "Single task - not decomposed enough"
    
    # Check scope
    for task_name, task_spec in tasks.items():
        # Each task should be 5-20 minutes of work
        estimated_scope = task_spec.get("estimated_scope", "medium")
        
        if estimated_scope == "huge":
            return False, f"Task '{task_name}' is too large"
        
        if estimated_scope == "tiny":
            return False, f"Task '{task_name}' is too small"
    
    # Check coherence (can each task be understood independently?)
    for task_spec in tasks.values():
        if not self._is_task_coherent(task_spec):
            return False, "Task instructions are incoherent"
    
    return True, "Good decomposition"
```

---

## Implementation Patterns (Python)

### Complete Coordinator-Subagent Example

```python
import anthropic
import json
from typing import Any
from dataclasses import dataclass

@dataclass
class TaskResult:
    subagent: str
    success: bool
    result: Any
    error: str = None

class Subagent:
    """A specialized subagent with isolated context."""
    
    def __init__(self, name: str, specialty: str, system_prompt: str):
        self.name = name
        self.specialty = specialty
        self.system_prompt = system_prompt
        self.client = anthropic.Anthropic()
    
    def execute(self, task: str, context: dict = None) -> TaskResult:
        """Execute task with isolated context."""
        
        # Build task message with only needed context
        if context:
            message_content = f"""
Task: {task}

Context provided:
{json.dumps(context, indent=2)}

Please complete this task. Focus on accuracy and clarity.
"""
        else:
            message_content = task
        
        try:
            messages = [{"role": "user", "content": message_content}]
            
            response = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=2048,
                system=self.system_prompt,
                messages=messages
            )
            
            result_text = response.content[0].text
            
            return TaskResult(
                subagent=self.name,
                success=True,
                result=result_text
            )
        
        except Exception as e:
            return TaskResult(
                subagent=self.name,
                success=False,
                result=None,
                error=str(e)
            )


class CoordinatorAgent:
    """Coordinator that manages multiple subagents."""
    
    def __init__(self):
        self.client = anthropic.Anthropic()
        
        # Create subagents
        self.subagents = {
            "market_analyst": Subagent(
                name="market_analyst",
                specialty="Market research and trend analysis",
                system_prompt="""You are a market research expert. Analyze markets, 
                identify trends, assess competition, and provide data-driven insights. 
                Focus on facts and evidence."""
            ),
            "financial_expert": Subagent(
                name="financial_expert",
                specialty="Financial analysis",
                system_prompt="""You are a financial analyst. Analyze financial data, 
                calculate metrics, assess profitability, and provide financial 
                projections. Be precise with numbers."""
            ),
            "strategist": Subagent(
                name="strategist",
                specialty="Strategic planning",
                system_prompt="""You are a strategic consultant. Synthesize information 
                and generate strategic recommendations. Consider long-term implications 
                and competitive positioning."""
            ),
        }
    
    def decompose_query(self, user_query: str) -> dict:
        """Analyze query and create task decomposition."""
        
        # Coordinator analyzes what's needed
        analysis_prompt = f"""
Analyze this query and determine what subtasks are needed:

Query: {user_query}

Respond with a JSON object:
{{
  "market_analysis_needed": boolean,
  "financial_analysis_needed": boolean,
  "strategic_synthesis_needed": boolean,
  "reasoning": "explanation"
}}
"""
        
        messages = [{"role": "user", "content": analysis_prompt}]
        
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            system="You are a task decomposition expert. Analyze queries and break them into appropriate subtasks.",
            messages=messages
        )
        
        try:
            # Parse response (handling potential JSON extraction)
            response_text = response.content[0].text
            # Extract JSON from response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            analysis = json.loads(response_text[json_start:json_end])
            return analysis
        except:
            return {
                "market_analysis_needed": True,
                "financial_analysis_needed": True,
                "strategic_synthesis_needed": True
            }
    
    def create_subtasks(self, user_query: str, analysis: dict) -> dict:
        """Create specific task instructions for each needed subagent."""
        
        tasks = {}
        
        if analysis.get("market_analysis_needed"):
            tasks["market"] = f"""
Analyze the market aspects of this query:
{user_query}

Provide:
1. Market size and growth potential
2. Key competitors and their positioning
3. Market trends and opportunities
4. Target customer segments
"""
        
        if analysis.get("financial_analysis_needed"):
            tasks["financial"] = f"""
Analyze the financial aspects of this query:
{user_query}

Provide:
1. Financial feasibility assessment
2. Cost structure analysis
3. Revenue potential
4. Return on investment considerations
"""
        
        if analysis.get("strategic_synthesis_needed"):
            tasks["strategy"] = f"""
Provide strategic recommendations based on:
{user_query}

Synthesize multiple perspectives to provide:
1. Strategic opportunities
2. Key success factors
3. Risk mitigation strategies
4. Actionable recommendations
"""
        
        return tasks
    
    def delegate_and_execute(self, tasks: dict) -> dict:
        """Delegate tasks to subagents and collect results."""
        
        results = {}
        
        if "market" in tasks:
            results["market"] = self.subagents["market_analyst"].execute(
                task=tasks["market"]
            )
        
        if "financial" in tasks:
            # Pass market findings as context to financial expert
            context = None
            if results.get("market") and results["market"].success:
                context = {"market_findings": results["market"].result}
            
            results["financial"] = self.subagents["financial_expert"].execute(
                task=tasks["financial"],
                context=context
            )
        
        if "strategy" in tasks:
            # Pass all previous findings to strategist
            context = {}
            if results.get("market") and results["market"].success:
                context["market_findings"] = results["market"].result
            if results.get("financial") and results["financial"].success:
                context["financial_findings"] = results["financial"].result
            
            results["strategy"] = self.subagents["strategist"].execute(
                task=tasks["strategy"],
                context=context
            )
        
        return results
    
    def synthesize_final_response(self, user_query: str, results: dict) -> str:
        """Aggregate subagent results into final response."""
        
        # Build synthesis prompt
        synthesis_content = f"""
Original Query: {user_query}

Results from specialists:
"""
        
        for key, result in results.items():
            if result.success:
                synthesis_content += f"""

{key.upper()} Analysis:
{result.result}
"""
            else:
                synthesis_content += f"""

{key.upper()} Analysis: FAILED - {result.error}
"""
        
        synthesis_prompt = synthesis_content + """

Please synthesize all these analyses into a comprehensive, coherent response 
to the original query. Integrate the findings, highlight key insights, and 
provide clear recommendations.
"""
        
        messages = [{"role": "user", "content": synthesis_prompt}]
        
        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            system="""You are an expert synthesizer. Combine diverse analyses into 
            coherent, actionable responses. Highlight key insights and provide clear 
            recommendations.""",
            messages=messages
        )
        
        return response.content[0].text
    
    def orchestrate(self, user_query: str) -> str:
        """Main orchestration flow."""
        
        print(f"Coordinator: Analyzing query...")
        analysis = self.decompose_query(user_query)
        
        print(f"Coordinator: Decomposing into tasks...")
        tasks = self.create_subtasks(user_query, analysis)
        
        print(f"Coordinator: Delegating to {len(tasks)} subagents...")
        results = self.delegate_and_execute(tasks)
        
        print(f"Coordinator: Synthesizing results...")
        final_response = self.synthesize_final_response(user_query, results)
        
        return final_response


# Usage
if __name__ == "__main__":
    coordinator = CoordinatorAgent()
    
    query = """We're considering expanding our SaaS product to the European market. 
    What should our go-to-market strategy be?"""
    
    response = coordinator.orchestrate(query)
    print("\nFinal Response:")
    print(response)
```

---

## Production Considerations

### 1. Monitoring and Observability

**What to track**:
- Subagent execution time
- Success/failure rates
- Result quality metrics
- Context window usage
- Cost per query

**Implementation**:

```python
class MonitoredCoordinator(CoordinatorAgent):
    def __init__(self):
        super().__init__()
        self.metrics = {
            "subagent_calls": {},
            "execution_times": {},
            "errors": {},
            "total_cost_usd": 0
        }
    
    def delegate_and_execute_monitored(self, tasks):
        """Execute with monitoring."""
        
        results = {}
        
        for task_name, task_spec in tasks.items():
            subagent_name = task_spec.get("subagent")
            
            # Track execution
            start_time = time.time()
            
            try:
                result = self.subagents[subagent_name].execute(task_spec["task"])
                execution_time = time.time() - start_time
                
                # Record metrics
                self._record_success(subagent_name, execution_time, result)
                results[task_name] = result
            
            except Exception as e:
                execution_time = time.time() - start_time
                self._record_error(subagent_name, execution_time, e)
                results[task_name] = None
        
        return results
    
    def _record_success(self, subagent, exec_time, result):
        if subagent not in self.metrics["subagent_calls"]:
            self.metrics["subagent_calls"][subagent] = 0
        
        self.metrics["subagent_calls"][subagent] += 1
        self.metrics["execution_times"][subagent] = exec_time
        
        print(f"✓ {subagent}: {exec_time:.2f}s")
    
    def _record_error(self, subagent, exec_time, error):
        if subagent not in self.metrics["errors"]:
            self.metrics["errors"][subagent] = []
        
        self.metrics["errors"][subagent].append(str(error))
        print(f"✗ {subagent}: {error}")
```

### 2. Error Handling and Retry Logic

**Strategy**: Retry at multiple levels

```python
class ResilientCoordinator(CoordinatorAgent):
    def __init__(self, max_retries=3):
        super().__init__()
        self.max_retries = max_retries
    
    def delegate_with_retry(self, subagent_name, task, max_retries=None):
        """Delegate with exponential backoff."""
        
        if max_retries is None:
            max_retries = self.max_retries
        
        for attempt in range(max_retries):
            try:
                result = self.subagents[subagent_name].execute(task)
                
                if result.success:
                    return result
                
                if attempt < max_retries - 1:
                    # Refine task for retry
                    task = self._refine_task_for_retry(task, result.error)
            
            except Exception as e:
                if attempt == max_retries - 1:
                    return TaskResult(
                        subagent=subagent_name,
                        success=False,
                        error=str(e)
                    )
```

### 3. Cost Management

**Strategies**:
- Use smaller models for simple decomposition
- Implement result caching
- Set query budgets
- Monitor token usage

```python
class CostEfficientCoordinator(CoordinatorAgent):
    def __init__(self, max_budget_usd=10.0):
        super().__init__()
        self.max_budget_usd = max_budget_usd
        self.spent_usd = 0.0
    
    def decompose_query_cheaply(self, user_query):
        """Use smaller model for decomposition."""
        
        # Use Haiku (cheaper) for decomposition
        response = self.client.messages.create(
            model="claude-haiku-4-5",  # Cheaper model
            max_tokens=300,
            messages=[{"role": "user", "content": f"Decompose: {user_query}"}]
        )
        
        return response.content[0].text
    
    def check_budget(self, estimated_cost):
        """Check if we can afford next call."""
        
        if self.spent_usd + estimated_cost > self.max_budget_usd:
            raise BudgetExceededError(
                f"Query would exceed budget. "
                f"Spent: ${self.spent_usd:.2f}, "
                f"Limit: ${self.max_budget_usd:.2f}"
            )
```

---

## Common Pitfalls and Solutions

### Pitfall 1: Coordinator Bottleneck

**Problem**: Coordinator becomes a bottleneck, making sequential decisions slowly.

**Example**:
```python
# ❌ WRONG: Sequential and blocking
result1 = subagent1.execute(task1)  # Wait for result
result2 = subagent2.execute(task2)  # Then wait for this
result3 = subagent3.execute(task3)  # Then wait for this
```

**Solution**: Parallelize independent tasks

```python
# ✓ CORRECT: Parallel execution
import asyncio

async def execute_parallel(self, independent_tasks):
    """Run independent tasks concurrently."""
    
    tasks = [
        self.subagents["analyst1"].execute_async(independent_tasks[0]),
        self.subagents["analyst2"].execute_async(independent_tasks[1]),
        self.subagents["analyst3"].execute_async(independent_tasks[2]),
    ]
    
    results = await asyncio.gather(*tasks)
    return results
```

### Pitfall 2: Context Leakage

**Problem**: Accidentally sharing coordinator's context with subagents, bloating their context window.

**Example**:
```python
# ❌ WRONG: Passing full conversation history
subagent.execute(
    task="Analyze sales",
    full_context=self.conversation_history  # Too much!
)
```

**Solution**: Pass only relevant context

```python
# ✓ CORRECT: Extract and pass only what's needed
relevant_context = {
    "sales_data": extract_sales_from_history(self.conversation_history),
    "date_range": "Q3 2024"
}

subagent.execute(
    task="Analyze sales",
    context=relevant_context  # Just what's needed
)
```

### Pitfall 3: Subagent Confusion

**Problem**: Subagents misunderstand their task because instructions are unclear.

**Example**:
```python
# ❌ WRONG: Ambiguous task
task = "Analyze the data"

# What data? Analyze what? What should the output be?
```

**Solution**: Crystal-clear task instructions

```python
# ✓ CORRECT: Explicit, detailed task
task = """
Analyze Q3 sales data with these specific steps:

1. Calculate total revenue and year-over-year growth
2. Identify top 5 products by revenue
3. Break down sales by customer segment
4. Calculate customer acquisition cost

Return results in JSON format with these exact keys:
- total_revenue
- yoy_growth_percent
- top_products (array with name, revenue, growth)
- segment_breakdown (object with segment: revenue pairs)
- cac
"""
```

### Pitfall 4: Over-Decomposition

**Problem**: Breaking task into too many small pieces, losing context.

**Example**:
```python
# ❌ WRONG: Too many tiny tasks
tasks = {
    "task1": "Extract numbers from data",
    "task2": "Sort the numbers",
    "task3": "Calculate average",
    "task4": "Calculate median",
    "task5": "Calculate std dev",
    "task6": "Describe results"
}
# Each task isolated, no one sees the big picture
```

**Solution**: Combine related subtasks

```python
# ✓ CORRECT: Grouped by coherence
tasks = {
    "statistical_analysis": """
Analyze the provided data:
1. Calculate key statistics (mean, median, std dev, percentiles)
2. Identify outliers
3. Describe the distribution

Return structured analysis with all metrics.
""",
    
    "interpretation": """
Given the statistical analysis, provide business interpretation:
1. What does this data tell us?
2. What are the key insights?
3. What should we do about it?
"""
}
```

### Pitfall 5: Result Conflation

**Problem**: Coordinator doesn't know how to handle conflicting recommendations from subagents.

**Example**:
```python
# ❌ WRONG: Conflict not resolved
market_analyst says: "Enter market immediately"
financial_expert says: "Not financially viable yet"
# Coordinator just presents both without resolving
```

**Solution**: Explicit conflict resolution

```python
# ✓ CORRECT: Acknowledge and resolve conflicts
def resolve_conflicts(self, results):
    """Identify and resolve conflicting recommendations."""
    
    conflicts = self._identify_conflicts(results)
    
    if conflicts:
        # Ask specialist to evaluate tradeoffs
        tradeoff_analysis = self.subagents["strategist"].execute(f"""
There are conflicting recommendations:

Market Analyst: {conflicts[0].recommendation}
Financial Expert: {conflicts[1].recommendation}

What is the best path forward considering both perspectives?
Explain your reasoning.
""")
    
    return {
        "conflicts": conflicts,
        "resolution": tradeoff_analysis
    }
```

---

## Best Practices Summary

### DO:
✓ Keep coordinator logic simple and focused
✓ Make subagent tasks explicit and unambiguous
✓ Pass only relevant context to subagents
✓ Parallelize independent tasks
✓ Handle failures gracefully with fallbacks
✓ Monitor subagent performance
✓ Document task decomposition strategy
✓ Validate subagent outputs
✓ Version your subagent prompts

### DON'T:
✗ Share full conversation history with subagents
✗ Make tasks too narrow (over-decompose)
✗ Make tasks too broad (under-decompose)
✗ Allow direct subagent-to-subagent communication
✗ Ignore errors and keep going
✗ Create too many specialized subagents
✗ Hardcode decomposition logic
✗ Assume subagent will "understand context"
✗ Forget to aggregate and synthesize results

---

## Certification Exam Focus Points

**Know these for the exam**:

1. **Hub-and-Spoke Pattern**
   - Coordinator makes ALL routing decisions
   - Subagents don't communicate directly
   - All information flows through coordinator
   - Clear separation of concerns

2. **Context Isolation**
   - Subagents do NOT inherit coordinator's history
   - Each subagent has independent context window
   - Coordinator must explicitly pass needed context
   - Benefits: isolation, efficiency, clarity

3. **Coordinator Responsibilities**
   - Task decomposition
   - Subagent selection
   - Result aggregation
   - Error handling

4. **Decomposition Risks**
   - Overly narrow = fragmented, loses context
   - Over-decomposition = coordinator bottleneck
   - Under-decomposition = single point of failure
   - Right balance = 3-4 coherent tasks

5. **Common Patterns**
   - Sequential (dependent subtasks)
   - Parallel (independent subtasks)
   - Conditional (only what's needed)

---

## Conclusion

Multi-agent orchestration with coordinator-subagent patterns enables:
- Specialization through domain-specific agents
- Parallelization of independent work
- Clear error isolation and recovery
- Scalable complex task handling

The key is maintaining the hub-and-spoke architecture, respecting context isolation, and getting decomposition right: not too narrow, not too broad, but balanced for your specific use case.
