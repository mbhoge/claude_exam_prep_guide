# Multi-Agent Orchestration: Patterns, Pitfalls, and Exam Preparation

---

## Decision Framework: When to Use Multi-Agent Systems

### Single Agent vs Multi-Agent Decision Tree

```
Is the task complex?
├─ NO: Single agent sufficient
│
└─ YES: Is there clear specialization needed?
   ├─ NO: Single agent can handle
   │
   └─ YES: Can tasks run in parallel?
      ├─ NO: Single agent chains them
      │
      └─ YES: Will context window be exceeded?
         ├─ NO: Single agent still possible
         │
         └─ YES: Multi-agent with coordinator
            └─ Use hub-and-spoke pattern
```

### When Multi-Agent is Overkill

```python
# ❌ WRONG: Multi-agent for simple task
coordinator = CoordinatorAgent()
result = coordinator.orchestrate(
    "What is 2 + 2?"  # Simple! Single agent.
)

# ✓ CORRECT: Single agent
client = anthropic.Anthropic()
response = client.messages.create(...)
```

### When Multi-Agent is Necessary

```python
# ✓ CORRECT: Multi-agent for complex, specialized task
coordinator = CoordinatorAgent()
result = coordinator.orchestrate(
    """Analyze market entry for our SaaS product in 5 countries.
    Consider market size, competition, regulations, and financials."""
    # Multiple domains: market, legal, finance
    # Can parallelize analysis
    # Each domain needs focused expertise
)
```

---

## Design Patterns for Coordinators

### Pattern 1: Sequential Pipeline

**When**: Tasks must run in order, each depends on previous.

```python
class PipelineCoordinator:
    """Execute tasks in strict sequence."""
    
    def orchestrate(self, query):
        # Step 1: Research
        research = self.subagents["researcher"].execute(
            "Research topic"
        )
        
        # Step 2: Analyze (uses Step 1 output)
        analysis = self.subagents["analyst"].execute(
            "Analyze topic",
            context={"research": research.content}
        )
        
        # Step 3: Synthesize (uses Steps 1+2)
        synthesis = self.subagents["strategist"].execute(
            "Synthesize insights",
            context={
                "research": research.content,
                "analysis": analysis.content
            }
        )
        
        return synthesis.content
```

**Pros**: Clear execution order, simple to understand
**Cons**: No parallelization, slower execution

### Pattern 2: Fan-Out/Fan-In

**When**: Multiple independent tasks, then synthesis.

```python
class FanOutFanInCoordinator:
    """Execute independent tasks in parallel, then synthesize."""
    
    async def orchestrate(self, query):
        # Fan-out: Parallel independent tasks
        results = await asyncio.gather(
            self.subagents["market"].execute("Market analysis", query),
            self.subagents["tech"].execute("Technical analysis", query),
            self.subagents["finance"].execute("Financial analysis", query),
        )
        
        # Fan-in: Synthesis
        return self.synthesize(results)
```

**Pros**: Faster (parallel execution)
**Cons**: More complex, requires async

### Pattern 3: Conditional Branching

**When**: Different queries need different subagents.

```python
class ConditionalCoordinator:
    """Invoke subagents based on query content."""
    
    def orchestrate(self, query):
        # Analyze what's needed
        if "code" in query:
            code_result = self.subagents["code"].execute(query)
        
        if "data" in query:
            data_result = self.subagents["data"].execute(query)
        
        if "security" in query:
            security_result = self.subagents["security"].execute(query)
        
        # Combine results
        return self.combine_results({
            "code": code_result if "code" in query else None,
            "data": data_result if "data" in query else None,
            "security": security_result if "security" in query else None,
        })
```

