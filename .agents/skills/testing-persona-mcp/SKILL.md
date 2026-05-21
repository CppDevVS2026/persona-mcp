---
name: testing-persona-mcp
description: Test the Persona MCP Server end-to-end. Use when verifying tool handlers, memory persistence, persona prompts, mood tracking, or custom persona loading.
---

# Testing Persona MCP Server

## Overview
The persona-mcp server is a stdio-based MCP server with no UI. All testing is done via Python scripts that import the modules directly and call async handlers. No browser or desktop recording is needed.

## Prerequisites
- Python 3.10+
- The package installed in editable mode: `pip install -e .` from the repo root
- No external services or credentials required (uses local SQLite)

## Critical Test Paths

### 1. Tool Dispatch (11 tools)
Import `call_tool` from `persona_mcp.server` and call each tool with valid arguments:
- `list_personas` — should return 3 built-in personas (friend/Alex, teacher/Dr. Maya Chen, mentor/James Rivera)
- `get_persona_info` — default persona is Alex/friend
- `switch_persona` — switches active persona, returns new persona name
- `remember` / `recall` / `forget` — full CRUD cycle on memories
- `set_mood` — sets mood with optional reason
- `set_user_info` / `get_user_profile` — stores and retrieves user profile data
- `get_conversation_context` — returns system prompt with realism rules
- `clear_memories` — requires `confirm=True` to actually clear

### 2. Memory Persistence
Use isolated test databases (e.g., `/tmp/test_persist.db`) to avoid polluting real data. Create a `MemoryStore`, store memories, close it, reopen with a new `MemoryStore` pointing to the same path, and verify all data persists. Check ordering by importance DESC.

### 3. Persona Prompt Generation
Call `persona.to_system_prompt()` for each built-in persona and verify:
- All prompts contain "SCARILY REALISTIC" and 5 realism subsections
- Teacher prompt has "TEACHING APPROACH" + "Socratic"
- Mentor prompt has "MENTORING APPROACH"
- Friend prompt does NOT have teaching/mentoring sections
- `user_name` parameter substitutes correctly

### 4. Custom Persona Loading
Write a JSON file with custom persona fields, then call `switch_persona` with `custom_path` pointing to it. Verify the custom persona appears in `list_personas` and has correct attributes.

### 5. Mood Tracking
Set mood via `set_mood`, then check `get_conversation_context` — the output should contain `Current mood: <mood>`. Change mood and verify the context updates immediately.

### 6. MCP Prompts
Call `get_prompt` for each of the 4 prompts (chat_as_friend, learn_with_teacher, get_advice, custom_chat) and verify they return PromptMessages with the correct persona's system prompt.

## Testing Pattern
```python
import asyncio
from persona_mcp.server import call_tool, get_prompt
from persona_mcp import memory as mem_module
from persona_mcp import server as srv_module

# Use isolated test DB
test_store = mem_module.MemoryStore("/tmp/test_e2e.db")
srv_module._memory = test_store

async def test():
    r = await call_tool("list_personas", {})
    assert "Alex" in r[0].text

asyncio.run(test())
```

## Important Notes
- Always override `srv_module._memory` with a test MemoryStore to avoid polluting `~/.persona-mcp/memory.db`
- Clean up test databases after tests
- No CI is configured on this repo — all verification is local
- The server uses stdio transport, so you cannot test it via HTTP/curl

## Devin Secrets Needed
None — all testing is fully local with no external services.
