# Python Agentic Loops: Complete Documentation Index

A comprehensive guide to understanding and implementing agentic loops in Claude Code using Python. All JavaScript examples from the original materials have been converted to Python.

---

## 📚 Documentation Files

### 1. **Python Quick Start Guide** (`python_quick_start_guide.md`)
**Start here if you're in a hurry**

5-minute overview covering:
- Core concept (the loop explained in 30 seconds)
- Bare minimum working example
- Message structure at each step
- Tool definition and execution templates
- Common patterns (sequential, parallel, error handling)
- Debugging checklist
- Real-world example (file debugger)

**Best for**: Quick reference, getting started, understanding the big picture

---

### 2. **Tool Results in Agentic Loops: Python Edition** (`tool_results_agentic_loops_python.md`)
**The comprehensive guide with full details**

Complete walkthrough including:
- **Ring 1**: Single tool call (simplest model)
  - Full code example with explanation
  - How tool_use_id linking works
  
- **Ring 2**: Full agentic loop
  - Complete working agent with system prompt
  - Tool definitions (read_file, write_file, bash)
  - The main loop logic explained step-by-step
  
- **Message lifecycle**: Detailed examples
  - How messages array evolves at each turn
  - What Claude sees on each invocation
  
- **Context management**: 
  - ContextTracker class
  - Context compaction strategies
  - Token estimation and monitoring
  
- **Multi-turn debugging session**: Real scenario
  - Complete example: Fix a failing login test
  - Shows all 5 turns with actual code
  - Demonstrates how Claude uses accumulated context
  
- **Design patterns**:
  - Always append, never rebuild
  - Make results explicit
  - Errors are information
  - Batch tool results properly
  
- **Production considerations**:
  - Prevent infinite loops (max_turns, max_budget)
  - Monitor context growth
  - Compress large results

**Best for**: Deep understanding, production implementation, learning by example

---

### 3. **Advanced Python Patterns** (`advanced_python_agentic_patterns.md`)
**Professional-grade patterns and techniques**

5 advanced patterns:

1. **Async Agent with Streaming**
   - AsyncAnthropic client
   - Real-time response streaming
   - Streaming combined with tool execution

2. **Session Management with Checkpointing**
   - AgentSession class
   - Persistent state to disk
   - Resume interrupted work
   - Session summaries

3. **Parallel Tool Execution**
   - Execute multiple tools concurrently
   - asyncio.gather for parallel runs
   - Efficient context usage

4. **Context Compression**
   - ContextCompressor class
   - Automatic summarization
   - Preserve latest turns
   - Long-running agent support

5. **Error Handling and Recovery**
   - AgentWithErrorRecovery class
   - Retry logic with exponential backoff
   - Graceful degradation
   - API error handling

**Best for**: Production systems, handling edge cases, scaling to long conversations

---

### 4. **JavaScript to Python Comparison** (`javascript_to_python_comparison.md`)
**Side-by-side code translation guide**

10 common patterns shown in both languages:

1. Basic message appending
2. Tool execution loop
3. Full agentic loop structure
4. Context monitoring
5. Error handling
6. Streaming responses
7. Tool definitions
8. Stop reason checking
9. Filtering content blocks
10. Async vs sync patterns

**Quick reference table**: Language differences at a glance

**Best for**: Converting JS implementations, learning both languages, understanding idioms

---

## 🎯 Quick Navigation by Use Case

### "I just want to get something working"
→ Start with: **Python Quick Start Guide**
→ Copy the bare minimum example
→ Replace tool execution functions with your own

### "I want to understand how this really works"
→ Read: **Tool Results in Agentic Loops** (Ring 1 and Ring 2)
→ Study: Message structure section
→ Walk through: Multi-turn debugging example

### "I'm building a production system"
→ Read: **Advanced Python Patterns**
→ Focus on: Session management + context compression
→ Use: Error handling and recovery patterns

### "I know JavaScript and want to learn Python"
→ Use: **JavaScript to Python Comparison**
→ Refer to: Quick reference table
→ Cross-reference with: Main guide

### "I need to debug something"
→ Check: Debugging checklist in Quick Start
→ Review: Error handling patterns in Advanced
→ Trace: Message structure with your actual messages

---

## 📋 Core Concepts Explained

### The Agentic Loop (in plain English)

```
While the task isn't complete:
  1. Send Claude your prompt + all previous conversation history
  2. Claude reads everything and decides: "Do I need tools or am I done?"
  3. If done: Return text response. Task complete, exit loop.
  4. If tools needed: Claude lists which tools to call and with what inputs
  5. Your code executes each tool
  6. Results get appended to the conversation as new "user" messages
  7. Go back to step 1 with the updated conversation
```

**Key insight**: Claude can see the results of what it requested on the previous turn. This feedback loop enables autonomous task completion.

### Message Roles

Only 2 roles exist, alternating:
- **user**: Initial prompt + tool results (sent by system)
- **assistant**: Claude's responses (text or tool calls)

Pattern: user → assistant → user → assistant → ... until assistant returns text-only

### Tool Result Linking

Each tool request gets an `id` from Claude. Each result references that `id` via `tool_use_id`. This is how Claude knows which result belongs to which request.

