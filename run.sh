#!/bin/bash
set -e

if [ -f /usr/bin/bashio ]; then
    INTERVAL=$(/usr/bin/bashio::config 'interval_minutes')
    URL=$(/usr/bin/bashio::config 'target_url')
else
    INTERVAL=10
    URL="https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu"
fi

echo "--- Hotdeal Monitor Starting ---"
echo "Interval: $INTERVAL min"
echo "URL: $URL"

exec python3 -u /app/hotdeal_monitor.py \
  --interval "$INTERVAL" \
  --url "$URL"

