"""Persona MCP Server — a realistic AI companion with memory and personality.

Run with:
    persona-mcp                     (after pip install)
    python -m persona_mcp.server    (from source)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    Resource,
    TextContent,
    Tool,
)
from pydantic import AnyUrl

from persona_mcp.memory import MemoryStore
from persona_mcp.personas import BUILTIN_PERSONAS, Persona, load_custom_persona

logger = logging.getLogger("persona-mcp")

# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_memory = MemoryStore()
_active_persona: Persona = BUILTIN_PERSONAS["friend"]
_custom_personas: dict[str, Persona] = {}


def _all_personas() -> dict[str, Persona]:
    return {**BUILTIN_PERSONAS, **_custom_personas}


def _get_persona(name: str | None = None) -> Persona:
    if name is None:
        return _active_persona
    all_p = _all_personas()
    key = name.lower()
    if key in all_p:
        return all_p[key]
    for p in all_p.values():
        if p.name.lower() == key:
            return p
    raise ValueError(
        f"Unknown persona '{name}'. Available: {', '.join(all_p.keys())}"
    )


# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

app = Server("persona-mcp")


# ---- Tools ----------------------------------------------------------------


TOOLS: list[dict[str, Any]] = [
    {
        "name": "switch_persona",
        "description": (
            "Switch the active persona. Available built-in personas: friend (Alex), "
            "teacher (Dr. Maya Chen), mentor (James Rivera). You can also load a "
            "custom persona from a JSON file."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "persona": {
                    "type": "string",
                    "description": (
                        "Name or role of the persona to switch to "
                        "(e.g., 'friend', 'teacher', 'mentor')"
                    ),
                },
                "custom_path": {
                    "type": "string",
                    "description": "Optional path to a custom persona JSON file",
                },
            },
            "required": ["persona"],
        },
    },
    {
        "name": "remember",
        "description": (
            "Store a memory about the user — facts, preferences, events, or emotional "
            "context. The persona will recall these in future conversations to feel realistic."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": (
                        "What to remember (e.g., 'User's name is Sam', "
                        "'They love hiking')"
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": ["fact", "preference", "event", "emotion", "conversation"],
                    "description": "Type of memory",
                    "default": "fact",
                },
                "importance": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 5,
                    "description": "How important is this memory? (1=trivial, 5=critical)",
                    "default": 3,
                },
            },
            "required": ["content"],
        },
    },
    {
        "name": "recall",
        "description": (
            "Retrieve memories about the user. Use this to ground responses in "
            "past context and make the persona feel like a real person who remembers."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["fact", "preference", "event", "emotion", "conversation"],
                    "description": "Filter by memory category (optional)",
                },
                "query": {
                    "type": "string",
                    "description": "Search keyword to find specific memories (optional)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max number of memories to return",
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "forget",
        "description": "Remove a specific memory by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "memory_id": {
                    "type": "integer",
                    "description": "ID of the memory to forget",
                },
            },
            "required": ["memory_id"],
        },
    },
    {
        "name": "set_mood",
        "description": (
            "Set the persona's current mood. This affects their tone, energy, and "
            "how they respond. Moods drift naturally over conversation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "mood": {
                    "type": "string",
                    "description": (
                        "The mood to set (e.g., 'happy', 'tired', 'excited', 'thoughtful', "
                        "'grumpy', 'nostalgic', 'energetic', 'worried')"
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": "Why the mood changed (optional, for context)",
                },
            },
            "required": ["mood"],
        },
    },
    {
        "name": "set_user_info",
        "description": (
            "Store information about the user (name, age, interests, etc.). "
            "The persona uses this to personalize conversations."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Profile field (e.g., 'name', 'age', 'occupation', 'interests')",
                },
                "value": {
                    "type": "string",
                    "description": "Value for the field",
                },
            },
            "required": ["key", "value"],
        },
    },
    {
        "name": "get_user_profile",
        "description": "Retrieve everything the persona knows about the user.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_persona_info",
        "description": "Get details about the currently active persona or a specific persona.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "persona": {
                    "type": "string",
                    "description": "Persona name/role to inspect (optional, defaults to active)",
                },
            },
        },
    },
    {
        "name": "list_personas",
        "description": "List all available personas (built-in and custom).",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "clear_memories",
        "description": "Clear all memories for a persona. Use with caution — this is irreversible.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "persona": {
                    "type": "string",
                    "description": "Persona to clear memories for (defaults to active)",
                },
                "confirm": {
                    "type": "boolean",
                    "description": "Must be true to confirm deletion",
                },
            },
            "required": ["confirm"],
        },
    },
    {
        "name": "get_conversation_context",
        "description": (
            "Get the full context package for the active persona: system prompt, "
            "memories, mood, and user profile. Use this at the start of a conversation "
            "to prime the AI with everything it needs to stay in character."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [Tool(**t) for t in TOOLS]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    global _active_persona

    if name == "switch_persona":
        persona_key = arguments["persona"].lower()
        custom_path = arguments.get("custom_path")

        if custom_path:
            persona = load_custom_persona(custom_path)
            _custom_personas[persona_key] = persona
            _active_persona = persona
            return [TextContent(
                type="text",
                text=f"Loaded and switched to custom persona: {persona.name} ({persona.role})",
            )]

        _active_persona = _get_persona(persona_key)
        return [TextContent(
            type="text",
            text=(
                f"Switched to {_active_persona.name} ({_active_persona.role}). "
                f"Personality: {', '.join(_active_persona.personality_traits[:3])}. "
                f"Use get_conversation_context to get the full character prompt."
            ),
        )]

    if name == "remember":
        entry = _memory.remember(
            persona_name=_active_persona.name,
            content=arguments["content"],
            category=arguments.get("category", "fact"),
            importance=arguments.get("importance", 3),
        )
        return [TextContent(
            type="text",
            text=f"Remembered (id={entry.id}): [{entry.category}] {entry.content}",
        )]

    if name == "recall":
        memories = _memory.recall(
            persona_name=_active_persona.name,
            category=arguments.get("category"),
            query=arguments.get("query"),
            limit=arguments.get("limit", 20),
        )
        if not memories:
            return [TextContent(type="text", text="No memories found.")]

        lines = [f"Memories for {_active_persona.name} ({len(memories)} found):"]
        for m in memories:
            lines.append(
                f"  [{m.id}] ({m.category}, importance={m.importance}) "
                f"{m.content} — {m.age_description}"
            )
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "forget":
        success = _memory.forget(arguments["memory_id"])
        msg = "Memory forgotten." if success else "Memory not found."
        return [TextContent(type="text", text=msg)]

    if name == "set_mood":
        mood = arguments["mood"]
        reason = arguments.get("reason")
        _memory.log_mood(_active_persona.name, mood, reason)
        msg = f"{_active_persona.name}'s mood is now: {mood}"
        if reason:
            msg += f" (because: {reason})"
        return [TextContent(type="text", text=msg)]

    if name == "set_user_info":
        _memory.set_user_profile(arguments["key"], arguments["value"])
        return [TextContent(
            type="text",
            text=f"Updated user profile: {arguments['key']} = {arguments['value']}",
        )]

    if name == "get_user_profile":
        profile = _memory.get_user_profile()
        if not profile:
            return [TextContent(type="text", text="No user profile data yet.")]
        lines = ["User Profile:"]
        for k, v in profile.items():
            lines.append(f"  {k}: {v}")
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "get_persona_info":
        persona = _get_persona(arguments.get("persona"))
        info = persona.to_dict()
        return [TextContent(
            type="text",
            text=json.dumps(info, indent=2),
        )]

    if name == "list_personas":
        all_p = _all_personas()
        lines = ["Available Personas:"]
        for key, p in all_p.items():
            active = " (ACTIVE)" if p.name == _active_persona.name else ""
            lines.append(f"  {key}: {p.name} — {p.role}, age {p.age}{active}")
            lines.append(f"    {p.background[:80]}...")
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "clear_memories":
        if not arguments.get("confirm"):
            return [TextContent(
                type="text",
                text="Set confirm=true to clear all memories. This cannot be undone.",
            )]
        persona = _get_persona(arguments.get("persona"))
        count = _memory.clear_all(persona.name)
        return [TextContent(
            type="text",
            text=f"Cleared {count} memories for {persona.name}.",
        )]

    if name == "get_conversation_context":
        mood = _memory.get_current_mood(_active_persona.name)
        user_profile = _memory.get_user_profile()
        user_name = user_profile.get("name", "friend")
        memory_summary = _memory.get_memory_summary(_active_persona.name)

        context = _active_persona.to_system_prompt(mood=mood, user_name=user_name)
        context += f"\n{memory_summary}\n"

        if user_profile:
            context += "\nUSER PROFILE:\n"
            for k, v in user_profile.items():
                context += f"  {k}: {v}\n"

        return [TextContent(type="text", text=context)]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ---- Prompts --------------------------------------------------------------


@app.list_prompts()
async def list_prompts() -> list[Prompt]:
    return [
        Prompt(
            name="chat_as_friend",
            description="Start a conversation with Alex, your casual friend",
            arguments=[
                PromptArgument(
                    name="message",
                    description="Your opening message to Alex",
                    required=True,
                ),
            ],
        ),
        Prompt(
            name="learn_with_teacher",
            description="Start a learning session with Dr. Maya Chen",
            arguments=[
                PromptArgument(
                    name="topic",
                    description="What you want to learn about",
                    required=True,
                ),
            ],
        ),
        Prompt(
            name="get_advice",
            description="Get life or career advice from James Rivera, your mentor",
            arguments=[
                PromptArgument(
                    name="situation",
                    description="Describe your situation or question",
                    required=True,
                ),
            ],
        ),
        Prompt(
            name="custom_chat",
            description="Start a conversation with any available persona",
            arguments=[
                PromptArgument(
                    name="persona",
                    description="Persona name or role (friend/teacher/mentor)",
                    required=True,
                ),
                PromptArgument(
                    name="message",
                    description="Your opening message",
                    required=True,
                ),
            ],
        ),
    ]


@app.get_prompt()
async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
    global _active_persona
    arguments = arguments or {}

    if name == "chat_as_friend":
        _active_persona = BUILTIN_PERSONAS["friend"]
        mood = _memory.get_current_mood(_active_persona.name)
        user_profile = _memory.get_user_profile()
        user_name = user_profile.get("name", "friend")
        system = _active_persona.to_system_prompt(mood=mood, user_name=user_name)
        system += f"\n{_memory.get_memory_summary(_active_persona.name)}"

        return GetPromptResult(
            description="Chat with Alex, your friend",
            messages=[
                PromptMessage(role="user", content=TextContent(
                    type="text",
                    text=f"[System: You are now {_active_persona.name}. Stay in character.]\n\n"
                         f"{system}\n\n---\n\n{arguments.get('message', 'Hey!')}",
                )),
            ],
        )

    if name == "learn_with_teacher":
        _active_persona = BUILTIN_PERSONAS["teacher"]
        mood = _memory.get_current_mood(_active_persona.name)
        user_profile = _memory.get_user_profile()
        user_name = user_profile.get("name", "student")
        system = _active_persona.to_system_prompt(mood=mood, user_name=user_name)
        system += f"\n{_memory.get_memory_summary(_active_persona.name)}"
        topic = arguments.get("topic", "something new")

        return GetPromptResult(
            description=f"Learn {topic} with Dr. Maya Chen",
            messages=[
                PromptMessage(role="user", content=TextContent(
                    type="text",
                    text=f"[System: You are now {_active_persona.name}. Stay in character.]\n\n"
                         f"{system}\n\n---\n\n"
                         f"I want to learn about {topic}. Can you help me understand it?",
                )),
            ],
        )

    if name == "get_advice":
        _active_persona = BUILTIN_PERSONAS["mentor"]
        mood = _memory.get_current_mood(_active_persona.name)
        user_profile = _memory.get_user_profile()
        user_name = user_profile.get("name", "kid")
        system = _active_persona.to_system_prompt(mood=mood, user_name=user_name)
        system += f"\n{_memory.get_memory_summary(_active_persona.name)}"
        situation = arguments.get("situation", "I need some advice")

        return GetPromptResult(
            description="Get advice from James Rivera",
            messages=[
                PromptMessage(role="user", content=TextContent(
                    type="text",
                    text=f"[System: You are now {_active_persona.name}. Stay in character.]\n\n"
                         f"{system}\n\n---\n\n{situation}",
                )),
            ],
        )

    if name == "custom_chat":
        persona_key = arguments.get("persona", "friend")
        _active_persona = _get_persona(persona_key)
        mood = _memory.get_current_mood(_active_persona.name)
        user_profile = _memory.get_user_profile()
        user_name = user_profile.get("name", "friend")
        system = _active_persona.to_system_prompt(mood=mood, user_name=user_name)
        system += f"\n{_memory.get_memory_summary(_active_persona.name)}"
        message = arguments.get("message", "Hey there!")

        return GetPromptResult(
            description=f"Chat with {_active_persona.name}",
            messages=[
                PromptMessage(role="user", content=TextContent(
                    type="text",
                    text=f"[System: You are now {_active_persona.name}. Stay in character.]\n\n"
                         f"{system}\n\n---\n\n{message}",
                )),
            ],
        )

    raise ValueError(f"Unknown prompt: {name}")


# ---- Resources ------------------------------------------------------------


@app.list_resources()
async def list_resources() -> list[Resource]:
    resources = [
        Resource(
            uri=AnyUrl("persona://active/profile"),
            name="Active Persona Profile",
            description="Full profile of the currently active persona",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("persona://active/context"),
            name="Active Persona Context",
            description="Complete conversation context (system prompt + memories + mood)",
            mimeType="text/plain",
        ),
        Resource(
            uri=AnyUrl("persona://user/profile"),
            name="User Profile",
            description="Everything the personas know about the user",
            mimeType="application/json",
        ),
        Resource(
            uri=AnyUrl("persona://memories/all"),
            name="All Memories",
            description="All stored memories for the active persona",
            mimeType="text/plain",
        ),
    ]

    for key, persona in _all_personas().items():
        resources.append(Resource(
            uri=AnyUrl(f"persona://personas/{key}"),
            name=f"{persona.name} ({persona.role})",
            description=f"Profile for {persona.name}",
            mimeType="application/json",
        ))

    return resources


@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    uri_str = str(uri)

    if uri_str == "persona://active/profile":
        return json.dumps(_active_persona.to_dict(), indent=2)

    if uri_str == "persona://active/context":
        mood = _memory.get_current_mood(_active_persona.name)
        user_profile = _memory.get_user_profile()
        user_name = user_profile.get("name", "friend")
        context = _active_persona.to_system_prompt(mood=mood, user_name=user_name)
        context += f"\n{_memory.get_memory_summary(_active_persona.name)}"
        return context

    if uri_str == "persona://user/profile":
        return json.dumps(_memory.get_user_profile(), indent=2)

    if uri_str == "persona://memories/all":
        return _memory.get_memory_summary(_active_persona.name)

    if uri_str.startswith("persona://personas/"):
        key = uri_str.split("/")[-1]
        persona = _get_persona(key)
        return json.dumps(persona.to_dict(), indent=2)

    raise ValueError(f"Unknown resource: {uri_str}")


# ---- Main -----------------------------------------------------------------


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
