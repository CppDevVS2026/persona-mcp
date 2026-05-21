"""
Persona MCP — One-Click Windows Setup Script
Run this and it will:
1. Install persona-mcp
2. Configure Windsurf, Claude Desktop, and VS Code (whichever you have)
3. Tell you what to do next
"""

import json
import os
import subprocess
import sys
from pathlib import Path


def main():
    print("=" * 60)
    print("  Persona MCP — Windows Setup")
    print("=" * 60)
    print()

    # Step 1: Install the package
    print("[1/3] Installing persona-mcp...")
    script_dir = Path(__file__).parent.resolve()
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(script_dir)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  ERROR: pip install failed:\n{result.stderr}")
        print("  Try running: pip install -e .")
        return
    print("  Done!")

    # Step 2: Verify import works
    print("[2/3] Verifying installation...")
    result = subprocess.run(
        [sys.executable, "-c", "from persona_mcp.server import mcp; print('OK')"],
        capture_output=True,
        text=True,
    )
    if "OK" not in result.stdout:
        print(f"  ERROR: Import failed:\n{result.stderr}")
        return
    print("  Done!")

    # Step 3: Configure MCP clients
    print("[3/3] Configuring MCP clients...")
    print()

    python_path = sys.executable.replace("\\", "\\\\")
    server_config = {
        "command": sys.executable,
        "args": ["-m", "persona_mcp"],
    }

    configured = []

    # --- Windsurf ---
    windsurf_paths = [
        Path.home() / ".codeium" / "windsurf" / "mcp_config.json",
        Path(os.environ.get("APPDATA", "")) / "Windsurf" / "mcp_config.json",
    ]
    for wp in windsurf_paths:
        if wp.parent.exists():
            _write_mcp_config(wp, "persona", server_config)
            configured.append(f"Windsurf ({wp})")
            break

    # --- Claude Desktop ---
    claude_paths = [
        Path(os.environ.get("APPDATA", ""))
        / "Claude"
        / "claude_desktop_config.json",
    ]
    for cp in claude_paths:
        if cp.parent.exists():
            _write_mcp_config(cp, "persona", server_config)
            configured.append(f"Claude Desktop ({cp})")
            break

    # --- VS Code / Cursor ---
    vscode_paths = [
        Path(os.environ.get("APPDATA", "")) / "Code" / "User" / "settings.json",
        Path(os.environ.get("APPDATA", ""))
        / "Cursor"
        / "User"
        / "settings.json",
    ]
    for vp in vscode_paths:
        if vp.exists():
            _write_vscode_config(vp, "persona", server_config)
            configured.append(f"VS Code/Cursor ({vp})")

    print()
    if configured:
        print("Configured for:")
        for c in configured:
            print(f"  - {c}")
    else:
        print("No MCP clients found automatically.")
        print("Manual config — add this to your MCP config file:")
        print()
        manual = {"mcpServers": {"persona": server_config}}
        print(json.dumps(manual, indent=2))

    print()
    print("=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Restart Windsurf / Claude Desktop / your editor")
    print("  2. Start chatting! Try: 'Hey Alex, what's up?'")
    print()
    print("Python path used:", sys.executable)
    print()


def _write_mcp_config(path, name, server_config):
    """Write or update a standalone MCP config file."""
    config = {}
    if path.exists():
        try:
            config = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            print(f"  SKIPPED: {path} (contains invalid JSON)")
            print("  Add this manually to that file:")
            snippet = json.dumps({"mcpServers": {name: server_config}}, indent=4)
            for line in snippet.splitlines():
                print(f"    {line}")
            return False

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"][name] = server_config

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
    print(f"  Wrote: {path}")
    return True


def _write_vscode_config(path, name, server_config):
    """Add MCP config to VS Code settings.json (JSONC-safe)."""
    if path.exists():
        try:
            json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            # VS Code settings.json is JSONC (comments/trailing commas).
            # Cannot safely parse — skip to avoid destroying user settings.
            print(f"  SKIPPED: {path} (contains comments or non-standard JSON)")
            print("  Add this manually in VS Code settings (Ctrl+Shift+P → Settings JSON):")
            snippet = json.dumps({"mcpServers": {name: server_config}}, indent=4)
            for line in snippet.splitlines():
                print(f"    {line}")
            return

    config = {}
    if path.exists():
        config = json.loads(path.read_text())

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    config["mcpServers"][name] = server_config
    path.write_text(json.dumps(config, indent=2))
    print(f"  Wrote: {path}")


if __name__ == "__main__":
    main()
