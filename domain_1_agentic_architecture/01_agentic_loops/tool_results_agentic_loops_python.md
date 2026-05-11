# Tool Results in Conversation History: Agentic Loops in Claude Code (Python)

## Core Concept

In agentic loops, anything not in the conversation history is invisible to the model. If your runtime does something between tool calls — logs, metrics, side effects — the model has no idea it happened unless you explicitly append it as part of a tool result or an injected message.

The fundamental principle is: **the model can only reason about information that appears in the conversation history**. Instead of rebuilding the messages array from scratch on each request, keep a running list and append to it. Every turn sees the complete prior context.

---

## The Message Lifecycle in Claude Code

When you start an agent, the SDK runs the same execution loop that powers Claude Code: Claude evaluates your prompt, calls tools to take action, receives the results, and repeats until the task is complete.

### Ring 1: Single Tool Call (Simplest Agentic Model)

```python
import anthropic
import json

# Initialize the Anthropic client
client = anthropic.Anthropic()

# Minimal structure: one tool, one call, one result
messages = [
    {"role": "user", "content": "What files are in the project?"}
]

# Define available tools
tools = [
    {
        "name": "bash",
        "description": "Execute shell commands",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                }
            },
            "required": ["command"]
        }
    }
]

# Step 1: Call Claude with the tool definition
response = client.messages.create(
    model="claude-opus-4-6",
    max_tokens=1024,
    tools=tools,
    messages=messages
)

# Response contains: stop_reason: "tool_use" and a tool_use content block
# Example response structure:
# {
#     "role": "assistant",
#     "content": [{
#         "type": "tool_use",
#         "id": "toolu_012...",
#         "name": "bash",
#         "input": {"command": "find . -type f"}
#     }]
# }

# Step 2: Execute the tool
def execute_bash(command):
    """Execute a bash command and return the output."""
    import subprocess
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "Error: Command timed out"
    except Exception as e:
        return f"Error: {str(e)}"

# Extract tool use from response
tool_use_block = next(
    (block for block in response.content if block.type == "tool_use"),
    None
)

if tool_use_block:
    # Execute the tool
    tool_result = execute_bash(tool_use_block.input["command"])
    # Example result: "app.py\npackage.json\nREADME.md\n..."

    # Step 3: Append assistant response to messages
    messages.append({
        "role": "assistant",
        "content": response.content
    })

    # Step 4: Create tool result and append it
    tool_result_message = {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_use_block.id,  # ← Links back to tool_use
                "content": tool_result
            }
        ]
    }
    messages.append(tool_result_message)

    print("Messages array after Turn 1:")
    print(json.dumps(messages, indent=2, default=str))
```

**Key insight**: The `tool_result` references the `tool_use_id` from the assistant's previous response. This linking is how Claude knows which result corresponds to which tool call.

---

### Ring 2: The Agentic Loop (Full Loop with Reasoning)

This is where recursion creates a system with no fixed "end" state. The agent only returns control when the model explicitly decides it's done — meaning the default behavior is continue until resolved, not respond once and stop.

