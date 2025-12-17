#!/usr/bin/with-contenv bashio

# 1. Python 종속성 설치 (이미 Dockerfile에서 했다면 생략 가능하지만 안전을 위해 유지)
pip3 install -r /app/requirements.txt

# 2. Home Assistant 설정 값 가져오기
# config.yaml의 options에 정의한 이름을 넣어야 합니다.
INTERVAL=$(bashio::config 'interval_minutes')
URL=$(bashio::config 'target_url')

bashio::log.info "Starting Hotdeal Monitor..."
bashio::log.info "Interval: $INTERVAL min, URL: $URL"

# 3. Python 스크립트 실행
# -u 옵션을 붙여야 로그가 실시간으로 화면에 출력됩니다.
python3 -u /app/hotdeal_alarm.py --interval "$INTERVAL" --url "$URL"
