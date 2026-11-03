#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "========================================================"
echo "  OpenMemory - 1-Click Setup for Linux & macOS"
echo "========================================================"

if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed or not in PATH! Please install Python 3.10+."
    exit 1
fi

echo "[1/2] Installing requirements..."
pip3 install -r requirements.txt

echo ""
echo "[2/2] Launching interactive IDE configuration wizard..."
python3 client/wizard.py

echo ""
echo "========================================================"
echo "  Setup Completed! You can now use OpenMemory in your IDE."
echo "========================================================"
