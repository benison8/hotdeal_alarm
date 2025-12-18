import time
import argparse
from notifier import send_ha_notify, send_telegram
from hotdeal_logic import check_deal

parser = argparse.ArgumentParser()
parser.add_argument("--interval", type=int)
parser.add_argument("--url", type=str)
parser.add_argument("--notify-type", type=str)
parser.add_argument("--tg-token", type=str)
parser.add_argument("--tg-chat-id", type=str)
args = parser.parse_args()

print("Hotdeal alarm started")

while True:
    deal = check_deal(args.url)

    if deal:
        message = f"🔥 핫딜 발견!\n{deal}"

        if args.notify_type in ("ha", "both"):
            send_ha_notify(message)

        if args.notify_type in ("telegram", "both"):
            send_telegram(
                message,
                args.tg_token,
                args.tg_chat_id
            )

    time.sleep(args.interval)
