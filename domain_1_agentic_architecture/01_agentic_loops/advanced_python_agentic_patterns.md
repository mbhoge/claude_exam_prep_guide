# Advanced Python Patterns for Claude Code Agentic Loops

## Advanced Example 1: Async Agent with Streaming

```python
import anthropic
import asyncio
from typing import AsyncIterator

client = anthropic.AsyncAnthropic()

async def async_agent_with_streaming(
    user_input: str,
    max_turns: int = 10
) -> dict:
    """
    Run an agentic loop with async/await and streaming responses.
    Streaming allows us to see Claude's thinking in real-time.
    """
    
    messages = [{"role": "user", "content": user_input}]
    
    tools = [
        {
            "name": "search_web",
            "description": "Search the web for information",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"}
                },
                "required": ["query"]
            }
        }
    ]
    
    async def search_web(query: str) -> str:
        """Simulate a web search."""
        await asyncio.sleep(0.1)  # Simulate network latency
        return f"Search results for '{query}': ..."
    
    turn = 0
    
    while turn < max_turns:
        turn += 1
        print(f"\n{'='*60}")
        print(f"Turn {turn}: Streaming response from Claude")
        print(f"{'='*60}")
        
        # Collect streamed response
        full_response_text = ""
        response = None
        
        with client.messages.stream(
            model="claude-opus-4-6",
            max_tokens=1024,
            tools=tools,
            messages=messages
        ) as stream:
            async for text in stream.text_stream:
                print(text, end="", flush=True)
                full_response_text += text
            
            response = stream.get_final_message()
        
        print()  # Newline after streaming
        
        # Append assistant response
        messages.append({
            "role": "assistant",
            "content": response.content
        })
        
        # Check if done
        if response.stop_reason == "end_turn":
            print("\n✓ Task complete!")
            return {
                "status": "complete",
                "turns": turn,
                "final_text": full_response_text
            }
        
        # Execute tools
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        
        if not tool_uses:
            break
        
        tool_results = []
        
        for tool_use in tool_uses:
            print(f"\nExecuting: {tool_use.name}")
            
            if tool_use.name == "search_web":
                result = await search_web(tool_use.input["query"])
            else:
                result = f"Unknown tool: {tool_use.name}"
            
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result
            })
        
        messages.append({
            "role": "user",
            "content": tool_results
        })
    
    return {
        "status": "max_turns_exceeded",
        "turns": turn
    }

# Usage
if __name__ == "__main__":
    result = asyncio.run(async_agent_with_streaming("What's the latest news in AI?"))
    print(f"\nFinal: {result}")
```

---

## Advanced Example 2: Agent with State Management and Checkpointing