```python
import anthropic
import os
import subprocess
from pathlib import Path

client = anthropic.Anthropic()

# System prompt for the agent
SYSTEM_PROMPT = """You are an expert debugging assistant. 
You can:
- Read files to understand code structure
- Run bash commands to execute tests
- Edit files to fix bugs
- Verify fixes by running tests again

When debugging, be systematic:
1. Read the failing test to understand expectations
2. Read the implementation to understand current behavior
3. Identify the root cause
4. Fix the issue
5. Verify the fix works

Always provide clear explanations of what you found and fixed."""

# Tool definitions
TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to read"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "The path to the file to write"
                },
                "content": {
                    "type": "string",
                    "description": "The content to write"
                }
            },
            "required": ["path", "content"]
        }
    },
    {
        "name": "bash",
        "description": "Execute bash commands",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                }
            },
            "required": ["command"]
        }
    }
]

# Tool execution functions
def read_file(path):
    """Read file contents."""
    try:
        with open(path, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error: {str(e)}"

def write_file(path, content):
    """Write content to file."""
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            f.write(content)
        return f"File written successfully: {path}"
    except Exception as e:
        return f"Error: {str(e)}"

def execute_bash(command):
    """Execute a bash command."""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "Error: Command timed out (>30 seconds)"
    except Exception as e:
        return f"Error: {str(e)}"

def execute_tool(tool_name, tool_input):
    """Execute a tool based on its name."""
    if tool_name == "read_file":
        return read_file(tool_input["path"])
    elif tool_name == "write_file":
        return write_file(tool_input["path"], tool_input["content"])
    elif tool_name == "bash":
        return execute_bash(tool_input["command"])
    else:
        return f"Error: Unknown tool {tool_name}"

def agent_loop(user_input, max_turns=10):
    """
    Run the agentic loop until the model produces a text-only response.
    
    The loop:
    1. Send prompt + full conversation history to Claude
    2. Claude decides: call tools or return text?
    3. If tools: execute them and append results to history
    4. If text-only: task complete, return
    5. Repeat with updated history
    """
    messages = [
        {"role": "user", "content": user_input}
    ]
    
    turn_count = 0
    
    while turn_count < max_turns:
        turn_count += 1
        print(f"\n{'='*60}")
        print(f"Turn {turn_count}: Calling Claude with {len(messages)} messages in history")
        print(f"{'='*60}")
        
        # Step 1: CALL MODEL with accumulated history
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        
        # Step 2: APPEND Assistant response to history
        messages.append({
            "role": "assistant",
            "content": response.content
        })
        
        # Step 3: CHECK if done (no tool calls, model produced final text)
        if response.stop_reason == "end_turn":
            # Model produced text-only response
            text_blocks = [block for block in response.content if hasattr(block, 'text')]
            if text_blocks:
                final_text = text_blocks[0].text
                print(f"\n✓ Task complete!")
                print(f"Final response:\n{final_text}")
                return {
                    "type": "final",
                    "text": final_text,
                    "turns": turn_count
                }
        
        # Step 4: EXECUTE each tool
        tool_uses = [block for block in response.content if block.type == "tool_use"]
        
        if not tool_uses:
            # No tools to execute, but stop_reason wasn't end_turn
            # This shouldn't happen in normal operation
            print("No tools to execute but loop didn't end. Stopping.")
            break
        
        tool_results = []
        
        for tool_use in tool_uses:
            print(f"\nExecuting tool: {tool_use.name}")
            print(f"Input: {tool_use.input}")
            
            # Execute the tool
            result = execute_tool(tool_use.name, tool_use.input)
            
            print(f"Result (first 200 chars): {result[:200]}...")
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
                "is_error": result.startswith("Error:")
            })
        
        # Step 5: APPEND all results to history (in a single user turn)
        messages.append({
            "role": "user",
            "content": tool_results
        })
        
        print(f"\nContext after turn {turn_count}:")
        print(f"  - Messages in history: {len(messages)}")
        print(f"  - Total content blocks: {sum(len(m.get('content', [])) if isinstance(m.get('content'), list) else 1 for m in messages)}")
    
    # Max turns exceeded
    if turn_count >= max_turns:
        return {
            "type": "error",
            "message": f"Max turns ({max_turns}) exceeded",
            "turns": turn_count
        }

# Example usage
if __name__ == "__main__":
    result = agent_loop(
        "The login_test.py test is failing. Debug and fix it, then verify the fix works."
    )
    print(f"\nFinal result: {result}")
```

---

## How Results Flow Back into Reasoning

The critical moment is when tool results get appended. Because there is an agentic loop, each Claude invocation is passed the accumulated conversation history in a structured messages list with role alternation (user/assistant). Claude can return multiple tool calls in a single response, and can mix text with tool calls in the same response.

### Message List Structure at Each Turn

