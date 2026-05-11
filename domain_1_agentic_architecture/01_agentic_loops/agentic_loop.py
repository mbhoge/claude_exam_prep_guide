"""
Task 1.1 – Agentic Loops for Autonomous Task Execution
=======================================================
Complete Python implementation covering:
  - Basic agentic loop (stop_reason control flow)
  - Tool result appending pattern
  - Multi-tool execution in one turn
  - Error handling and retry
  - Anti-pattern examples
"""

import anthropic
import subprocess
from pathlib import Path

client = anthropic.Anthropic()

# ─────────────────────────────────────────────────────────
# SECTION 1: Bare-minimum agentic loop
# ─────────────────────────────────────────────────────────

def simple_agentic_loop(user_input: str, tools: list, max_turns: int = 10) -> str:
    """
    Correct agentic loop implementation.

    Key behaviours:
      - Continues when stop_reason is "tool_use"
      - Terminates when stop_reason is "end_turn"
      - Appends every tool_result before the next model call
    """
    messages = [{"role": "user", "content": user_input}]
    turn = 0

    while turn < max_turns:
        turn += 1

        # ── 1. Call the model with full accumulated history ──
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            tools=tools,
            messages=messages,
        )

        # ── 2. Append assistant response to history ──
        messages.append({"role": "assistant", "content": response.content})

        # ── 3. Inspect stop_reason ──
        if response.stop_reason == "end_turn":
            # Task complete – extract and return text
            text = next(
                (block.text for block in response.content if hasattr(block, "text")),
                "",
            )
            return text

        # ── 4. stop_reason == "tool_use" – execute each tool ──
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            result = _execute_tool(block.name, block.input)

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,   # links result to request
                    "content": result,
                    "is_error": result.startswith("Error:"),
                }
            )

        # ── 5. Append ALL tool results in ONE user turn ──
        messages.append({"role": "user", "content": tool_results})

    return "Max turns reached without completion."


def _execute_tool(name: str, inputs: dict) -> str:
    """Dispatch to the correct tool handler."""
    handlers = {
        "read_file":  _tool_read_file,
        "write_file": _tool_write_file,
        "bash":       _tool_bash,
    }
    handler = handlers.get(name)
    if not handler:
        return f"Error: Unknown tool '{name}'"
    try:
        return handler(inputs)
    except Exception as exc:
        return f"Error: {exc}"


def _tool_read_file(inputs: dict) -> str:
    return Path(inputs["path"]).read_text()


def _tool_write_file(inputs: dict) -> str:
    Path(inputs["path"]).write_text(inputs["content"])
    return "Written successfully."


def _tool_bash(inputs: dict) -> str:
    result = subprocess.run(
        inputs["command"], shell=True, capture_output=True, text=True, timeout=30
    )
    return result.stdout + result.stderr


# ─────────────────────────────────────────────────────────
# SECTION 2: How tool results appear in the message array
# ─────────────────────────────────────────────────────────

def demonstrate_message_evolution():
    """
    Shows exactly how the messages list grows across turns.
    Read this to understand the data structure the exam tests.
    """

    # After initial user message
    messages_turn_0 = [
        {"role": "user", "content": "Read config.json and summarise it"}
    ]

    # After Claude responds (calls a tool)
    messages_turn_1 = messages_turn_0 + [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "call_abc123",          # ← unique ID
                    "name": "read_file",
                    "input": {"path": "config.json"},
                }
            ],
        }
    ]

    # After tool execution – result appended as USER turn
    messages_turn_1_result = messages_turn_1 + [
        {
            "role": "user",          # ← system sends this as "user"
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "call_abc123",   # ← matches the request
                    "content": '{"host": "localhost", "port": 5432}',
                }
            ],
        }
    ]

    # On turn 2, Claude sees ALL of the above and decides what to do next.
    # If it calls another tool, we repeat the append cycle.
    # If stop_reason is "end_turn", we exit.

    return messages_turn_1_result


# ─────────────────────────────────────────────────────────
# SECTION 3: Multiple tool calls in a single response
# ─────────────────────────────────────────────────────────