```python
import anthropic
import json
from pathlib import Path
from datetime import datetime
from typing import Optional

class AgentSession:
    """
    Manage an agentic session with persistent state and checkpointing.
    Allows pausing, resuming, and analyzing agent behavior.
    """
    
    def __init__(self, session_id: str, checkpoint_dir: str = ".checkpoints"):
        self.session_id = session_id
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True)
        
        self.messages = []
        self.turns = 0
        self.created_at = datetime.now()
        self.last_updated = datetime.now()
        
        self._load_if_exists()
    
    def _load_if_exists(self):
        """Load session from disk if it exists."""
        checkpoint_file = self.checkpoint_dir / f"{self.session_id}.json"
        if checkpoint_file.exists():
            print(f"Loading session from {checkpoint_file}")
            data = json.loads(checkpoint_file.read_text())
            self.messages = data["messages"]
            self.turns = data["turns"]
            self.created_at = datetime.fromisoformat(data["created_at"])
            self.last_updated = datetime.fromisoformat(data["last_updated"])
    
    def save_checkpoint(self):
        """Save session state to disk."""
        checkpoint_file = self.checkpoint_dir / f"{self.session_id}.json"
        self.last_updated = datetime.now()
        
        data = {
            "session_id": self.session_id,
            "messages": self.messages,
            "turns": self.turns,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }
        
        checkpoint_file.write_text(json.dumps(data, indent=2))
        print(f"Saved checkpoint to {checkpoint_file}")
    
    def add_user_message(self, content: str):
        """Add a user message."""
        self.messages.append({"role": "user", "content": content})
        self.save_checkpoint()
    
    def add_assistant_message(self, content):
        """Add an assistant message."""
        self.messages.append({"role": "assistant", "content": content})
        self.turns += 1
        self.save_checkpoint()
    
    def add_tool_results(self, results: list):
        """Add tool results."""
        self.messages.append({"role": "user", "content": results})
        self.save_checkpoint()
    
    def get_summary(self) -> dict:
        """Get session summary."""
        return {
            "session_id": self.session_id,
            "turns": self.turns,
            "messages": len(self.messages),
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "age_seconds": (datetime.now() - self.created_at).total_seconds()
        }

def run_session_with_checkpointing(
    session_id: str,
    user_input: Optional[str] = None,
    max_turns: int = 10
):
    """Run or resume an agent session with checkpointing."""
    
    client = anthropic.Anthropic()
    session = AgentSession(session_id)
    
    # If resuming, add context about what's been done
    if session.turns > 0:
        print(f"Resuming session with {session.turns} prior turns")
    elif user_input:
        session.add_user_message(user_input)
    else:
        print("No session history and no new input provided")
        return
    
    tools = [
        {
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    ]
    
    def execute_tool(name: str, input_data: dict) -> str:
        if name == "read_file":
            try:
                return Path(input_data["path"]).read_text()
            except Exception as e:
                return f"Error: {e}"
    
    while session.turns < max_turns:
        print(f"\nTurn {session.turns + 1}")
        
        # Call Claude
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            tools=tools,
            messages=session.messages
        )
        
        # Append response
        session.add_assistant_message(response.content)
        
        # Check if done
        if response.stop_reason == "end_turn":
            text_block = next(
                (b for b in response.content if hasattr(b, 'text')),
                None
            )
            if text_block:
                print(f"Complete: {text_block.text[:100]}...")
            break
        
        # Execute tools
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            break
        
        tool_results = []
        for tool_use in tool_uses:
            result = execute_tool(tool_use.name, tool_use.input)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result[:500]  # Limit size
            })
        
        session.add_tool_results(tool_results)
    
    print(f"\nSession summary:")
    print(json.dumps(session.get_summary(), indent=2))

# Usage
if __name__ == "__main__":
    # First run
    run_session_with_checkpointing("debug_session_1", "Debug the test failure")
    
    # Later, resume the same session
    run_session_with_checkpointing("debug_session_1")
```

---

## Advanced Example 3: Parallel Tool Execution

```python
import anthropic
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import List

async def parallel_tool_execution():
    """
    Execute multiple tools in parallel when Claude requests them.
    This is more efficient than executing tools sequentially.
    """
    
    client = anthropic.Anthropic()
    
    tools = [
        {
            "name": "fetch_url",
            "description": "Fetch content from a URL",
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"]
            }
        },
        {
            "name": "query_database",
            "description": "Query a database",
            "input_schema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    ]
    
    async def fetch_url(url: str) -> str:
        """Simulate URL fetch."""
        await asyncio.sleep(0.5)
        return f"Content from {url}"
    
    async def query_database(query: str) -> str:
        """Simulate database query."""
        await asyncio.sleep(0.3)
        return f"Database results for: {query}"
    
    messages = [
        {
            "role": "user",
            "content": "Get the latest documentation from docs.example.com and also query the performance metrics"
        }
    ]
    
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        tools=tools,
        messages=messages
    )
    
    messages.append({"role": "assistant", "content": response.content})
    
    # Extract tool uses
    tool_uses = [b for b in response.content if b.type == "tool_use"]
    
    if not tool_uses:
        print("No tools requested")
        return
    
    # Execute tools in parallel
    print(f"Executing {len(tool_uses)} tools in parallel...")
    
    async def execute_tool_async(tool_use):
        if tool_use.name == "fetch_url":
            result = await fetch_url(tool_use.input["url"])
        elif tool_use.name == "query_database":
            result = await query_database(tool_use.input["query"])
        else:
            result = f"Unknown tool: {tool_use.name}"
        
        return {
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": result
        }
    
    # Run all tools concurrently
    tool_results = await asyncio.gather(
        *[execute_tool_async(tool_use) for tool_use in tool_uses]
    )
    
    # Append results as single user turn
    messages.append({
        "role": "user",
        "content": tool_results
    })
    
    # Get final response
    final_response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        tools=tools,
        messages=messages
    )
    
    text_block = next(
        (b for b in final_response.content if hasattr(b, 'text')),
        None
    )
    
    if text_block:
        print(f"\nFinal response:\n{text_block.text}")

# Usage
if __name__ == "__main__":
    asyncio.run(parallel_tool_execution())
```