**Pros**: Efficient (only invoke what's needed)
**Cons**: Analysis logic can get complex

### Pattern 4: Hierarchical (Multi-Level)

**When**: Complex task broken into sub-coordinators.

```python
class HierarchicalCoordinator:
    """Coordinator that delegates to sub-coordinators."""
    
    def __init__(self):
        # Sub-coordinators for each domain
        self.market_coordinator = MarketCoordinator()
        self.tech_coordinator = TechCoordinator()
        self.finance_coordinator = FinanceCoordinator()
    
    def orchestrate(self, query):
        # Each domain is coordinated independently
        market_result = self.market_coordinator.analyze(query)
        tech_result = self.tech_coordinator.analyze(query)
        finance_result = self.finance_coordinator.analyze(query)
        
        # Synthesize cross-domain
        return self.synthesize(market_result, tech_result, finance_result)
```

**Pros**: Scalable to complex problems, clear separation
**Cons**: More complex, harder to debug

---

## Task Decomposition: Decision Framework

### Decomposition Quality Checklist

For each proposed decomposition, ask:

```
✓ Cohesion: Is each task coherent?
  - Can a subagent understand the task alone?
  - No?  → Tasks are too small (over-decomposed)
  - Yes? → Continue

✓ Independence: Can tasks run in parallel?
  - Are there true dependencies?
  - Unclear? → Combine tasks

✓ Coverage: Do tasks cover the full query?
  - Run each task independently
  - Would combining give different answer?
  - Yes? → You're missing synthesis

✓ Scope: Is each task appropriately scoped?
  - Too small (< 2 minutes work) → Over-decomposed
  - Too large (> 30 minutes work) → Under-decomposed
  - Just right (5-15 minutes) → Good!

✓ Clarity: Can subagent understand unambiguously?
  - Show task to non-expert
  - Can they explain what to do?
  - No? → Rewrite task instruction
```

### Anti-Patterns in Decomposition

**Anti-Pattern 1: Atomic Task Decomposition**

```python
# ❌ WRONG: Each task is too small
tasks = {
    "t1": "Count records in database",
    "t2": "Count unique customers",
    "t3": "Sum total revenue",
    "t4": "Calculate average",
    "t5": "Calculate percentiles",
    "t6": "Describe results"
}
# Each task is tiny and disconnected
# Coordinator must stitch everything together
```

**Better Approach**:

```python
# ✓ CORRECT: Group related tasks
tasks = {
    "data_analysis": """
Analyze the data:
1. Calculate key statistics (mean, median, std dev, percentiles)
2. Count records and unique customers
3. Calculate total and average revenue
4. Identify outliers

Return structured JSON with all metrics.
""",
    
    "insights": """
Given the statistical analysis:
1. What are the key findings?
2. What business implications?
3. What should we do about it?
"""
}
```

**Anti-Pattern 2: Information Loss**

```python
# ❌ WRONG: Narrow decomposition loses context
query = "We want to expand into Asia. Give us a strategy."

tasks = {
    "t1": "List Asian countries",
    "t2": "Find population of each country",
    "t3": "Find GDP of each country",
    "t4": "Find technology adoption rates",
}

# Result: List of facts, not strategy
# Missing: competition analysis, regulatory, our capabilities
```

**Better Approach**:

```python
# ✓ CORRECT: Balanced decomposition with synthesis
tasks = {
    "market_opportunity": """
Analyze Asian market opportunity for our product:
1. Market size and growth
2. Customer segments
3. Technology adoption
4. Key competitors

Provide prioritized list of attractive markets.
""",
    
    "strategy": """
Given market opportunities:
1. Which markets align with our capabilities?
2. Entry strategy for each market
3. Key risks and mitigation
4. Resource requirements

Provide strategic recommendations.
"""
}
```

**Anti-Pattern 3: Circular Dependencies**

```python
# ❌ WRONG: Task A depends on B, B depends on A
tasks = {
    "market": {
        "depends_on": ["financial"]  # Wait for financial
    },
    "financial": {
        "depends_on": ["market"]  # Wait for market
    }
}
# Deadlock! Neither can execute.
```

**Solution**: Reanalyze decomposition

```python
# ✓ CORRECT: Clear execution order
tasks = {
    "market": {
        "depends_on": []  # Can run immediately
    },
    "financial": {
        "depends_on": ["market"]  # Uses market findings
    }
}
```

---

## Context Isolation Patterns

### Pattern: Minimal Context

**Principle**: Pass only what the subagent absolutely needs.

```python
# ❌ WRONG: Pass everything
full_context = {
    "entire_conversation": self.history,
    "all_previous_results": self.all_results,
    "system_state": self.state,
    "user_preferences": self.user_prefs,
    "company_secrets": self.secrets,
}

subagent.execute("Analyze revenue", context=full_context)

# Subagent is distracted and confused by irrelevant data
```

```python
# ✓ CORRECT: Pass only what's needed
relevant_context = {
    "revenue_data": extract_revenue(self.history),
    "time_period": "Q3 2024",
}

subagent.execute("Analyze revenue", context=relevant_context)

# Subagent is focused and efficient
```

### Pattern: Progressive Context

**Principle**: Subagents can use results from other subagents through coordinator.

```python
def orchestrate(self, query):
    # Task 1: Gather raw data
    data_result = self.subagents["data_gatherer"].execute(
        "Gather sales data",
        context=None  # No prior context needed
    )
    
    # Task 2: Analyze data (can reference Task 1)
    analysis_result = self.subagents["analyst"].execute(
        "Analyze sales patterns",
        context={
            "data": data_result.content  # From Task 1
        }
    )
    
    # Task 3: Synthesize (can reference Tasks 1+2)
    synthesis = self.subagents["strategist"].execute(
        "Synthesize into strategy",
        context={
            "data": data_result.content,      # From Task 1
            "analysis": analysis_result.content  # From Task 2
        }
    )
    
    return synthesis.content
```

### Anti-Pattern: Context Pollution

```python
# ❌ WRONG: Subagent inherits coordinator's entire history
coordinator_context = {
    "query_1": "What is AI?",
    "query_2": "What is ML?",
    "query_3": "What is deep learning?",
    "query_4": "How to build an agent?",  # Current query
    "all_previous_responses": [...],
    "system_metrics": {...},
    "user_history": {...},
}

# Pass all of this to subagent!
subagent.execute("Analyze agent architecture", context=coordinator_context)

# Subagent's context window is bloated with irrelevant information
```

---

## Error Handling Patterns

### Pattern 1: Fallback Subagents

```python
def execute_with_fallback(self, task, primary_subagent, fallback_subagent):
    """Try primary, fall back if it fails."""
    
    # Try primary
    result = primary_subagent.execute(task)
    
    if result.success:
        return result
    
    # Fall back to alternative
    print(f"Primary failed, trying fallback...")
    fallback_result = fallback_subagent.execute(task)
    
    return fallback_result
```

### Pattern 2: Partial Failure Handling

```python
def synthesize_with_partial_results(self, results: Dict[str, TaskResult]):
    """Handle case where some subagents failed."""
    
    successful = {k: v for k, v in results.items() if v.success}
    failed = {k: v for k, v in results.items() if not v.success}
    
    if len(successful) == 0:
        return "All subagents failed. Unable to answer."
    
    if len(failed) == 0:
        return "All subagents succeeded. Proceeding with synthesis."
    
    # Partial failure - synthesize with what we have
    partial_input = "Partial analysis (some subagents failed):\n"
    
    for task_id, result in successful.items():
        partial_input += f"\n{task_id}: {result.content}\n"
    
    for task_id, result in failed.items():
        partial_input += f"\n{task_id}: FAILED - {result.error}\n"
    
    # Synthesize with degraded results
    return self.coordinator.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        system="""You are synthesizing analysis where some specialists failed.
        Work with what you have and note what's missing.""",
        messages=[{"role": "user", "content": partial_input}]
    )
```

---

## Exam Preparation

### Key Concepts to Know

**1. Hub-and-Spoke Architecture**
- Coordinator is the single point of routing
- Subagents don't communicate directly
- All information flows through coordinator
- Why: Simplicity, error isolation, central monitoring

**2. Context Isolation**
- Subagents do NOT inherit coordinator's history
- Each subagent has independent context window
- Coordinator explicitly passes needed context
- Why: Efficiency, clarity, focus

**3. Coordinator Responsibilities**
- Task decomposition (breaking complex into simple)
- Subagent selection (which specialist for which task)
- Delegation (passing task with context)
- Result aggregation (combining findings)
- Synthesis (generating final answer)
- Error handling (recovery and retry)

**4. Decomposition Risks**
- Over-decomposition: Too many tiny tasks, context lost
- Under-decomposition: Too few large tasks, no parallelization
- Bad boundaries: Incoherent tasks
- Missing coverage: Incomplete analysis

**5. Execution Patterns**
- Sequential: Tasks in order, each depends on previous
- Parallel: Independent tasks run concurrently
- Conditional: Only invoke needed subagents
- Hierarchical: Multi-level coordinators

### Practice Questions

**Q1**: When should you NOT use a multi-agent system?
A: When a single agent can handle the task within context window.

**Q2**: What happens if you pass the coordinator's full conversation history to a subagent?
A: Context explosion, subagent gets distracted, less efficient.

**Q3**: How should a coordinator handle conflicting recommendations from subagents?
A: Invoke a synthesizer subagent to analyze tradeoffs and recommend resolution.

**Q4**: What's the risk of decomposing a query into 8 tiny subtasks?
A: Over-decomposition. Subtasks lose context, become disconnected, coordinator must stitch everything together.

**Q5**: Can subagents communicate directly with each other?
A: No. Hub-and-spoke pattern: all communication through coordinator.

**Q6**: A subagent fails. What should the coordinator do?
A: Log error, either retry with refined task or invoke fallback subagent.

**Q7**: How do you implement parallel execution?
A: Use asyncio.gather() or similar to run independent tasks concurrently.

**Q8**: What should be in the context passed to a subagent?
A: Only information that subagent needs to complete its specific task.

---

## Anti-Patterns Summary

| Anti-Pattern | Description | Fix |
|---|---|---|
| Context Pollution | Pass all coordinator context | Pass only relevant parts |
| Over-decomposition | 5+ tiny fragmented tasks | Combine into 3-4 coherent tasks |
| Under-decomposition | Single huge monolithic task | Break into focused subtasks |
| Direct Communication | Subagents talk to each other | Route all through coordinator |
| Implicit Dependencies | Unclear task order | Make dependencies explicit |
| Ambiguous Instructions | Vague task descriptions | Write clear, detailed instructions |
| Lost Results | Don't preserve subagent outputs | Aggregate and synthesize properly |
| No Error Handling | Fail if any subagent fails | Implement retries and fallbacks |
| Poor Monitoring | Don't track performance | Log metrics, track costs |

---

## Real-World Examples

### Example 1: Content Analysis (Good Decomposition)

```python
def analyze_content(user_query):
    """Analyze content across multiple dimensions."""
    
    # Decomposition
    tasks = {
        "sentiment": "Analyze sentiment and tone",
        "themes": "Extract key themes and topics",
        "entities": "Identify named entities (people, places, companies)",
        "summary": "Create concise summary"
    }
    
    # Why this works:
    # ✓ Each task is coherent and focused
    # ✓ Tasks can run in parallel (independent)
    # ✓ Output of each is useful on its own
    # ✓ Easy to synthesize into final report
```

### Example 2: Market Analysis (Balanced Decomposition)

```python
def analyze_market(market, product):
    """Analyze market opportunity."""
    
    # Decomposition
    tasks = {
        "market_size": """
        Analyze market size and growth:
        - Current size and growth rate
        - Growth drivers
        - Market segments
        """,
        
        "competition": """
        Analyze competitive landscape:
        - Key competitors
        - Market share
        - Competitive positioning
        """,
        
        "strategy": """
        Develop market entry strategy using findings from:
        - Market analysis
        - Competitive analysis
        - Our capabilities
        
        Return: Entry strategy with key success factors
        """
    }
    
    # Why this works:
    # ✓ "market_size" and "competition" can run in parallel
    # ✓ "strategy" depends on the above (sequential)
    # ✓ Each task has appropriate scope
    # ✓ Clear synthesis at the end
```

---

## Conclusion: When You Use This Knowledge

On the exam, you'll see scenarios like:

> "A coordinator is analyzing a market. It decomposed the task into 12 subtasks: 
> 'Extract market size', 'Extract growth rate', 'Extract customer count', etc.
> What's the problem?"

**Answer**: Over-decomposition. These should be combined into "Market analysis" which includes all of these. The decomposition is too narrow and lacks coherence.

> "A subagent is failing on a task. The coordinator passes its entire 
> 50,000-token conversation history to help the subagent. Good idea?"

**Answer**: No. This violates context isolation principle. Pass only the relevant data the subagent needs for its specific task.

> "Should coordinator and subagents communicate directly?"

**Answer**: No. Hub-and-spoke: all communication through coordinator. Subagents only talk to coordinator.

Master these concepts and you'll ace the multi-agent orchestration portion of the certification.
