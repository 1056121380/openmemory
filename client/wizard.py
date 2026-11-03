"""Interactive 1-Click Setup Wizard for OpenMemory MCP.

Automatically detects installed AI IDEs (Cursor, Claude Desktop, Windsurf, Cline)
and generates or updates their MCP configuration files.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_default_mcp_config(mode: str = "local", server_url: str = "http://localhost:8000"):
    python_exe = sys.executable
    mcp_script = os.path.join(parent_dir, "client", "mcp_server.py")

    if mode == "local":
        args = [mcp_script, "--mode", "local"]
    else:
        args = [mcp_script, "--mode", "remote", "--url", server_url]

    return {
        "command": python_exe,
        "args": args,
        "env": {
            "PYTHONUNBUFFERED": "1"
        }
    }


def configure_claude_desktop():
    if sys.platform == "win32":
        config_path = Path(os.environ.get("APPDATA", "")) / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        config_path = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"

    print(f"\n[Claude Desktop] Target config path: {config_path}")
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = {"mcpServers": {}}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"mcpServers": {}}

    data.setdefault("mcpServers", {})["openmemory"] = get_default_mcp_config(mode="local")
    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print("  -> Claude Desktop configured successfully!")


def configure_cursor(workspace_dir: str = "."):
    cursor_dir = Path(workspace_dir) / ".cursor"
    cursor_dir.mkdir(parents=True, exist_ok=True)
    config_path = cursor_dir / "mcp.json"

    data = {"mcpServers": {}}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            data = {"mcpServers": {}}

    data.setdefault("mcpServers", {})["openmemory"] = get_default_mcp_config(mode="local")
    config_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[Cursor] Configured: {config_path.resolve()}")


def main():
    print("=" * 60)
    print("  OpenMemory - 1-Click Environment Setup Wizard")
    print("=" * 60)
    print("1. Configure Claude Desktop (Global)")
    print("2. Configure Cursor (.cursor/mcp.json in current directory)")
    print("3. Print Raw MCP JSON Config snippet (for Windsurf / Cline / Codex)")
    print("4. Exit")

    choice = input("\nSelect an option [1-4] (default: 1): ").strip() or "1"

    if choice == "1":
        configure_claude_desktop()
    elif choice == "2":
        configure_cursor(".")
    elif choice == "3":
        snippet = {
            "mcpServers": {
                "openmemory": get_default_mcp_config(mode="local")
            }
        }
        print("\nCopy and paste this snippet into your IDE's MCP config:")
        print("-" * 50)
        print(json.dumps(snippet, indent=2))
        print("-" * 50)
    else:
        print("Setup cancelled.")


if __name__ == "__main__":
    main()
