@echo off
cd /d "%~dp0.."
if not exist .venv\Scripts\python.exe (
  echo Run scripts\setup_windows.bat first.
  pause
  exit /b 1
)
start "" http://127.0.0.1:8000
.venv\Scripts\python.exe -m aksharacheck serve --port 8000
pause
