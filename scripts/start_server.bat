@echo off
setlocal
echo ========================================================
echo  OpenMemory - Starting Local Governance Console & Server
echo ========================================================

cd /d "%~dp0\.."
if not exist .venv (
    echo [INFO] Virtualenv not detected, running with system python...
)
python -m server.app
