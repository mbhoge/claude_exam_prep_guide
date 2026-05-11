# Python Agentic Loops: Quick Start Guide

## The 5-Minute Summary

An agentic loop is a simple pattern where Claude Code:
1. **Receives** your prompt + full conversation history
2. **Decides** what tools to call (if any)
3. **Executes** the tools
4. **Appends** the results back to the conversation history
5. **Repeats** with the updated history until it returns text-only (task complete)

The magic: Claude sees not just what it asked for, but what it got back. This feedback loop enables autonomous task completion.

---

## Bare Minimum Example

```python
import anthropic

client = anthropic.Anthropic()

messages = [{"role": "user", "content": "Fix the failing test"}]

while True:
    # 1. Call Claude with accumulated history
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        tools=[...],  # Define your tools
        messages=messages
    )
    
    # 2. Append response
    messages.append({"role": "assistant", "content": response.content})
    
    # 3. Check if done
    if response.stop_reason == "end_turn":
        print("Done!")
        break
    
    # 4. Execute tools
    tool_results = []
    for tool_use in [b for b in response.content if b.type == "tool_use"]:
        result = execute_tool(tool_use.name, tool_use.input)
        tool_results.append({
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": result
        })
    
    # 5. Append results and loop
    messages.append({"role": "user", "content": tool_results})
```

That's it. Everything else is details.

---

## Message Structure at Each Step

```python
# After user input
messages = [
    {"role": "user", "content": "Your task"}
]

# After Claude responds (calls a tool)
messages = [
    {"role": "user", "content": "Your task"},
    {
        "role": "assistant",
        "content": [{
            "type": "tool_use",
            "id": "call_123",
            "name": "read_file",
            "input": {"path": "file.py"}
        }]
    }
]

# After tool executes (result appended)
messages = [
    {"role": "user", "content": "Your task"},
    {
        "role": "assistant",
        "content": [{...tool_use...}]
    },
    {
        "role": "user",  # System re-enters as "user"
        "content": [{
            "type": "tool_result",
            "tool_use_id": "call_123",  # ← Matches the call above
            "content": "file contents..."
        }]
    }
]

# On next turn, Claude sees ALL of the above
# and can reason with the file contents
```

**Key insight**: The `tool_use_id` on the result links back to the original request. This is how Claude knows which result matches which request.

---

## The Three Message Roles

| Role | When | Contains |
|------|------|----------|
| `user` | Initial prompt + after tools execute | Text message or list of tool results |
| `assistant` | When Claude responds | List of content blocks (text or tool_use) |
| (only 2 roles) | (message by message) | Alternates: user → assistant → user → ... |

