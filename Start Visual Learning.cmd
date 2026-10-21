@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup-app.ps1"
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m visual_learning
if errorlevel 1 pause
