import os
import requests
import logging

_LOGGER = logging.getLogger(__name__)


def send_ha_notify(message: str) -> None:
    """
    Home Assistant notify 서비스로 메시지 전송
    (notify.notify)
    """
    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")

    if not supervisor_token:
        _LOGGER.error("SUPERVISOR_TOKEN not found. Is this running as an add-on?")
        return

    url = "http://supervisor/core/api/services/notify/notify"
    headers = {
        "Authorization": f"Bearer {supervisor_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "message": message
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code >= 300:
            _LOGGER.error(
                "HA notify failed: %s - %s",
                response.status_code,
                response.text,
            )
        else:
            _LOGGER.info("HA notify sent successfully")

    except Exception as e:
        _LOGGER.exception("Exception while sending HA notify: %s", e)


def send_telegram(message: str, bot_token: str, chat_id: str) -> None:
    """
    Telegram Bot API로 메시지 전송
    """
    if not bot_token or not chat_id:
        _LOGGER.warning("Telegram token or chat_id not set, skipping telegram notify")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(url, data=payload, timeout=10)

        if response.status_code >= 300:
            _LOGGER.error(
                "Telegram notify failed: %s - %s",
                response.status_code,
                response.text,
            )
        else:
            _LOGGER.info("Telegram notify sent successfully")

    except Exception as e:
        _LOGGER.exception_
