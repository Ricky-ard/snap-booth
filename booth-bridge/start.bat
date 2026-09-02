@echo off
cd /d "%~dp0"
pip install --quiet fastapi uvicorn
python main.py
