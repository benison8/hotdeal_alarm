#!/bin/bash
set -e

# bashio 설정 값 읽기
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

# 파이썬 실행 (-u 옵션으로 로그 즉시 출력)
python3 -u /app/hotdeal_alarm.py --interval "$INTERVAL" --url "$URL"