Important: Tool results are sent back as a `user` role message (from the system's perspective).

---

## Tool Definition Template

```python
tools = [
    {
        "name": "operation_name",
        "description": "What this tool does",
        "input_schema": {
            "type": "object",
            "properties": {
                "param1": {
                    "type": "string",
                    "description": "What param1 is for"
                },
                "param2": {
                    "type": "integer",
                    "description": "What param2 is for"
                }
            },
            "required": ["param1"]  # param2 is optional
        }
    }
]
```

---

## Tool Execution Template

```python
def execute_tool(name: str, input_data: dict) -> str:
    """Execute a tool and return result as string."""
    try:
        if name == "read_file":
            return Path(input_data["path"]).read_text()
        elif name == "write_file":
            Path(input_data["path"]).write_text(input_data["content"])
            return "Written successfully"
        elif name == "bash":
            result = subprocess.run(
                input_data["command"],
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout + result.stderr
        else:
            return f"Unknown tool: {name}"
    except Exception as e:
        return f"Error: {e}"
```

---

## Extracting Content from Response

```python
# Get all tool uses
tool_uses = [b for b in response.content if b.type == "tool_use"]

# Get all text blocks
text_blocks = [b for b in response.content if hasattr(b, 'text')]

# Get first text block
text = next(
    (b.text for b in response.content if hasattr(b, 'text')),
    None
)

# Check if Claude is done
if response.stop_reason == "end_turn":
    # Task complete, Claude returned text-only response
    pass

if response.stop_reason == "tool_use":
    # Claude wants to call tools
    pass
```

---

## Context Window Tips

### Monitor Growth
```python
def estimate_tokens(messages):
    """Quick token estimate."""
    total_chars = sum(
        len(str(msg.get("content", "")))
        for msg in messages
    )
    return total_chars // 4  # ~4 chars per token

tokens = estimate_tokens(messages)
if tokens > 80_000:
    print(f"Warning: {tokens:,} tokens used")
```

### Compress Results
```python
def compress_result(result: str, max_chars: int = 2000) -> str:
    """Keep large results manageable."""
    if len(result) <= max_chars:
        return result
    return result[:max_chars] + f"\n... [{len(result) - max_chars} chars omitted]"

# Use it
messages.append({
    "role": "user",
    "content": [{
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": compress_result(large_output)
    }]
})
```

---

## Common Patterns

### Pattern 1: Sequential Tools
```python
# Run tools one at a time
for tool_use in tool_uses:
    result = execute_tool(tool_use.name, tool_use.input)
    # ... append result ...
```

### Pattern 2: Parallel Tools
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Run tools in parallel
with ThreadPoolExecutor() as executor:
    results = list(executor.map(
        lambda t: execute_tool(t.name, t.input),
        tool_uses
    ))
```

### Pattern 3: Error Handling
```python
result = "Error: initial"
try:
    result = execute_tool(name, input_data)
except FileNotFoundError:
    result = f"Error: File not found"
except Exception as e:
    result = f"Error: {e}"

tool_results.append({
    "type": "tool_result",
    "tool_use_id": tool_use.id,
    "content": result,
    "is_error": result.startswith("Error:")
})
```

### Pattern 4: Stopping the Loop
```python
MAX_TURNS = 10
turn = 0

while turn < MAX_TURNS:
    turn += 1
    # ... loop logic ...
    if response.stop_reason == "end_turn":
        break

if turn >= MAX_TURNS:
    print(f"Hit max turns limit ({MAX_TURNS})")
```

---

## Debugging Checklist

| Issue | Check |
|-------|-------|
| Claude not calling tools | Are tools defined? Is schema valid? Check model has permissions? |
| Tool results not appearing next turn | Is `tool_use_id` correct? Is result in a list inside `content`? |
| Loop never ends | Does Claude return `stop_reason: "end_turn"`? Did you set `max_turns`? |
| Context exploding | Are you compressing large tool outputs? Are you appending results every turn? |
| Token limit hit | Use `estimate_tokens()` to monitor. Compress results. Summarize old turns. |

---

## Real-World Example: File Debugger

```python
import anthropic
import subprocess
from pathlib import Path

def debug_file(filename: str):
    """Debug a Python file for errors."""
    
    client = anthropic.Anthropic()
    messages = [
        {
            "role": "user",
            "content": f"Debug {filename} and fix any issues"
        }
    ]
    
    tools = [
        {
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        },
        {
            "name": "run_python",
            "description": "Run Python code",
            "input_schema": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"]
            }
        },
        {
            "name": "write_file",
            "description": "Write to a file",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["path", "content"]
            }
        }
    ]
    
    def execute_tool(name, input_data):
        if name == "read_file":
            return Path(input_data["path"]).read_text()
        elif name == "run_python":
            result = subprocess.run(
                ["python", "-c", input_data["code"]],
                capture_output=True,
                text=True
            )
            return result.stdout + result.stderr
        elif name == "write_file":
            Path(input_data["path"]).write_text(input_data["content"])
            return "OK"
    
    for turn in range(10):
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            system="You are a Python debugging expert.",
            tools=tools,
            messages=messages
        )
        
        messages.append({"role": "assistant", "content": response.content})
        
        if response.stop_reason == "end_turn":
            # Get final text
            text = next(
                (b.text for b in response.content if hasattr(b, 'text')),
                ""
            )
            print(f"✓ Done: {text}")
            return
        
        # Execute tools
        tool_results = []
        for tool_use in [b for b in response.content if b.type == "tool_use"]:
            result = execute_tool(tool_use.name, tool_use.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result
            })
        
        messages.append({"role": "user", "content": tool_results})

# Usage
debug_file("app.py")
```

---

## When to Use Agentic Loops

✅ **Use when**:
- Task has multiple steps (read → analyze → fix → verify)
- You don't know in advance which tools you'll need
- Claude needs to reason about tool outputs to decide next action
- Task is complex and benefits from iteration

❌ **Don't use when**:
- You just need a single API call
- Tools always run in the same sequence
- You want to control flow explicitly (use regular code instead)
- Latency is critical (multiple calls = slower)

---

## Further Reading

- **Main guide**: `tool_results_agentic_loops_python.md`
- **Advanced patterns**: `advanced_python_agentic_patterns.md`
- **Language comparison**: `javascript_to_python_comparison.md`
- **Official docs**: https://docs.anthropic.com/en/docs/build-with-claude/agent-sdk/overview

---

## The One-Liner

> An agentic loop is: send prompt + history → Claude decides tools → execute tools → append results → repeat until text response.

Everything else is optimization and error handling around this core pattern.
