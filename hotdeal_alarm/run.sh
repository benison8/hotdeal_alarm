#!/usr/bin/with-contenv bashio
set -e

export CONFIG_PATH="/data/options.json"
export PYTHONUNBUFFERED=1
exec /opt/venv/bin/python -u /app/main.py

