# 🎭 Persona MCP Server

An MCP (Model Context Protocol) server that transforms any AI client into a **realistic person** — a friend, teacher, or mentor with genuine personality, persistent memory, and emotional awareness.

Unlike a typical AI assistant, Persona MCP creates characters that feel *real*: they have opinions, quirks, bad days, inside jokes, and they remember your past conversations.

## Features

- **3 Built-in Personas** with deep, realistic personalities:
  - **Alex** (Friend) — A 28-year-old UX designer from Portland who's obsessed with rock climbing and has strong opinions about coffee
  - **Dr. Maya Chen** (Teacher) — A 42-year-old CS professor who explains everything with analogies and celebrates your "aha moments"
  - **James Rivera** (Mentor) — A 55-year-old former VP of Engineering who shares wisdom through stories and never gives you the answer directly

- **Persistent Memory** — Remembers facts about you, your preferences, life events, and emotional context across sessions (SQLite-backed)

- **Emotional Awareness** — Personas track and respond to mood shifts naturally

- **Custom Personas** — Create your own characters with a simple JSON file

- **MCP Native** — Works with Claude Desktop, Cursor, Zed, and any MCP-compatible client

## Quick Start

### Install

```bash
pip install persona-mcp
```

Or install from source:

```bash
git clone https://github.com/CppDevVS2026/persona-mcp.git
cd persona-mcp
pip install -e .
```

### Configure with Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "persona": {
      "command": "persona-mcp"
    }
  }
}
```

Or if running from source:

```json
{
  "mcpServers": {
    "persona": {
      "command": "python",
      "args": ["-m", "persona_mcp"]
    }
  }
}
```

### Configure with Cursor

Add to your Cursor MCP settings:

```json
{
  "mcpServers": {
    "persona": {
      "command": "persona-mcp"
    }
  }
}
```

## Usage

Once configured, you can interact with the persona through your MCP client.

### Prompts (Quick Start Conversations)

| Prompt | Description |
|--------|-------------|
| `chat_as_friend` | Start a casual conversation with Alex |
| `learn_with_teacher` | Begin a learning session with Dr. Maya Chen |
| `get_advice` | Get life/career advice from James Rivera |
| `custom_chat` | Chat with any available persona |

### Tools

| Tool | Description |
|------|-------------|
| `switch_persona` | Switch between friend, teacher, mentor (or load a custom one) |
| `remember` | Store a memory about the user (facts, preferences, events, emotions) |
| `recall` | Retrieve memories — the persona remembers past conversations |
| `forget` | Remove a specific memory |
| `set_mood` | Set the persona's emotional state (happy, tired, excited, etc.) |
| `set_user_info` | Store user profile info (name, age, interests) |
| `get_user_profile` | See everything the persona knows about you |
| `get_persona_info` | View a persona's full personality profile |
| `list_personas` | List all available personas |
| `get_conversation_context` | Get the complete context package for staying in character |
| `clear_memories` | Reset all memories for a persona |

### Resources

| Resource URI | Description |
|-------------|-------------|
| `persona://active/profile` | Active persona's full profile (JSON) |
| `persona://active/context` | Complete conversation context with memories |
| `persona://user/profile` | User profile data |
| `persona://memories/all` | All stored memories |
| `persona://personas/{key}` | Profile for a specific persona |

## Custom Personas

Create your own persona by writing a JSON file:

```json
{
  "name": "Luna",
  "role": "friend",
  "age": 24,
  "background": "A freelance illustrator who lives in a tiny apartment in Brooklyn with three cats...",
  "personality_traits": ["creative", "introverted but warm", "witty in a dry way"],
  "speaking_style": "Thoughtful and visual — describes things in images and colors...",
  "quirks": [
    "Doodles during every conversation (describes what she's drawing)",
    "Names all her plants and talks about them like friends"
  ],
  "interests": ["illustration", "cats", "indie music", "tea", "anime"],
  "catchphrases": [
    "Okay that's going in my sketchbook",
    "Hmm, let me think about that while I pet Chairman Meow"
  ],
  "emotional_baseline": "calm and observant, with bursts of creative excitement"
}
```

Then load it:
```
Use the switch_persona tool with custom_path="/path/to/luna.json"
```

## How It Works

Persona MCP doesn't generate responses itself — it provides **rich context, personality prompts, and memory tools** that instruct the host AI (Claude, GPT, etc.) to behave as a realistic character.

The magic comes from:
1. **Detailed system prompts** with personality traits, quirks, speech patterns, and rules for realistic behavior
2. **Persistent memory** that makes the character remember and reference past conversations naturally
3. **Emotional state tracking** that affects tone and energy
4. **Pre-built conversation starters** (prompts) that set up the character context automatically

## Data Storage

Memories are stored locally in SQLite at `~/.persona-mcp/memory.db`. No data is sent to external services.

## License

MIT