```python
# Request (from Claude)
{"type": "tool_use", "id": "call_123", "name": "read_file", ...}

# Result (sent back to Claude)
{"type": "tool_result", "tool_use_id": "call_123", "content": "..."}
```

### Context Accumulation

The context window is the total information Claude has access to. It includes:
- System prompt
- Tool definitions
- **Full conversation history** (every message, every response, every result)

It does NOT reset between turns. Everything accumulates. This is why:
- Early turns are cheap (prompts cached)
- Late turns are expensive (full history repriced)
- Large tool outputs cause context explosion
- Compression becomes necessary for long sessions

---

## 🔧 Implementation Checklist

### Before Writing Code

- [ ] Define what tools you need
- [ ] Plan the tool schema (inputs, descriptions)
- [ ] Decide on max_turns limit
- [ ] Consider context budget
- [ ] Plan error handling strategy

### Building the Loop

- [ ] Initialize messages list with user input
- [ ] Create tools array with definitions
- [ ] Implement execute_tool function
- [ ] Write the while loop
- [ ] Call client.messages.create with full messages array
- [ ] Append assistant response to messages
- [ ] Check stop_reason for "end_turn"
- [ ] Extract tool uses from response
- [ ] Execute each tool
- [ ] Create tool_result for each execution
- [ ] Append tool_results to messages (as user role)
- [ ] Loop back

### Production Hardening

- [ ] Add max_turns limit
- [ ] Monitor context usage
- [ ] Implement result compression
- [ ] Add error handling with retries
- [ ] Log all messages for debugging
- [ ] Set up checkpointing for resumable sessions
- [ ] Consider parallel tool execution
- [ ] Test with streaming

---

## 📊 Example Progression

The codebase provides examples in increasing complexity:

1. **Bare minimum** (Quick Start)
   - Single loop iteration
   - One tool
   - No error handling

2. **Simple loop** (Ring 1 in Main Guide)
   - Single tool execution
   - Message management
   - Result linking

3. **Full agent** (Ring 2 in Main Guide)
   - Multiple tools
   - System prompt
   - Error handling
   - Context tracking

4. **Production agent** (Advanced Patterns)
   - Checkpointing
   - Parallel execution
   - Context compression
   - Advanced error recovery

Start with #1 and #2. Move to #3 for your actual agent. Use #4 for production.

---

## 🐛 Common Issues and Solutions

### "Claude keeps calling the same tool"
- Check if tool returns clear results
- Verify tool_use_id linking is correct
- Consider whether Claude needs more context

### "Context grows too fast"
- Compress large tool outputs (see compress_result in guides)
- Implement context compaction (see advanced patterns)
- Reduce tool output verbosity
- Summarize old turns

### "Loop never terminates"
- Check that response has stop_reason == "end_turn"
- Add max_turns safeguard
- Examine if Claude is stuck in a pattern
- Revise system prompt to be clearer about success criteria

### "Tool results not visible next turn"
- Verify tool_use_id matches exactly
- Check that results are in a list under "content"
- Ensure tool_results appended as {"role": "user", "content": [...]"}
- Look at actual messages array to debug

### "API costs exploding"
- Use estimate_tokens() to monitor
- Compress results aggressively
- Check for infinite loops
- Implement max_budget_usd limit
- Use smaller model for subtasks (Haiku)

---

## 📖 Theory vs Practice

### Theory (How It Works)
- Conversation history is a list of messages
- Each message has role (user/assistant) and content
- Content can be text or tool blocks
- Tool blocks link via ID
- Full history sent on every request
- Context window accumulates

### Practice (How To Use It)
- Create an empty messages list
- Add user message
- Loop: call API, append response, execute tools, append results
- Stop when response has stop_reason == "end_turn"
- Monitor tokens, compress results, add safeguards

**In both languages, the logic is identical.** Only syntax differs (push → append, === → ==, etc.)

---

## 🚀 Next Steps

1. **Read**: Python Quick Start (5 min)
2. **Copy**: Bare minimum example
3. **Modify**: Tool execution functions for your use case
4. **Test**: Single tool, single turn
5. **Expand**: Multiple tools
6. **Monitor**: Add token estimation
7. **Harden**: Add error handling
8. **Optimize**: Use advanced patterns as needed

---

## 📞 Resources

| Need | Resource |
|------|----------|
| Official docs | https://docs.anthropic.com |
| API Reference | https://platform.claude.com/docs/api/overview |
| Anthropic SDK | https://github.com/anthropics/anthropic-sdk-python |
| Claude Code | https://code.claude.com |
| Agent SDK | https://docs.anthropic.com/en/docs/build-with-claude/agent-sdk/overview |

---

## Summary

All code in this documentation has been converted from JavaScript to Python. The agentic loop pattern is language-agnostic:

```python
while True:
    response = client.messages.create(messages=messages, tools=tools, ...)
    messages.append({"role": "assistant", "content": response.content})
    
    if response.stop_reason == "end_turn":
        break
    
    tool_results = [execute_tool(...) for tool in response.tools]
    messages.append({"role": "user", "content": tool_results})
```

Start simple, add complexity as needed, monitor context, and you've got a working autonomous agent.

Good luck! 🚀
