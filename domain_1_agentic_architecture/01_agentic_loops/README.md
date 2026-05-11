# Task 1.1 – Agentic Loops for Autonomous Task Execution

## Core Concept

The agentic loop is the heartbeat of any autonomous Claude agent. At each iteration, the model reads the full conversation history, decides whether to call a tool or finish, and either executes tools (appending results) or returns its final answer.

```
Send request + full conversation history
            │
            ▼
     Claude evaluates
            │
    ┌───────┴───────┐
    │               │
stop_reason      stop_reason
"tool_use"       "end_turn"
    │               │
Execute tools    Return final
    │             response
    ▼
Append tool_result to history
    │
    └──── Loop back ──────┘
```

## The Three Rules

1. **Continue** when `stop_reason == "tool_use"`
2. **Terminate** when `stop_reason == "end_turn"`
3. **Append** all tool results to conversation history before the next iteration

## Anti-Patterns (Exam Traps)

| Anti-Pattern | Why It Fails |
|---|---|
| Parse natural language to detect "I'm done" | Brittle, model may phrase differently |
| Use iteration cap as PRIMARY stopping mechanism | Terminates valid tasks prematurely |
| Check for assistant text content as completion indicator | Incorrect — model can mix text + tool_use |
| Skip appending tool results | Model can't reason about what happened |