def handle_parallel_tool_calls(response_content: list) -> list:
    """
    Claude may call multiple tools in one response.
    Each must get its own tool_result with matching tool_use_id.
    All results go in ONE user-role message.
    """
    tool_results = []

    for block in response_content:
        if block.type != "tool_use":
            continue

        result = _execute_tool(block.name, block.input)

        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": block.id,   # each result linked to its request
                "content": result,
            }
        )

    # ✅ All results in ONE user turn (not separate turns)
    return [{"role": "user", "content": tool_results}]


# ─────────────────────────────────────────────────────────
# SECTION 4: Anti-pattern examples (what NOT to do)
# ─────────────────────────────────────────────────────────

def antipattern_natural_language_termination(response):
    """❌ WRONG: parsing assistant text to detect completion."""
    text = next(
        (b.text for b in response.content if hasattr(b, "text")), ""
    )
    if "I have completed" in text or "finished" in text.lower():
        return True   # brittle – model phrasing varies
    return False


def antipattern_fixed_iteration_cap():
    """❌ WRONG: using a hard cap as the ONLY stopping mechanism."""
    messages = [{"role": "user", "content": "..."}]
    for _ in range(5):           # arbitrary cap – may cut valid tasks short
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=messages,
        )
        # No stop_reason check – always continues until cap
        messages.append({"role": "assistant", "content": response.content})
    return "Done (but maybe not really)"


def antipattern_skip_tool_results():
    """❌ WRONG: calling the model again without appending tool results."""
    messages = [{"role": "user", "content": "Analyse this file"}]
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=messages,
    )
    # Execute tools but DON'T append results
    # Next call: Claude has no idea what the tools returned
    response2 = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=messages,   # stale – still only the user message
    )
    return response2


# ─────────────────────────────────────────────────────────
# SECTION 5: Production-grade loop with monitoring
# ─────────────────────────────────────────────────────────

def production_agentic_loop(
    user_input: str,
    tools: list,
    system_prompt: str = "",
    max_turns: int = 20,
    max_cost_usd: float = 5.0,
) -> dict:
    """
    Production loop with:
      - Correct stop_reason handling
      - Cost tracking
      - Structured result
      - Safety limits
    """
    messages = [{"role": "user", "content": user_input}]
    total_input_tokens = 0
    total_output_tokens = 0
    COST_PER_M_INPUT = 3.0    # adjust to current pricing
    COST_PER_M_OUTPUT = 15.0

    for turn in range(1, max_turns + 1):
        create_kwargs = dict(
            model="claude-opus-4-6",
            max_tokens=4096,
            tools=tools,
            messages=messages,
        )
        if system_prompt:
            create_kwargs["system"] = system_prompt

        response = client.messages.create(**create_kwargs)

        # Track usage
        total_input_tokens  += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens
        cost = (
            total_input_tokens  / 1_000_000 * COST_PER_M_INPUT
            + total_output_tokens / 1_000_000 * COST_PER_M_OUTPUT
        )

        # Append response
        messages.append({"role": "assistant", "content": response.content})

        # ── PRIMARY termination: stop_reason ──
        if response.stop_reason == "end_turn":
            text = next(
                (b.text for b in response.content if hasattr(b, "text")), ""
            )
            return {
                "status": "complete",
                "result": text,
                "turns": turn,
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "cost_usd": round(cost, 4),
            }

        # Budget guard (secondary safety, not primary stopping)
        if cost > max_cost_usd:
            return {
                "status": "budget_exceeded",
                "turns": turn,
                "cost_usd": round(cost, 4),
            }

        # Execute tools and append results
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            result = _execute_tool(block.name, block.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                    "is_error": result.startswith("Error:"),
                }
            )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

    return {"status": "max_turns_exceeded", "turns": max_turns}


# ─────────────────────────────────────────────────────────
# Tool definitions (used by example calls)
# ─────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "read_file",
        "description": "Read the full text content of a file on disk.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file."
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write text content to a file, overwriting if it exists.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path":    {"type": "string", "description": "File path."},
                "content": {"type": "string", "description": "Content to write."},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "bash",
        "description": "Execute a shell command and return combined stdout + stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Shell command to run."
                }
            },
            "required": ["command"],
        },
    },
]


# ─────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = production_agentic_loop(
        user_input="List all Python files in the current directory and count the lines in each.",
        tools=TOOLS,
        max_turns=10,
    )
    print(result)