```python
# After Turn 1 (user input)
messages = [
    {"role": "user", "content": "Analyze this CSV file"}
]

# After Turn 1 completes (assistant calls tool)
messages = [
    {"role": "user", "content": "Analyze this CSV file"},
    {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "t1",
                "name": "read_file",
                "input": {"path": "data.csv"}
            }
        ]
    }
]

# After Turn 1 tool execution (result appended)
messages = [
    {"role": "user", "content": "Analyze this CSV file"},
    {
        "role": "assistant",
        "content": [
            {
                "type": "tool_use",
                "id": "t1",
                "name": "read_file",
                "input": {"path": "data.csv"}
            }
        ]
    },
    {
        "role": "user",  # ← User turn (even though it's from the system)
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": "t1",  # ← Links back to assistant's request
                "content": "col1,col2,col3\n1,2,3\n4,5,6\n..."
            }
        ]
    }
]

# On Turn 2, Claude sees the ENTIRE list above
# It can reason: "I asked for data.csv, got these rows..."
# Then it might call another tool: tool_use(analyze_data)
# That result ALSO gets appended

messages = [
    {"role": "user", "content": "Analyze this CSV file"},
    {"role": "assistant", "content": [tool_use(read_file)]},
    {"role": "user", "content": [tool_result: "CSV content"]},
    {"role": "assistant", "content": [tool_use(analyze_data)]},
    {"role": "user", "content": [tool_result: "Analysis results"]},
    # ... and so on
]
```

---

## Context Window Management in Agentic Loops

The context window is the total amount of information available to Claude during a session. It does not reset between turns within a session. Everything accumulates: the system prompt, tool definitions, conversation history, tool inputs, and tool outputs. Content that stays the same across turns (system prompt, tool definitions, CLAUDE.md) is automatically prompt cached, which reduces cost and latency for repeated prefixes.

### Growth and Constraints (Python Example)

```python
def estimate_message_tokens(messages):
    """
    Rough estimate of tokens in messages.
    Actual token count requires Claude's tokenizer, but this gives an order of magnitude.
    Rule of thumb: ~4 characters ≈ 1 token
    """
    total_chars = 0
    
    for message in messages:
        if isinstance(message.get("content"), str):
            total_chars += len(message["content"])
        elif isinstance(message.get("content"), list):
            for block in message["content"]:
                if isinstance(block, dict) and "content" in block:
                    total_chars += len(str(block["content"]))
                if isinstance(block, dict) and "text" in block:
                    total_chars += len(block["text"])
    
    estimated_tokens = total_chars // 4
    return estimated_tokens

def monitor_context(messages, warn_threshold=80000, critical_threshold=95000):
    """
    Monitor context usage and warn when approaching limits.
    """
    estimated_tokens = estimate_message_tokens(messages)
    
    if estimated_tokens > critical_threshold:
        print(f"⚠️  CRITICAL: Context at {estimated_tokens:,} tokens (>95% of 100k limit)")
        return "critical"
    elif estimated_tokens > warn_threshold:
        print(f"⚠️  WARNING: Context at {estimated_tokens:,} tokens (approaching limit)")
        return "warning"
    else:
        print(f"✓ Context healthy: {estimated_tokens:,} tokens")
        return "healthy"

# Usage example
messages = [
    {"role": "user", "content": "Read a 50KB file..."},
    {"role": "assistant", "content": [{"type": "tool_use", "name": "read_file"}]},
    {"role": "user", "content": [{"type": "tool_result", "content": "...large file content..."}]},
]

status = monitor_context(messages)

# Simplified cost model
class ContextTracker:
    """Track context usage across turns."""
    
    def __init__(self, max_tokens=100000, overhead=8000):
        """
        max_tokens: Maximum context window (typically 100,000 for Opus)
        overhead: Initial tokens used by system prompt + tools (cached)
        """
        self.max_tokens = max_tokens
        self.cached_tokens = overhead  # System prompt, tool defs (cached)
        self.used_tokens = overhead
        self.turns = 0
    
    def add_turn(self, user_msg_chars, assistant_response_chars, tool_result_chars):
        """Add tokens for a turn."""
        self.turns += 1
        
        # First turn: all tokens counted
        # Later turns: history is repriced, but system/tools stay cached
        user_tokens = user_msg_chars // 4
        assistant_tokens = assistant_response_chars // 4
        result_tokens = tool_result_chars // 4
        
        # Total = cached + current history
        self.used_tokens = self.cached_tokens + user_tokens + assistant_tokens + result_tokens
        
        return {
            "turn": self.turns,
            "turn_tokens": user_tokens + assistant_tokens + result_tokens,
            "total_tokens": self.used_tokens,
            "percent_used": (self.used_tokens / self.max_tokens) * 100
        }
    
    def should_compact(self, threshold=92):
        """Check if context compaction should trigger."""
        percent = (self.used_tokens / self.max_tokens) * 100
        return percent >= threshold

# Usage
tracker = ContextTracker()

stats = tracker.add_turn(
    user_msg_chars=100,
    assistant_response_chars=200,
    tool_result_chars=5000
)
print(f"Turn {stats['turn']}: {stats['total_tokens']:,} tokens ({stats['percent_used']:.1f}%)")

if tracker.should_compact():
    print("→ Time to compact context (92% threshold reached)")
```

