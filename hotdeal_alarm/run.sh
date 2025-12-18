#!/usr/bin/with-contenv bashio
set -e

CONFIG_PATH="/data/options.json"
export CONFIG_PATH

exec python3 /app/main.py
