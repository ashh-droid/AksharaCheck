@echo off
cd /d "%~dp0.."
py -3 -m venv .venv
if errorlevel 1 (echo Python 3 is required & pause & exit /b 1)
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e ".[test]"
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 (echo Chromium install failed & pause & exit /b 1)
echo Setup complete! Use scripts\start_backend_windows.bat to start the server.
pause
