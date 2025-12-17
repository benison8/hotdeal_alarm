if [ -f /usr/bin/bashio ]; then
    INTERVAL=$(/usr/bin/bashio::config 'interval_minutes')
    URL=$(/usr/bin/bashio::config 'target_url')
else
    INTERVAL=10
    URL="https://www.ppomppu.co.kr/zboard/zboard.php?id=ppomppu"
fi

echo "Starting Hotdeal Monitor..."
echo "Interval: $INTERVAL min, URL: $URL"

python3 -u /app/hotdeal_alarm.py --interval "$INTERVAL" --url "$URL"
