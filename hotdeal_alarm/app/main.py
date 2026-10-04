import json
import os
import re
import time
import html
import traceback
import sys
import math
import unicodedata
from typing import Dict, List
from collections import Counter
from datetime import datetime

import requests
import cloudscraper


DATA_DIR = "/data"
STATE_FILE = os.path.join(DATA_DIR, "state.json")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/data/options.json")


def normalize_match_text(value: str) -> str:
    if value is None:
        return ""

    text = unicodedata.normalize("NFKC", str(value))
    text = text.lower()
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[\u200b-\u200d\u2060\ufeff]", "", text)
    text = re.sub(r"[\s\-_.,/()\[\]{}+!~`'\";:<>|\\]+", "", text, flags=re.UNICODE)
    return text.strip()


def sanitize_telegram_chat_id(value) -> str:
    if value is None:
        return ""

    chat_id = str(value).strip()
    if not chat_id:
        return ""

    chat_id = chat_id.replace(" ", "").replace("\t", "")
    if chat_id.startswith("@"):
        return chat_id if re.fullmatch(r"@[A-Za-z0-9_]+", chat_id) else ""
    if chat_id.startswith("+"):
        chat_id = chat_id[1:]
    if chat_id.startswith("chat_id:"):
        chat_id = chat_id.split(":", 1)[1].strip()
    if re.fullmatch(r"\d+:[A-Za-z0-9_-]+", chat_id):
        return ""
    if re.fullmatch(r"-?\d+", chat_id):
        return chat_id
    return ""


def log(*args):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(ts, *args, flush=True)


site_map = {
    "ppomppu": "뽐뿌",
    "clien": "클리앙",
    "ruriweb": "루리웹",
    "coolenjoy": "쿨엔조이",
    "quasarzone": "퀘이사존",
}

board_map = {
    "ppomppu": "뽐뿌게시판",
    "ppomppu4": "해외뽐뿌",
    "ppomppu8": "알리뽐뿌",
    "money": "재태크포럼",
    "allsell": "사고팔고",
    "jirum": "알뜰구매",
    "1020": "핫딜/예판 유저",
    "600004": "핫딜/예판 업체",
    "qb_saleinfo": "지름/할인정보",
}


def get_url_prefix(site_name: str) -> str:
    if site_name == "ppomppu":
        return "https://www.ppomppu.co.kr/zboard/"
    if site_name == "clien":
        return "https://www.clien.net"
    if site_name == "coolenjoy":
        return "https://coolenjoy.net"
    if site_name == "quasarzone":
        return "https://quasarzone.com"
    if site_name == "ruriweb":
        return "https://bbs.ruliweb.com"
    return ""


def clean_html_title(text: str) -> str:
    if not text:
        return ""
    # 쿨엔조이/그 외 게시판의 스크린리더용 태그 제거
    text = re.sub(r'<span[^>]*class="[^"]*sound_only[^"]*"[^>]*>[\s\S]*?</span>', '', text)
    # 모든 잔여 HTML 태그 제거
    text = re.sub(r"<[^>]+>", "", text)
    # HTML 엔티티 디코딩 및 다중 공백 정리
    text = html.unescape(text)
    return " ".join(text.split()).strip()


def load_config() -> Dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state() -> Dict:
    if not os.path.exists(STATE_FILE):
        return {"seen": {}, "mall_cache": {}, "fail_count": {}}

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        st = json.load(f)

    if not isinstance(st, dict):
        return {"seen": {}, "mall_cache": {}, "fail_count": {}}

    st.setdefault("seen", {})
    st.setdefault("mall_cache", {})
    st.setdefault("fail_count", {})
    return st


def save_state(state: Dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def make_requests_session() -> requests.Session:
    s = requests.session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Connection": "close",
        }
    )
    return s


# 전역 세션/스크레이퍼
_GLOBAL_SESS: requests.Session | None = None
_GLOBAL_SCRAPER = None


def get_global_sess() -> requests.Session:
    global _GLOBAL_SESS
    if _GLOBAL_SESS is None:
        _GLOBAL_SESS = make_requests_session()
    return _GLOBAL_SESS


def get_global_scraper():
    global _GLOBAL_SCRAPER
    if _GLOBAL_SCRAPER is None:
        _GLOBAL_SCRAPER = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "android", "desktop": False}
        )
    return _GLOBAL_SCRAPER


def recreate_global_scraper():
    global _GLOBAL_SCRAPER
    _GLOBAL_SCRAPER = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "android", "desktop": False}
    )
    return _GLOBAL_SCRAPER


def recreate_global_sess():
    global _GLOBAL_SESS
    try:
        if _GLOBAL_SESS is not None:
            _GLOBAL_SESS.close()
    except Exception:
        pass
    _GLOBAL_SESS = make_requests_session()
    return _GLOBAL_SESS