---

## Practical Example: Multi-Turn Debugging Session

```python
import anthropic
import subprocess
from pathlib import Path

client = anthropic.Anthropic()

def multi_turn_debug_example():
    """
    Scenario: "Fix the failing login test"
    
    This demonstrates a complete multi-turn agentic session where Claude:
    1. Reads the test file to understand what's failing
    2. Reads the implementation to see how it works
    3. Identifies the mismatch
    4. Fixes the test
    5. Verifies the fix works
    """
    
    # Setup: Create test files
    test_content = '''
def test_login_valid():
    """Test login with valid credentials"""
    result = login('user@example.com', 'password123')
    assert result['token'] is not None
    assert result['status'] == 200  # ← This might be wrong
    
def test_login_invalid():
    """Test login with invalid credentials"""
    result = login('user@example.com', 'wrong')
    assert result['error'] is not None
'''
    
    auth_content = '''
import jwt

def login(email, password):
    """Login user and return token"""
    # Returns 201 (created), not 200
    return {
        'token': jwt.encode({'email': email}, 'secret'),
        'status': 201  # ← Created, not OK
    }
'''
    
    Path("auth_test.py").write_text(test_content)
    Path("auth.py").write_text(auth_content)
    
    # System prompt
    system = """You are debugging a Python authentication system. 
    Help identify and fix issues with login tests and implementation."""
    
    # Tools
    tools = [
        {
            "name": "read_file",
            "description": "Read file contents",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"}
                },
                "required": ["path"]
            }
        },
        {
            "name": "edit_file",
            "description": "Edit a file by replacing old_str with new_str",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "old_str": {"type": "string"},
                    "new_str": {"type": "string"}
                },
                "required": ["path", "old_str", "new_str"]
            }
        },
        {
            "name": "bash",
            "description": "Execute bash commands",
            "input_schema": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"}
                },
                "required": ["command"]
            }
        }
    ]
    
    def execute_tool(name, input_data):
        if name == "read_file":
            try:
                return Path(input_data["path"]).read_text()
            except Exception as e:
                return f"Error: {e}"
        elif name == "edit_file":
            try:
                content = Path(input_data["path"]).read_text()
                new_content = content.replace(
                    input_data["old_str"],
                    input_data["new_str"]
                )
                Path(input_data["path"]).write_text(new_content)
                return "File updated successfully"
            except Exception as e:
                return f"Error: {e}"
        elif name == "bash":
            try:
                result = subprocess.run(
                    input_data["command"],
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return result.stdout + result.stderr
            except Exception as e:
                return f"Error: {e}"
    
    # ============ Run the agentic loop ============
    messages = [
        {
            "role": "user",
            "content": "The auth_test.py test is failing. Debug and fix it, then verify it passes."
        }
    ]
    
    print("Starting multi-turn debug session...")
    print(f"Initial message: {messages[0]['content']}\n")
    
    turn = 0
    max_turns = 10
    
    while turn < max_turns:
        turn += 1
        print(f"\n{'='*70}")
        print(f"Turn {turn}")
        print(f"{'='*70}")
        print(f"Conversation history has {len(messages)} messages")
        
        # Call Claude with accumulated history
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2048,
            system=system,
            tools=tools,
            messages=messages
        )
        
        # Append assistant response
        messages.append({
            "role": "assistant",
            "content": response.content
        })
        
        # Check if done
        if response.stop_reason == "end_turn":
            text_block = next(
                (b for b in response.content if hasattr(b, 'text')),
                None
            )
            if text_block:
                print(f"\n✓ Task complete!")
                print(f"Final response:\n{text_block.text}")
                return {
                    "status": "complete",
                    "turns": turn,
                    "final_message": text_block.text
                }
        
        # Extract and execute tools
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        
        if not tool_uses:
            print("No tools requested but loop didn't end")
            break
        
        tool_results = []
        
        for tool_use in tool_uses:
            print(f"\nTool: {tool_use.name}")
            print(f"Input: {tool_use.input}")
            
            result = execute_tool(tool_use.name, tool_use.input)
            
            # Show first 300 chars of result
            result_preview = result[:300] if len(result) > 300 else result
            print(f"Result: {result_preview}")
            if len(result) > 300:
                print(f"... ({len(result)} chars total)")
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
                "is_error": result.startswith("Error:")
            })
        
        # Append tool results
        messages.append({
            "role": "user",
            "content": tool_results
        })
    
    return {
        "status": "max_turns_exceeded",
        "turns": turn,
        "message": f"Exceeded max turns ({max_turns})"
    }

# Run the example
if __name__ == "__main__":
    result = multi_turn_debug_example()
    print(f"\n\nFinal result: {result}")
```

