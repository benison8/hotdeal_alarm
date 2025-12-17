#!/bin/bash

# Home Assistant 설정 값 가져오기 (bashio를 사용할 수 없는 경우를 대비해 기본값 설정)
# bashio가 작동하지 않을 경우를 대비한 표준 bash 문법입니다.
if [ -f /usr/bin/bashio ]; then
    INTERVAL=$(/usr/bin/bashio::config 'interval_minutes')
    URL=$(/usr/bin/bashio::config 'target_url')
else
    INTERVAL=10
    URL="https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu"
fi

echo "Starting Hotdeal Monitor..."
echo "Interval: $INTERVAL min, URL: $URL"

# 파이썬 스크립트 실행 (-u 옵션으로 실시간 로그 출력)
python3 -u /app/hotdeal_alarm.py --interval "$INTERVAL" --url "$URL"
