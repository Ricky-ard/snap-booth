#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
pip install --quiet fastapi uvicorn
exec python main.py