def http_get_text(url: str, use_cloudscraper: bool = False) -> str:
    try:
        if use_cloudscraper:
            sc = get_global_scraper()
            res = sc.get(url, timeout=20)
        else:
            sess = get_global_sess()
            res = sess.get(url, timeout=20)

        if "ppomppu.co.kr" in url:
            res.encoding = "euc-kr"
        else:
            res.encoding = res.apparent_encoding

        return res.text
    except Exception as e:
        log("WARN: http_get_text failed:", url, repr(e))
        return ""


def send_telegram_via_homeassistant(cfg: Dict, msg: str) -> bool:
    service_name = (cfg.get("telegram_ha_service") or "notify.telegram").strip()
    if not service_name:
        return False

    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        log("WARN: HA telegram integration requested but SUPERVISOR_TOKEN missing")
        return False

    if "." not in service_name:
        log("WARN: invalid HA telegram service name:", service_name)
        return False

    domain, svc = service_name.split(".", 1)
    url = f"http://supervisor/core/api/services/{domain}/{svc}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {"message": msg}

    chat_id = sanitize_telegram_chat_id(cfg.get("telegram_chat_id"))
    if chat_id:
        if service_name.startswith("telegram_") or service_name.startswith("telegram"):
            payload["chat_id"] = chat_id
        else:
            payload["target"] = [chat_id]

    title = (cfg.get("telegram_ha_title") or "Hotdeal Alarm").strip()
    if title:
        payload["title"] = title

    try:
        requests.post(url, headers=headers, json=payload, timeout=20).raise_for_status()
        return True
    except Exception as e:
        log("WARN: homeassistant telegram send failed:", repr(e))
        return False


def send_telegram(cfg: Dict, msg: str) -> bool:
    if not cfg.get("telegram_enable"):
        return False

    method = (cfg.get("telegram_send_method") or "direct").strip().lower()
    if method == "homeassistant":
        return send_telegram_via_homeassistant(cfg, msg)

    token = cfg.get("telegram_bot_token")
    chat_id = sanitize_telegram_chat_id(cfg.get("telegram_chat_id"))
    if not token or not chat_id:
        log("WARN: telegram disabled or invalid chat_id/token")
        return False
    try:
        payload = {"chat_id": chat_id, "text": msg[:4090] + "..." if len(msg) > 4096 else msg}
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=20,
        ).raise_for_status()
        return True
    except Exception as e:
        log("WARN: telegram send failed:", repr(e))
        return False


def send_discord(cfg: Dict, msg: str) -> bool:
    if not cfg.get("discord_enable"):
        return False
    webhook = cfg.get("discord_webhook_url")
    if not webhook:
        return False
    try:
        requests.post(webhook, json={"content": msg}, timeout=20).raise_for_status()
        return True
    except Exception as e:
        log("WARN: discord send failed:", repr(e))
        return False


def send_homeassistant_notify(cfg: Dict, msg: str) -> bool:
    if not cfg.get("ha_notify_enable"):
        return False

    service = (cfg.get("ha_notify_service") or "").strip()
    if not service.startswith("notify."):
        return False

    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        return False

    domain, svc = service.split(".", 1)
    url = f"http://supervisor/core/api/services/{domain}/{svc}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"message": msg}

    try:
        requests.post(url, headers=headers, json=payload, timeout=20).raise_for_status()
        return True
    except Exception as e:
        log("WARN: ha notify failed:", repr(e))
        return False


def send_default_ha_notify(msg: str) -> bool:
    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        return False

    url = "http://supervisor/core/api/services/notify/notify"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    try:
        requests.post(url, headers=headers, json={"message": msg}, timeout=20).raise_for_status()
        return True
    except Exception as e:
        log("WARN: fallback HA notify failed:", repr(e))
        return False


def send_push_notifications(cfg: Dict, msg: str) -> bool:
    routes = []

    if cfg.get("telegram_enable"):
        method = (cfg.get("telegram_send_method") or "direct").strip().lower()
        if method == "homeassistant":
            routes.append(("telegram_ha", lambda: send_telegram_via_homeassistant(cfg, msg)))
        else:
            routes.append(("telegram_direct", lambda: send_telegram(cfg, msg)))

    if cfg.get("discord_enable"):
        routes.append(("discord", lambda: send_discord(cfg, msg)))

    if cfg.get("ha_notify_enable"):
        routes.append(("ha_notify", lambda: send_homeassistant_notify(cfg, msg)))

    # 강제 fallback: 선택한 채널이 모두 실패해도 HA 기본 알림으로 푸시를 보낸다.
    if not routes:
        routes.append(("ha_default_notify", lambda: send_default_ha_notify(msg)))

    sent = False
    for name, route in routes:
        try:
            if route():
                sent = True
                break
        except Exception as e:
            log("WARN: notification route failed:", name, repr(e))

    if not sent:
        return send_default_ha_notify(msg)

    return True


