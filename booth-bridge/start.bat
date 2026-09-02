@echo off
REM One-click launcher for Booth Bridge on Windows.
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo [booth-bridge] creating virtualenv...
  python -m venv .venv
)
call .venv\Scripts\activate.bat

echo [booth-bridge] installing/refreshing dependencies...
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q pywin32 2>NUL

echo [booth-bridge] starting on http://127.0.0.1:8787 ...
echo [booth-bridge] (make sure digiCamControl is running with the Web Server enabled)
python main.py %*
