@echo off
setlocal
echo ========================================================
echo  OpenMemory - Starting Local MCP Server (Stdio)
echo ========================================================

cd /d "%~dp0\.."
python client\mcp_server.py --mode local
