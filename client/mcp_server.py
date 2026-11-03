"""Universal Model Context Protocol (MCP) Server for OpenMemory.

Connects Cursor, Claude Desktop, Windsurf, Cline, Codex, AntiGravity, and OpenClaw
to the 6-Layer Memory Governance & Provenance Engine.

Operates over stdio using JSON-RPC 2.0. Supports:
- Local Mode (default): 100% offline, directly uses local SQLite WAL database.
- Remote Mode: Connects to a self-hosted OpenMemory server via REST API.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

# Add parent directory to sys.path so core can be imported in local mode
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from core.engine import GovernanceEngine
from core.models import Sensitivity, SourceType

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[OpenMemory-MCP] %(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("openmemory.mcp")


class MCPRemoteClient:
    """Client for remote OpenMemory server."""

    def __init__(self, base_url: str, api_token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token or os.environ.get("OPENMEMORY_TOKEN", "")

    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Any:
        url = f"{self.base_url}{endpoint}"
        body = json.dumps(data).encode("utf-8") if data is not None else None
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))


class MCPServer:
    """Universal MCP Server implementing standard JSON-RPC 2.0 over stdio."""

    def __init__(self, mode: str = "local", db_path: Optional[str] = None, remote_url: Optional[str] = None, token: Optional[str] = None):
        self.mode = mode
        if mode == "local":
            self.engine = GovernanceEngine(db_path=db_path)
            self.remote = None
            logger.info(f"Initialized in Local Mode (DB: {self.engine.storage.db_path})")
        else:
            self.engine = None
            self.remote = MCPRemoteClient(base_url=remote_url or "http://localhost:8000", api_token=token)
            logger.info(f"Initialized in Remote Mode (Server: {self.remote.base_url})")

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Return MCP tool schemas."""
        return [
            {
                "name": "recall_memories",
                "description": "Recall long-term memories, user habits, coding styles, decisions, and preferences from OpenMemory with confidence decay and provenance tracking.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language query to search relevant memories.",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Optional topic filter (e.g. 'code_style', 'architecture', 'user_preference').",
                        },
                        "max_sensitivity": {
                            "type": "string",
                            "enum": ["L0_public", "L1_work", "L2_private"],
                            "default": "L1_work",
                            "description": "Highest sensitivity level allowed to read. Default is L1_work.",
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "description": "Maximum number of memories to return.",
                        },
                    },
                },
            },
            {
                "name": "record_memory",
                "description": "Record a new user preference, architectural decision, or habitual pattern. Automatically performs conflict detection and provenance logging.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Category or topic (e.g. 'code_style', 'backend', 'tool_preference').",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Clear, atomic statement of the memory or decision.",
                        },
                        "source_type": {
                            "type": "string",
                            "enum": ["user_statement", "tool_event", "ai_inference", "manual_audit"],
                            "default": "user_statement",
                            "description": "Provenance origin: 'user_statement' (high trust 0.95), 'ai_inference' (inferred 0.65), or 'tool_event' (0.85).",
                        },
                        "source_ref": {
                            "type": "string",
                            "default": "mcp_session",
                            "description": "Identifier of the conversation or file where this fact emerged.",
                        },
                        "evidence": {
                            "type": "string",
                            "description": "Literal quote or log line proving this memory.",
                        },
                        "sensitivity": {
                            "type": "string",
                            "enum": ["L0_public", "L1_work", "L2_private"],
                            "default": "L0_public",
                            "description": "Sensitivity tier: L0_public (general preferences), L1_work (project internals), L2_private (personal confidential).",
                        },
                        "scope": {
                            "type": "string",
                            "default": "global",
                            "description": "Scope tag: 'global' or project-specific identifier.",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keywords or search tags.",
                        },
                    },
                    "required": ["topic", "summary"],
                },
            },
            {
                "name": "correct_memory",
                "description": "Correct or supersede an existing memory when the user updates their preference or when an AI inference was wrong. Preserves full audit trail.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "old_memory_id": {
                            "type": "string",
                            "description": "ID of the memory to replace.",
                        },
                        "new_summary": {
                            "type": "string",
                            "description": "New correct memory statement.",
                        },
                        "reason": {
                            "type": "string",
                            "default": "User correction",
                            "description": "Explanation of why the old memory was superseded.",
                        },
                    },
                    "required": ["old_memory_id", "new_summary"],
                },
            },
            {
                "name": "reinforce_memory",
                "description": "Reinforce an existing memory when it is corroborated again by user action, boosting its confidence score.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "ID of the memory to reinforce.",
                        },
                        "boost": {
                            "type": "number",
                            "default": 0.05,
                            "description": "Amount to increment confidence (default 0.05).",
                        },
                    },
                    "required": ["memory_id"],
                },
            },
            {
                "name": "forget_memory",
                "description": "Safely soft-delete or cascade-forget a memory and alert if other memories depended on it.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "memory_id": {
                            "type": "string",
                            "description": "ID of the memory to forget.",
                        },
                        "cascade": {
                            "type": "boolean",
                            "default": True,
                            "description": "Whether to cascade stale recalculations for dependent derived memories.",
                        },
                        "reason": {
                            "type": "string",
                            "default": "User requested forget",
                            "description": "Reason for deletion.",
                        },
                    },
                    "required": ["memory_id"],
                },
            },
            {
                "name": "get_governance_stats",
                "description": "Inspect OpenMemory health stats: active memories, pending conflict adjudications, audit trail entries, and confidence decay status.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool call in local or remote mode."""
        if self.mode == "local":
            return self._handle_local_tool(tool_name, arguments)
        else:
            return self._handle_remote_tool(tool_name, arguments)

    def _normalize_sensitivity(self, val: str) -> str:
        v = (val or "").upper()
        if "L0" in v or "PUBLIC" in v:
            return Sensitivity.L0.value
        if "L2" in v or "PRIVATE" in v:
            return Sensitivity.L2.value
        return Sensitivity.L1.value

    def _normalize_source_type(self, val: str) -> str:
        v = (val or "").lower()
        if "infer" in v:
            return SourceType.AI_INFERENCE.value
        if "tool" in v or "event" in v:
            return SourceType.TOOL_EVENT.value
        return SourceType.DIRECT_STATEMENT.value

    def _handle_local_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "recall_memories":
            query = args.get("query", "")
            category = args.get("topic", "") or args.get("category", "")
            sens = self._normalize_sensitivity(args.get("max_sensitivity", "L1"))
            limit = int(args.get("limit", 10))

            if sens == Sensitivity.L0.value:
                allowed = [Sensitivity.L0.value]
            elif sens == Sensitivity.L1.value:
                allowed = [Sensitivity.L0.value, Sensitivity.L1.value]
            else:
                allowed = [Sensitivity.L0.value, Sensitivity.L1.value, Sensitivity.L2.value]

            # Apply decay first
            self.engine.apply_confidence_decay()
            memories = self.engine.get_memories(
                query=query,
                category=category,
                status="active",
                allowed_sensitivities=allowed,
                limit=limit,
            )
            return [m.to_dict() for m in memories]

        elif tool_name == "record_memory":
            statement = args.get("summary") or args.get("statement", "")
            category = args.get("topic") or args.get("category", "preference")
            src_type = self._normalize_source_type(args.get("source_type", "user_statement"))
            sens = self._normalize_sensitivity(args.get("sensitivity", "L0"))
            scope = args.get("scope", "general")
            evidence = args.get("evidence") or args.get("source_snippet", "")
            source_ref = args.get("source_ref", "mcp_client")

            res = self.engine.add_memory(
                statement=statement,
                category=category,
                source_type=src_type,
                sensitivity=sens,
                scope=scope,
                source_client="mcp",
                source_session=source_ref,
                source_snippet=evidence,
                check_conflict=True,
                operator="mcp_agent",
            )
            return res

        elif tool_name == "correct_memory":
            old_id = args.get("old_memory_id") or args.get("memory_id")
            new_stmt = args.get("new_summary") or args.get("new_statement")
            reason = args.get("reason", "用户修正")
            res = self.engine.supersede(
                memory_id=old_id,
                new_statement=new_stmt,
                reason=reason,
                operator="user",
            )
            return {
                "status": "superseded",
                "old_memory_id": old_id,
                "new_memory_id": res["new_id"],
                "created_at": res["created_at"],
            }

        elif tool_name == "reinforce_memory":
            mem_id = args["memory_id"]
            res = self.engine.reinforce(mem_id, snippet=args.get("snippet", ""), operator="mcp_agent")
            return res

        elif tool_name == "forget_memory":
            res = self.engine.forget(
                memory_id=args["memory_id"],
                reason=args.get("reason", "用户指令遗忘"),
                operator="user",
            )
            return res

        elif tool_name == "get_governance_stats":
            return self.engine.get_stats()

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def _handle_remote_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        if tool_name == "recall_memories":
            params = []
            if args.get("query"):
                params.append(f"q={urllib.request.quote(args['query'])}")
            if args.get("topic"):
                params.append(f"topic={urllib.request.quote(args['topic'])}")
            if args.get("max_sensitivity"):
                params.append(f"max_sensitivity={args['max_sensitivity']}")
            if args.get("limit"):
                params.append(f"limit={args['limit']}")
            qs = "&".join(params)
            endpoint = f"/api/memories?status=active{('&' + qs) if qs else ''}"
            return self.remote._request("GET", endpoint)

        elif tool_name == "record_memory":
            return self.remote._request("POST", "/api/memories", args)

        elif tool_name == "correct_memory":
            old_id = args["old_memory_id"]
            return self.remote._request("POST", f"/api/memories/{old_id}/supersede", {
                "new_summary": args["new_summary"],
                "reason": args.get("reason", "User correction"),
            })

        elif tool_name == "reinforce_memory":
            mem_id = args["memory_id"]
            return self.remote._request("POST", f"/api/memories/{mem_id}/reinforce", {
                "boost": args.get("boost", 0.05)
            })

        elif tool_name == "forget_memory":
            mem_id = args["memory_id"]
            return self.remote._request("DELETE", f"/api/memories/{mem_id}")

        elif tool_name == "get_governance_stats":
            return self.remote._request("GET", "/api/stats")

        else:
            raise ValueError(f"Unknown tool: {tool_name}")

    def run(self):
        """Standard JSON-RPC 2.0 loop reading from stdin and writing to stdout."""
        logger.info("OpenMemory MCP Server is listening on stdio...")
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                request = json.loads(line)
            except Exception as e:
                logger.error(f"Failed to parse JSON: {e}")
                continue

            msg_id = request.get("id")
            method = request.get("method")
            params = request.get("params", {})

            # Standard MCP Handlers
            if method == "initialize":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {
                            "tools": {},
                        },
                        "serverInfo": {
                            "name": "openmemory",
                            "version": "1.0.0",
                        },
                    },
                }
                self._send_response(response)

            elif method == "notifications/initialized":
                # Notification, no response needed
                logger.info("Client connected and initialized.")

            elif method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "tools": self.get_tool_definitions(),
                    },
                }
                self._send_response(response)

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                try:
                    result = self.handle_tool_call(tool_name, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result, ensure_ascii=False, indent=2),
                                }
                            ]
                        },
                    }
                except Exception as err:
                    logger.error(f"Error handling tool call {tool_name}: {err}")
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32000,
                            "message": str(err),
                        },
                    }
                self._send_response(response)

            elif method == "ping":
                self._send_response({"jsonrpc": "2.0", "id": msg_id, "result": {}})

            else:
                if msg_id is not None:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method '{method}' not found",
                        },
                    }
                    self._send_response(response)

    def _send_response(self, response: Dict[str, Any]):
        out = json.dumps(response, ensure_ascii=False)
        sys.stdout.write(out + "\n")
        sys.stdout.flush()


def start_mcp_server():
    """CLI entrypoint for running the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="OpenMemory Universal MCP Server")
    parser.add_argument("--mode", choices=["local", "remote"], default="local", help="Operation mode: 'local' (offline SQLite) or 'remote' (HTTP API)")
    parser.add_argument("--db", default=None, help="Path to SQLite memory database (local mode)")
    parser.add_argument("--url", default=None, help="Server URL (remote mode, default http://localhost:8000)")
    parser.add_argument("--token", default=None, help="API Bearer Token (remote mode)")
    args = parser.parse_args()

    server = MCPServer(mode=args.mode, db_path=args.db, remote_url=args.url, token=args.token)
    server.run()


if __name__ == "__main__":
    start_mcp_server()