---

## Key Design Patterns for Agentic Loops

### 1. Always Append, Never Replace

```python
# ❌ WRONG: Rebuilding from scratch loses context
messages = [{"role": "user", "content": "..."}]

# ✅ CORRECT: Append to maintain full history
messages.append({"role": "assistant", "content": response.content})
messages.append({"role": "user", "content": tool_results})
```

### 2. Tool Results Must Be Explicit

```python
# ❌ WRONG: Model doesn't know what happened outside the loop
result = read_file("data.json")
# Claude has no idea what data.json contains!

# ✅ CORRECT: Always append results as tool_result
messages.append({
    "role": "user",
    "content": [{
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": result,
        "is_error": False
    }]
})
```

### 3. Errors Are Information Too

```python
# Errors still get appended (with is_error flag)
try:
    result = read_file("data.json")
except FileNotFoundError:
    result = "File not found"
    is_error = True

messages.append({
    "role": "user",
    "content": [{
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": result,
        "is_error": is_error
    }]
})

# Claude now knows: "I tried to read that file but it doesn't exist"
# → Next action might be: create the file, or search elsewhere
```

### 4. One User Turn Per Tool Execution Batch

```python
# ✅ CORRECT: All tool results in one user turn
messages.append({
    "role": "user",
    "content": [
        {"type": "tool_result", "tool_use_id": "call_1", "content": "result1"},
        {"type": "tool_result", "tool_use_id": "call_2", "content": "result2"},
        {"type": "tool_result", "tool_use_id": "call_3", "content": "result3"}
    ]
})
```

---

## Production Considerations

### Prevent Infinite Loops

```python
def agent_loop_with_limits(user_input, max_turns=10, max_budget_usd=5.00):
    """Run agent with hard limits on turns and cost."""
    messages = [{"role": "user", "content": user_input}]
    turn_count = 0
    total_cost = 0.0
    
    # Rough pricing (update with actual rates)
    INPUT_COST_PER_MTOK = 3.00      # $3 per million input tokens
    OUTPUT_COST_PER_MTOK = 15.00    # $15 per million output tokens
    
    while turn_count < max_turns:
        # ... agent logic ...
        
        turn_count += 1
        
        # Estimate cost of this turn
        input_tokens = estimate_message_tokens(messages) // 1_000_000
        output_tokens = 1000 // 1_000_000  # Rough estimate
        
        turn_cost = (input_tokens * INPUT_COST_PER_MTOK + 
                     output_tokens * OUTPUT_COST_PER_MTOK)
        total_cost += turn_cost
        
        if total_cost > max_budget_usd:
            return {
                "status": "budget_exceeded",
                "turns": turn_count,
                "cost_usd": total_cost,
                "limit_usd": max_budget_usd
            }
    
    if turn_count >= max_turns:
        return {
            "status": "max_turns_exceeded",
            "turns": turn_count,
            "cost_usd": total_cost
        }
```

