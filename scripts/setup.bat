@echo off
setlocal
echo ========================================================
echo  OpenMemory - 1-Click Setup for Windows
echo ========================================================

cd /d "%~dp0\.."

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH! Please install Python 3.10+.
    pause
    exit /b 1
)

echo [1/2] Installing requirements...
pip install -r requirements.txt

echo.
echo [2/2] Launching interactive IDE configuration wizard...
python client\wizard.py

echo.
echo ========================================================
echo  Setup Completed! You can now use OpenMemory in your IDE.
echo ========================================================
pause
