#!/usr/bin/with-contenv bashio
set -e

export CONFIG_PATH="/data/options.json"
exec /opt/venv/bin/python /app/main.py

