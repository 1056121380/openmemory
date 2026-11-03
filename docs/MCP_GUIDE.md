# OpenMemory MCP Integration Guide

OpenMemory implements the official **Model Context Protocol (MCP)** standard over `stdio`. It connects seamlessly to Cursor, Claude Desktop, Windsurf, Cline, and Codex.

---

## 1. Quick Setup via Interactive Wizard

Run the built-in wizard from the root of the repository:

```bash
# On Windows
scripts\setup.bat

# On Linux / macOS
chmod +x scripts/setup.sh && ./scripts/setup.sh
```

Or invoke Python directly:
```bash
python client/wizard.py
```

---

## 2. Manual Configuration

### A. Cursor (`.cursor/mcp.json` or Global Settings)

Add OpenMemory to your workspace `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "openmemory": {
      "command": "python",
      "args": [
        "/path/to/openmemory/client/mcp_server.py",
        "--mode",
        "local"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1"
      }
    }
  }
}
```

*Tip: For Windows, use forward slashes or double backslashes in paths.*

---

### B. Claude Desktop

Edit your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "openmemory": {
      "command": "python3",
      "args": [
        "/absolute/path/to/openmemory/client/mcp_server.py",
        "--mode",
        "local"
      ]
    }
  }
}
```

---

### C. Windsurf & Cline

Add to `~/.codeium/windsurf/mcp_config.json` or your Cline MCP settings:

```json
{
  "mcpServers": {
    "openmemory": {
      "command": "python",
      "args": [
        "/absolute/path/to/openmemory/client/mcp_server.py",
        "--mode",
        "local"
      ]
    }
  }
}
```

---

## 3. Remote Hub Mode (Shared Team / Multi-Device)

If you are running the OpenMemory Hub on a remote server or NAS, configure your local MCP client to connect via HTTP:

```json
{
  "mcpServers": {
    "openmemory": {
      "command": "python",
      "args": [
        "/path/to/client/mcp_server.py",
        "--mode",
        "remote",
        "--url",
        "https://your-openmemory-server.com",
        "--token",
        "your-secret-token"
      ]
    }
  }
}
```

---

## 4. Available MCP Tools

| Tool Name | Purpose | When LLM uses it |
|---|---|---|
| `recall_memories` | Recall persona, styles, architecture decisions | Before planning or generating code |
| `record_memory` | Save user preferences, architectural rules | When user declares or clarifies rules |
| `correct_memory` | Supersede outdated or incorrect memory | When user corrects an earlier mistake |
| `reinforce_memory` | Boost confidence of corroborated facts | When user repeatedly follows a habit |
| `forget_memory` | Safely soft-delete or cascade-forget | When user asks to forget a past detail |
| `get_governance_stats`| Inspect system memory health and conflicts | During diagnosis or system status checks |
