#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "========================================================"
echo "  OpenMemory - Starting Local MCP Server (Stdio)"
echo "========================================================"

python3 client/mcp_server.py --mode local