### Monitor Context Growth

```python
class ContextMonitor:
    """Monitor context growth and provide recommendations."""
    
    def __init__(self, warning_percent=80, critical_percent=92):
        self.messages = []
        self.warning_percent = warning_percent
        self.critical_percent = critical_percent
    
    def add_message(self, role, content):
        """Add a message and check context status."""
        self.messages.append({"role": role, "content": content})
        
        tokens = self.estimate_tokens()
        percent = (tokens / 100_000) * 100  # Assuming 100k context window
        
        status = {
            "tokens": tokens,
            "percent": percent,
            "message_count": len(self.messages)
        }
        
        if percent >= self.critical_percent:
            status["recommendation"] = "CRITICAL: Trigger compaction immediately"
        elif percent >= self.warning_percent:
            status["recommendation"] = "WARNING: Consider compaction soon"
        else:
            status["recommendation"] = "HEALTHY: No action needed"
        
        return status
    
    def estimate_tokens(self):
        """Estimate total tokens in conversation."""
        total_chars = 0
        for msg in self.messages:
            if isinstance(msg.get("content"), str):
                total_chars += len(msg["content"])
            elif isinstance(msg.get("content"), list):
                total_chars += sum(
                    len(str(block.get("content", ""))) 
                    for block in msg["content"]
                )
        return total_chars // 4

# Usage
monitor = ContextMonitor()

status = monitor.add_message("user", "Analyze this file...")
print(f"Status: {status}")

status = monitor.add_message("assistant", [{"type": "tool_use", "name": "read_file"}])
print(f"Status: {status}")

status = monitor.add_message("user", [{"type": "tool_result", "content": "...large output..."}])
print(f"Status: {status}")
```

### Compress Large Results

```python
def compress_tool_result(result, max_chars=2000):
    """Compress large tool results to prevent context explosion."""
    if len(result) <= max_chars:
        return result
    
    # Strategy 1: Take last N lines (for logs)
    if "\n" in result:
        lines = result.split("\n")
        # Keep first 5 lines + last 10 lines
        summary = "\n".join(lines[:5]) + "\n... [truncated] ...\n"
        summary += "\n".join(lines[-10:])
        if len(summary) <= max_chars:
            return summary
    
    # Strategy 2: Truncate with indicator
    return result[:max_chars] + f"\n... [{len(result) - max_chars} chars truncated]"

# Usage
large_file_output = read_file("huge.log")
compressed = compress_tool_result(large_file_output)

messages.append({
    "role": "user",
    "content": [{
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": compressed
    }]
})
```

---

## Summary

The agentic loop's power comes from treating each step as a fresh invocation with updated state through recursion. By appending tool results to the conversation history on every turn:

1. **Claude maintains context** – Previous observations stay visible
2. **Feedback loops work** – Results inform the next decision
3. **Tasks complete autonomously** – No human intervention needed between turns
4. **Reasoning chains form** – Multi-step plans emerge naturally

In Python, the pattern is straightforward:

```python
messages = [{"role": "user", "content": initial_prompt}]

while True:
    # 1. Send accumulated history
    response = client.messages.create(messages=messages, ...)
    
    # 2. Append assistant response
    messages.append({"role": "assistant", "content": response.content})
    
    # 3. Check if done
    if response.stop_reason == "end_turn":
        break  # Task complete
    
    # 4. Execute tools and collect results
    tool_results = [execute_tool(...) for tool in response.tools]
    
    # 5. Append results
    messages.append({"role": "user", "content": tool_results})
```

Claude Code implements this same loop with additional features (compaction, subagents, caching) but the core principle remains: keep a flat message history, append results, and send the full history on every turn. This simple recursive pattern enables powerful autonomous behavior.
