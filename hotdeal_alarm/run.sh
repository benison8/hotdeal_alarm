#!/usr/bin/with-contenv bashio

# Python 종속성 설치
pip install -r /app/requirements.txt

# Home Assistant 설정 값 가져오기
INTERVAL=$(bashio::config 'interval_minutes')
URL=$(bashio::config 'target_url')

bashio::log.info "Starting Hotdeal Monitor with interval: $INTERVAL minutes"
bashio::log.info "Target URL: $URL"

# Python 스크립트 실행 (무한 루프)
# Home Assistant 환경 변수를 hotdeal_monitor.py에 전달
python3 /app/hotdeal_monitor.py --interval "$INTERVAL" --url "$URL"