def should_send(cfg: Dict, title: str):
    keywords = [
        normalize_match_text(k)
        for k in (cfg.get("hotdeal_alarm_keyword") or "").split(",")
        if normalize_match_text(k)
    ]
    send_all = bool(cfg.get("use_hotdeal_alarm"))

    normalized_title = normalize_match_text(title)

    send_kw = False
    send_kw_dist = False
    if cfg.get("use_hotdeal_keyword_alarm") and keywords:
        send_kw = any(k in normalized_title for k in keywords)
    if cfg.get("use_hotdeal_keyword_alarm_dist") and keywords:
        send_kw_dist = any(k in normalized_title for k in keywords)

    return send_all or send_kw, send_kw_dist


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    log("DEBUG: addon started, entering main loop")

    while True:
        cycle_start = time.time()
        log("DEBUG: cycle start")

        cfg = load_config()
        state = load_state()

        max_fail = int(cfg.get("max_send_fail_retries", 10) or 0)
        keep_factor = float(cfg.get("state_keep_factor", 1.5) or 1.5)
        keep_min = int(cfg.get("state_keep_min", 50) or 50)

        try:
            items = scrape_board_items(cfg)

            keep_keys: List[str] = []
            for it in items:
                site = it["site"]
                board = it["board"]
                raw_url = it["url"]
                full_url = raw_url if raw_url.startswith("http") else (get_url_prefix(site) + raw_url)
                keep_keys.append(f"{site}:{board}:{full_url}")

            trim_state_to_firstpage(state, keep_keys, keep_factor=keep_factor, keep_min=keep_min)
            save_state(state)
            log(
                "DEBUG: state sizes after trim:",
                {k: len(state.get(k, {})) for k in ("seen", "mall_cache", "fail_count")},
            )

            log("ITEMS scraped:", len(items))
            c = Counter((it.get("site"), it.get("board")) for it in items)
            log("ITEMS by site/board:", dict(c))

            for it in items:
                site = it["site"]
                board = it["board"]
                title = (it["title"] or "").strip()
                raw_url = it["url"]

                full_url = raw_url if raw_url.startswith("http") else (get_url_prefix(site) + raw_url)
                key = f"{site}:{board}:{full_url}"

                if state["seen"].get(key):
                    continue

                send_main, send_dist = should_send(cfg, title)
                wants_detail = bool(send_main or send_dist)

                mall_url = ""
                if wants_detail:
                    if key in state["mall_cache"]:
                        mall_url = state["mall_cache"].get(key, "")
                    else:
                        mall_url = scrape_mall_url(site, raw_url)
                        state["mall_cache"][key] = mall_url

                if not (send_main or send_dist):
                    continue

                msg = format_message(
                    cfg.get("alarm_message_template", "{title}\n{url}\n{mall_url}"),
                    title,
                    site,
                    board,
                    full_url,
                    mall_url,
                )

                sent_any = False

                if send_main:
                    log(
                        f"ALARM(main): {site_map.get(site, site)} / {board_map.get(board, board)} | {title} | {full_url} | mall={bool(mall_url)}"
                    )
                    sent_any = (send_push_notifications(cfg, msg) or sent_any)

                if send_dist:
                    log(
                        f"ALARM(dist): {site_map.get(site, site)} / {board_map.get(board, board)} | {title} | {full_url} | mall={bool(mall_url)}"
                    )
                    sent_any = (send_push_notifications(cfg, msg) or sent_any)

                if sent_any:
                    state["seen"][key] = time.time()
                    if key in state["fail_count"]:
                        del state["fail_count"][key]
                    save_state(state)
                else:
                    cur = int(state["fail_count"].get(key, 0)) + 1
                    state["fail_count"][key] = cur
                    if max_fail > 0 and cur >= max_fail:
                        state["seen"][key] = time.time()
                        del state["fail_count"][key]
                    save_state(state)

        except Exception as e:
            log("ERROR:", repr(e))
            log(traceback.format_exc())
            if "No file descriptors available" in repr(e):
                log("FATAL: No file descriptors available, exiting to trigger restart...")
                sys.exit(1)

        interval = int(cfg.get("interval_min", 1))
        sleep_s = max(60, interval * 60)
        elapsed = time.time() - cycle_start
        log(f"DEBUG: cycle end (elapsed={elapsed:.1f}s); sleeping {sleep_s}s")
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()
