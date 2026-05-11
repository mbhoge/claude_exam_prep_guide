# JavaScript to Python: Agentic Loop Code Comparison

A quick reference guide showing how JavaScript agentic loop patterns translate directly to Python.

---

## 1. Basic Message Appending

### JavaScript
```javascript
const messages = [
  { role: "user", content: "Analyze this file" }
];

// Append assistant response
messages.push({
  role: "assistant",
  content: response.content
});

// Append tool results
messages.push({
  role: "user",
  content: toolResults
});
```

### Python
```python
messages = [
    {"role": "user", "content": "Analyze this file"}
]

# Append assistant response
messages.append({
    "role": "assistant",
    "content": response.content
})

# Append tool results
messages.append({
    "role": "user",
    "content": tool_results
})
```

**Key difference**: `push()` → `append()`

---

## 2. Tool Execution Loop

### JavaScript
```javascript
for (const toolUse of response.content.filter(c => c.type === "tool_use")) {
  let result;
  try {
    if (toolUse.name === "read_file") {
      result = await fs.readFile(toolUse.input.path, "utf-8");
    } else if (toolUse.name === "bash") {
      result = await exec(toolUse.input.command);
    }
  } catch (error) {
    result = `Error: ${error.message}`;
  }

  toolResults.push({
    type: "tool_result",
    tool_use_id: toolUse.id,
    content: result,
    is_error: result.startsWith("Error:")
  });
}
```

### Python
```python
for tool_use in [b for b in response.content if b.type == "tool_use"]:
    result = None
    try:
        if tool_use.name == "read_file":
            result = Path(tool_use.input["path"]).read_text()
        elif tool_use.name == "bash":
            result = subprocess.run(
                tool_use.input["command"],
                shell=True,
                capture_output=True,
                text=True
            ).stdout
    except Exception as e:
        result = f"Error: {str(e)}"

    tool_results.append({
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": result,
        "is_error": result.startswith("Error:")
    })
```

**Key differences**:
- `fs.readFile()` → `Path.read_text()`
- `await exec()` → `subprocess.run()`
- `try/catch` → `try/except`
- Dictionary access: `toolUse.name` → `tool_use.name`
- Object creation is identical

---

## 3. The Agentic Loop Structure

### JavaScript
```javascript
async function* agentLoop(messages, systemPrompt, tools) {
  while (true) {
    // 1. Call model
    const response = await anthropic.messages.create({
      model: "claude-opus-4-6",
      max_tokens: 4096,
      system: systemPrompt,
      tools: tools,
      messages: messages  // ← Full history every turn
    });

    // 2. Append response
    messages.push({ role: "assistant", content: response.content });

    // 3. Check if done
    if (response.stop_reason === "end_turn") {
      yield { type: "final", text: textBlock.text };
      return;
    }

    // 4. Execute tools
    const toolResults = [];
    for (const toolUse of response.content.filter(c => c.type === "tool_use")) {
      const result = await executeTool(toolUse.name, toolUse.input);
      toolResults.push({
        type: "tool_result",
        tool_use_id: toolUse.id,
        content: result
      });
    }

    // 5. Append results
    messages.push({ role: "user", content: toolResults });
    
    yield { type: "turn", toolCount: toolResults.length };
  }
}
```

### Python
```python
def agent_loop(user_input, system_prompt, tools, max_turns=10):
    messages = [{"role": "user", "content": user_input}]
    
    turn = 0
    while turn < max_turns:
        turn += 1
        
        # 1. Call model
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages  # ← Full history every turn
        )

        # 2. Append response
        messages.append({"role": "assistant", "content": response.content})

        # 3. Check if done
        if response.stop_reason == "end_turn":
            return {
                "type": "final",
                "text": next(
                    (b.text for b in response.content if hasattr(b, 'text')),
                    None
                ),
                "turns": turn
            }

        # 4. Execute tools
        tool_results = []
        for tool_use in [b for b in response.content if b.type == "tool_use"]:
            result = execute_tool(tool_use.name, tool_use.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result
            })

        # 5. Append results
        messages.append({"role": "user", "content": tool_results})
        
        yield {"type": "turn", "tool_count": len(tool_results)}
```