---

## Advanced Example 4: Context Compression and Summarization

```python
import anthropic
import json
from typing import List, Dict

class ContextCompressor:
    """
    Manage context compression to prevent token explosion.
    When approaching the limit, summarize early turns.
    """
    
    def __init__(
        self,
        max_context_tokens: int = 100_000,
        compress_threshold: float = 0.92,
        preserve_last_n_turns: int = 3
    ):
        self.max_context_tokens = max_context_tokens
        self.compress_threshold = compress_threshold
        self.preserve_last_n_turns = preserve_last_n_turns
        self.messages: List[Dict] = []
        self.compression_history: List[str] = []
    
    def estimate_tokens(self) -> int:
        """Rough token estimation."""
        total_chars = 0
        for msg in self.messages:
            if isinstance(msg.get("content"), str):
                total_chars += len(msg["content"])
            elif isinstance(msg.get("content"), list):
                for block in msg["content"]:
                    if isinstance(block, dict):
                        total_chars += len(json.dumps(block))
        
        return total_chars // 4
    
    def should_compress(self) -> bool:
        """Check if compression threshold reached."""
        tokens = self.estimate_tokens()
        percent = tokens / self.max_context_tokens
        return percent >= self.compress_threshold
    
    def compress_early_turns(self, client: anthropic.Anthropic) -> bool:
        """
        Summarize early turns to save context.
        Returns True if compression was performed.
        """
        if not self.should_compress():
            return False
        
        # Keep last N turns untouched
        preserve_count = self.preserve_last_n_turns * 2  # user + assistant pairs
        
        if len(self.messages) <= preserve_count:
            print("Not enough messages to compress")
            return False
        
        to_compress = self.messages[:-preserve_count]
        to_preserve = self.messages[-preserve_count:]
        
        # Create summary prompt
        summary_prompt = "Summarize the key points from this conversation:\n\n"
        for msg in to_compress:
            if isinstance(msg.get("content"), str):
                summary_prompt += f"{msg['role']}: {msg['content'][:200]}\n"
        
        # Get summary from Claude
        summary_response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[
                {"role": "user", "content": summary_prompt}
            ]
        )
        
        summary_text = summary_response.content[0].text
        
        # Replace early turns with summary
        self.messages = [
            {
                "role": "user",
                "content": f"[SUMMARY OF PRIOR CONVERSATION]\n{summary_text}"
            }
        ] + to_preserve
        
        self.compression_history.append(summary_text[:200])
        
        print(f"✓ Compressed {len(to_compress)} messages into 1 summary message")
        return True
    
    def add_message(self, role: str, content):
        """Add a message and auto-compress if needed."""
        self.messages.append({"role": role, "content": content})
        
        if self.should_compress():
            print(f"⚠️  Context at {self.estimate_tokens():,} tokens - compressing...")
            # Could pass client here for automatic compression
    
    def get_stats(self) -> dict:
        """Get compression statistics."""
        return {
            "total_messages": len(self.messages),
            "estimated_tokens": self.estimate_tokens(),
            "percent_used": (self.estimate_tokens() / self.max_context_tokens) * 100,
            "compressions_performed": len(self.compression_history)
        }

def agent_with_auto_compression():
    """Run agent with automatic context compression."""
    
    client = anthropic.Anthropic()
    compressor = ContextCompressor(compress_threshold=0.85)
    
    tools = [
        {
            "name": "read_file",
            "description": "Read a file",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"]
            }
        }
    ]
    
    # Initial message
    compressor.add_message(
        "user",
        "Analyze all Python files in the project and identify code smell"
    )
    
    for turn in range(10):
        print(f"\nTurn {turn + 1}")
        print(f"Context: {compressor.get_stats()}")
        
        # Call Claude
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            tools=tools,
            messages=compressor.messages
        )
        
        compressor.add_message("assistant", response.content)
        
        if response.stop_reason == "end_turn":
            print("Task complete!")
            break
        
        # Execute tools
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        
        if not tool_uses:
            break
        
        tool_results = []
        for tool_use in tool_uses:
            result = f"File content (simulated)"  # Simulate file read
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result[:1000]  # Limit result size
            })
        
        compressor.add_message("user", tool_results)

# Usage
if __name__ == "__main__":
    agent_with_auto_compression()
```

