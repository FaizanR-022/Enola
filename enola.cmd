@echo off
rem Start all of Enola in one terminal. Double-click, or run `enola` from this folder.
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=python"
)
"%PY%" -m enola.scripts.dev %*
if errorlevel 1 (
  echo.
  echo Enola exited with an error. Press any key to close.
  pause >nul
)