**Key differences**:
- JavaScript generator (`async function*`) → Python generator (`yield`)
- `const` declarations → not needed in Python
- `await` for async → Python generators don't need `async` (or use `async def` for async version)
- `===` → `==`
- `.find()` → `next(...)`
- Error handling returns vs yields

---

## 4. Context Monitoring

### JavaScript
```javascript
function estimateTokens(messages) {
  let tokens = 0;
  for (const msg of messages) {
    tokens += msg.content.length / 4;  // Rough estimate
  }
  return tokens;
}

function monitorContext(messages, warnThreshold = 80000) {
  const tokens = estimateTokens(messages);
  const percent = (tokens / 100000) * 100;
  
  if (percent > 92) {
    console.warn(`CRITICAL: ${tokens} tokens used`);
    return "critical";
  } else if (percent > warnThreshold) {
    console.warn(`WARNING: ${tokens} tokens used`);
    return "warning";
  }
  return "healthy";
}
```

### Python
```python
def estimate_tokens(messages):
    """Rough token estimation."""
    total_chars = 0
    for msg in messages:
        if isinstance(msg.get("content"), str):
            total_chars += len(msg["content"])
        elif isinstance(msg.get("content"), list):
            for block in msg["content"]:
                if isinstance(block, dict):
                    total_chars += len(str(block.get("content", "")))
    
    return total_chars // 4  # Rough estimate

def monitor_context(messages, warn_threshold=80000, critical_threshold=95000):
    """Monitor context usage."""
    tokens = estimate_tokens(messages)
    percent = (tokens / 100000) * 100
    
    if percent > 92:
        print(f"CRITICAL: {tokens:,} tokens used")
        return "critical"
    elif tokens > warn_threshold:
        print(f"WARNING: {tokens:,} tokens used")
        return "warning"
    return "healthy"
```

**Key differences**:
- `console.warn()` → `print()`
- String formatting: backticks → f-strings
- Type checking: implicit → explicit with `isinstance()`
- Array vs list iteration same pattern

---

## 5. Error Handling

### JavaScript
```javascript
const toolResults = [];

for (const toolUse of toolUses) {
  let result;
  try {
    result = await executeTool(toolUse.name, toolUse.input);
  } catch (error) {
    result = error.message;
  }

  toolResults.push({
    type: "tool_result",
    tool_use_id: toolUse.id,
    content: result,
    is_error: result.startsWith("Error:")
  });
}

messages.push({
  role: "user",
  content: toolResults
});
```

### Python
```python
tool_results = []

for tool_use in tool_uses:
    result = None
    try:
        result = execute_tool(tool_use.name, tool_use.input)
    except Exception as e:
        result = str(e)

    tool_results.append({
        "type": "tool_result",
        "tool_use_id": tool_use.id,
        "content": result,
        "is_error": result.startswith("Error:")
    })

messages.append({
    "role": "user",
    "content": tool_results
})
```

**Key differences**:
- `catch (error)` → `except Exception as e`
- `error.message` → `str(e)`
- Declaration pattern same (set, try, push/append)

---

## 6. Streaming Responses

### JavaScript
```javascript
const stream = await anthropic.messages.create({
  stream: true,
  model: "claude-opus-4-6",
  max_tokens: 1024,
  messages: messages
});

for await (const event of stream) {
  if (event.type === "content_block_delta") {
    process.stdout.write(event.delta.text);
  }
}

const finalMessage = await stream.finalMessage();
```

### Python
```python
from anthropic import Anthropic

client = Anthropic()

with client.messages.stream(
    model="claude-opus-4-6",
    max_tokens=1024,
    messages=messages
) as stream:
    for text in stream.text_stream:
        print(text, end="", flush=True)
    
    final_message = stream.get_final_message()
```

**Key differences**:
- `stream: true` → context manager with `stream()`
- `for await` → `for` with context manager
- Event handling → direct text stream
- Getting final message → `.get_final_message()` method

---

## 7. Tool Definition

