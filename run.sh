#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

INTERVAL=$(jq -r '.interval' $CONFIG_PATH)
URL=$(jq -r '.url' $CONFIG_PATH)
NOTIFY_TYPE=$(jq -r '.notify_type' $CONFIG_PATH)
TG_TOKEN=$(jq -r '.telegram_bot_token' $CONFIG_PATH)
TG_CHAT_ID=$(jq -r '.telegram_chat_id' $CONFIG_PATH)

echo "Starting hotdeal alarm..."

exec python3 -u /app/main.py \
  --interval "$INTERVAL" \
  --url "$URL" \
  --notify-type "$NOTIFY_TYPE" \
  --tg-token "$TG_TOKEN" \
  --tg-chat-id "$TG_CHAT_ID"
