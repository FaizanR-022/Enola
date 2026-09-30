#!/usr/bin/env sh
# Start all of Enola in one terminal. Run as ./enola.sh from Git Bash, WSL or any POSIX shell.
# Windows cmd / PowerShell / Explorer use enola.cmd instead.
set -e
cd "$(dirname "$0")"
if [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python"
fi
exec "$PY" -m enola.scripts.dev "$@"