### JavaScript
```javascript
const tools = [
  {
    name: "read_file",
    description: "Read a file's contents",
    input_schema: {
      type: "object",
      properties: {
        path: {
          type: "string",
          description: "Path to the file"
        }
      },
      required: ["path"]
    }
  }
];
```

### Python
```python
tools = [
    {
        "name": "read_file",
        "description": "Read a file's contents",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file"
                }
            },
            "required": ["path"]
        }
    }
]
```

**Key difference**: Identical! No language-specific syntax here (both use JSON structure).

---

## 8. Checking Stop Reasons

### JavaScript
```javascript
if (response.stop_reason === "end_turn") {
  console.log("Task complete!");
  break;
}

if (response.stop_reason === "tool_use") {
  // Execute tools
}

if (response.stop_reason === "max_tokens") {
  console.warn("Response truncated, hit token limit");
}
```

### Python
```python
if response.stop_reason == "end_turn":
    print("Task complete!")
    break

if response.stop_reason == "tool_use":
    # Execute tools
    pass

if response.stop_reason == "max_tokens":
    print("Response truncated, hit token limit")
```

**Key difference**: `===` → `==`

---

## 9. Filtering Content Blocks

### JavaScript
```javascript
// Get tool use blocks
const toolUses = response.content.filter(c => c.type === "tool_use");

// Get text blocks
const textBlocks = response.content.filter(c => c.type === "text");
const textContent = textBlocks[0]?.text;

// Find first match
const toolUse = response.content.find(c => c.type === "tool_use");
```

### Python
```python
# Get tool use blocks
tool_uses = [b for b in response.content if b.type == "tool_use"]

# Get text blocks
text_blocks = [b for b in response.content if hasattr(b, 'text')]
text_content = text_blocks[0].text if text_blocks else None

# Find first match
tool_use = next(
    (b for b in response.content if b.type == "tool_use"),
    None
)
```

**Key differences**:
- `.filter()` → list comprehension `[... for ... if ...]`
- Optional chaining `?.` → explicit `if` check
- `.find()` → `next(..., None)`

---

## 10. Async vs Sync Patterns

### JavaScript (Async)
```javascript
async function runAgent() {
  const response = await anthropic.messages.create({...});
  const result = await execute_tool(...);
  return result;
}

// Usage
const result = await runAgent();
```

### Python (Sync)
```python
def run_agent():
    response = client.messages.create({...})
    result = execute_tool(...)
    return result

# Usage
result = run_agent()
```

### Python (Async - if needed)
```python
import asyncio

async def run_agent():
    response = await client.messages.create({...})
    result = await execute_tool_async(...)
    return result

# Usage
result = asyncio.run(run_agent())
```

**Key insight**: Python default is sync, JavaScript default is async. Python requires explicit `async`/`await` if needed.

---

## Quick Reference Table

| Concept | JavaScript | Python |
|---------|-----------|--------|
| Array/List | `[]` | `[]` |
| Append | `.push()` | `.append()` |
| Loop array | `for (const x of arr)` | `for x in arr:` |
| Filter | `.filter(c => c.x)` | `[c for c in arr if c.x]` |
| Find first | `.find()` | `next((...), None)` |
| String equality | `===` | `==` |
| Comparison | `typeof` | `type()`, `isinstance()` |
| Try/catch | `try/catch` | `try/except` |
| Async | `async/await` | `async/await` (explicit) |
| Sleep | `setTimeout()` | `time.sleep()` |
| Print | `console.log()` | `print()` |
| Error object | `error.message` | `str(e)` |
| Dictionary access | `.prop` or `['key']` | `['key']` or `.get()` |

---

## Common Patterns Summary

### The Core Loop (Both Languages)

```
while True:
  1. Send messages + full history to Claude
  2. Append Claude's response to messages
  3. If response is text-only: DONE
  4. Extract tool calls from response
  5. Execute each tool
  6. Append results to messages
  7. Loop back to step 1
```

This pattern is **identical** in JavaScript and Python. The language differences are syntax only; the agentic logic is the same.

The key principle remains: **accumulate history, append results, send full context every turn**.