---

## Advanced Example 5: Error Handling and Recovery

```python
import anthropic
from typing import Optional
import time

class AgentWithErrorRecovery:
    """Agent that gracefully handles errors and recovers."""
    
    def __init__(self, max_retries: int = 3):
        self.client = anthropic.Anthropic()
        self.max_retries = max_retries
        self.error_history = []
    
    def execute_tool_with_retry(
        self,
        tool_name: str,
        tool_input: dict,
        max_retries: int = 3
    ) -> tuple[str, bool]:
        """
        Execute a tool with retry logic.
        Returns (result, is_error).
        """
        
        for attempt in range(max_retries):
            try:
                if tool_name == "call_api":
                    # Simulate potential API failure
                    if attempt < 2:  # Fail first 2 attempts
                        raise ConnectionError("API temporarily unavailable")
                    return ("API response data", False)
                
                elif tool_name == "read_file":
                    # Simulate file read with potential failure
                    return ("File contents", False)
                
                else:
                    return (f"Unknown tool: {tool_name}", True)
            
            except (ConnectionError, TimeoutError) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    error_msg = f"Failed after {max_retries} attempts: {e}"
                    self.error_history.append(error_msg)
                    return (error_msg, True)
            
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                self.error_history.append(error_msg)
                return (error_msg, True)
        
        return ("Unknown error", True)
    
    def run_with_error_recovery(
        self,
        user_input: str,
        max_turns: int = 10
    ) -> dict:
        """Run agent with comprehensive error handling."""
        
        messages = [{"role": "user", "content": user_input}]
        
        tools = [
            {
                "name": "call_api",
                "description": "Call an external API",
                "input_schema": {
                    "type": "object",
                    "properties": {"endpoint": {"type": "string"}},
                    "required": ["endpoint"]
                }
            },
            {
                "name": "read_file",
                "description": "Read a file",
                "input_schema": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"]
                }
            }
        ]
        
        turn = 0
        
        while turn < max_turns:
            turn += 1
            
            try:
                # Call Claude
                response = self.client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=1024,
                    tools=tools,
                    messages=messages
                )
            
            except anthropic.APIError as e:
                # Handle API errors gracefully
                print(f"API error on turn {turn}: {e}")
                
                # Add error context to conversation
                messages.append({
                    "role": "user",
                    "content": f"Error occurred: {e}. Please adjust your approach."
                })
                
                self.error_history.append(f"Turn {turn}: {e}")
                continue
            
            messages.append({"role": "assistant", "content": response.content})
            
            if response.stop_reason == "end_turn":
                return {
                    "status": "complete",
                    "turns": turn,
                    "errors": self.error_history
                }
            
            # Extract and execute tools
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            
            if not tool_uses:
                break
            
            tool_results = []
            
            for tool_use in tool_uses:
                print(f"Executing {tool_use.name} with retry logic...")
                
                result, is_error = self.execute_tool_with_retry(
                    tool_use.name,
                    tool_use.input,
                    max_retries=3
                )
                
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result,
                    "is_error": is_error
                })
            
            messages.append({"role": "user", "content": tool_results})
        
        return {
            "status": "max_turns_exceeded",
            "turns": turn,
            "errors": self.error_history
        }

# Usage
if __name__ == "__main__":
    agent = AgentWithErrorRecovery()
    result = agent.run_with_error_recovery(
        "Fetch data from the API and analyze it"
    )
    print(f"\nResult: {result}")
```

---

## Summary of Advanced Patterns

| Pattern | Use Case | Key Benefit |
|---------|----------|-------------|
| **Async/Streaming** | Real-time feedback needed | See Claude's response as it streams |
| **Checkpointing** | Long-running sessions | Resume interrupted work without losing context |
| **Parallel Execution** | Multiple independent tools | Faster tool execution |
| **Context Compression** | Long conversations | Stay within token limits |
| **Error Recovery** | Unreliable operations | Gracefully handle and retry failed tools |

All patterns follow the core principle: **keep a flat message history, append results, send full context on every turn**.
