#!/usr/bin/with-contenv bashio
set -eux

export CONFIG_PATH="/data/options.json"
# Run Python unbuffered and capture stdout/stderr to /data/addon_start.log for debugging
if [ ! -x /opt/venv/bin/python ]; then
	echo "WARN: python interpreter not found at /opt/venv/bin/python" >> /data/addon_start.log || true
fi
exec /opt/venv/bin/python -u /app/main.py >> /data/addon_start.log 2>&1

