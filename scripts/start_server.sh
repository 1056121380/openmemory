#!/usr/bin/env bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
cd "$DIR"

echo "========================================================"
echo "  OpenMemory - Starting Local Governance Console & Server"
echo "========================================================"

python3 -m server.app
