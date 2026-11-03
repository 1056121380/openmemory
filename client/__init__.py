"""OpenMemory Client Package.

Includes the Universal MCP Server, Local Session Sync & Scrubber,
and Configuration Wizards for Cursor, Claude Desktop, Windsurf, Cline, and Codex.
"""

from .mcp_server import start_mcp_server

__all__ = ["start_mcp_server"]
