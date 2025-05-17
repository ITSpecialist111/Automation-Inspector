#!/usr/bin/ash
set -e
uvicorn app.main:app --host 0.0.0.0 --port 1234
