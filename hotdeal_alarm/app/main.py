import json, os, re, time, html, traceback
from typing import Dict, List

import requests
import cloudscraper


DATA_DIR = "/data"
STATE_FILE = os.path.join(DATA_DIR, "state.json")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/data/options.json")


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
    return ""


def load_config() -> Dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state() -> Dict:
    if not os.path.exists(STATE_FILE):
        return {"seen": {}, "mall_cache": {}}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: Dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_FILE)


def http_get_text(url: str, use_cloudscraper: bool = False) -> str:
    # 상세 페이지는 요청 빈도가 높지 않으므로 단순 구현 유지
    if use_cloudscraper:
        sc = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "android", "desktop": False})
        return sc.get(url, timeout=20).text
    return requests.get(url, timeout=20).text


def scrape_board_items(cfg: Dict) -> List[Dict]:
    out = []

    def make_session():
        s = requests.session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
            "Connection": "close",
        })
        return s

    sess = make_session()

    def safe_get_text(url: str) -> str:
        nonlocal sess
        try:
            return sess.get(url, timeout=20).text
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, OSError) as e:
            # FD 고갈(Errno 24) / SSL / 연결 끊김 등일 때 세션 재생성 후 1회 재시도
            print("WARN: recreate session due to:", repr(e))
            try:
                sess.close()
            except Exception:
                pass

            # 잠깐 쉬었다가 재시도(폭주 완화)
            time.sleep(1)

            sess = make_session()
            try:
                return sess.get(url, timeout=20).text
            except Exception as e2:
                print("WARN: retry failed:", repr(e2))
                return ""

    scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "android", "desktop": False})

    # ppomppu
    if cfg.get("use_site_ppomppu"):
        boards = ["ppomppu", "ppomppu4", "ppomppu8", "money"]
        ppomppu_regex = r'title[\"\'] href=\"(?P<url>view\.php.+?)\"\s*>.+>(?P<title>.+?)<'
        for board in boards:
            if not cfg.get(f"use_board_ppomppu_{board}"):
                continue

            url = f"https://www.ppomppu.co.kr/zboard/zboard.php?id={board}"
            text = safe_get_text(url)
            print("PPOMPPU URL:", url)
            print("PPOMPPU HTML length:", len(text))
            print("PPOMPPU matches:", len(re.findall(ppomppu_regex, text, re.MULTILINE)))

            if not text:
                continue

            for m in re.finditer(ppomppu_regex, text, re.MULTILINE):
                out.append({"site": "ppomppu", "board": board, "title": m.group("title"), "url": m.group("url")})

    # clien
    if cfg.get("use_site_clien"):
        for board in ["allsell", "jirum"]:
            if not cfg.get(f"use_board_clien_{board}"):
                continue

            if board == "allsell":
                clien_regex = r'class=\"list_subject\" href=\"(?P<url>.+?)\" .+\s+.+\s+.+?data-role=\"list-title-text\"\stitle=\"(?P<title>.+?)\"'
                url = f"https://www.clien.net/service/group/{board}"
            else:
                # 안정적인 보수적 패턴
                clien_regex = r'href=\"(?P<url>/service/board/jirum/\d+)[^\"]*\"[^>]*>[^<]*<span[^>]*class=\"subject_fixed\"[^>]*>(?P<title>[^<]+)</span>'
                url = f"https://www.clien.net/service/board/{board}"

            text = safe_get_text(url)
            print("CLIEN URL:", url)
            print("CLIEN HTML length:", len(text))
            print("CLIEN matches:", len(re.findall(clien_regex, text, re.MULTILINE)))

            if not text:
                continue

            for m in re.finditer(clien_regex, text, re.MULTILINE):
                out.append({"site": "clien", "board": board, "title": m.group("title"), "url": m.group("url")})

    # ruriweb
    if cfg.get("use_site_ruriweb"):
        for board in ["1020", "600004"]:
            if not cfg.get(f"use_board_ruriweb_{board}"):
                continue

            url = f"https://bbs.ruliweb.com/market/board/{board}"
            ruriweb_regex = r'href=\"(?P<url>/market/board/\d+/read/\d+)[^\"]*\"[^>]*>(?P<title>[^<]+)</a>'

            text = safe_get_text(url)
            print("RURIWEB URL:", url)
            print("RURIWEB HTML length:", len(text))
            print("RURIWEB matches:", len(re.findall(ruriweb_regex, text, re.MULTILINE)))

            if not text:
                continue

            for m in re.finditer(ruriweb_regex, text, re.MULTILINE):
                out.append({"site": "ruriweb", "board": board, "title": m.group("title"), "url": m.group("url")})

    # quasarzone
    if cfg.get("use_site_quasarzone"):
        board = "qb_saleinfo"
        if cfg.get("use_board_quasarzone_qb_saleinfo"):
            url = f"https://quasarzone.com/bbs/{board}"
            quasar_regex = r'href=\"(?P<url>/bbs/qb_saleinfo/views/\d+)\"[^>]*>(?P<title>[^<]+)</a>'

            # quasarzone는 cloudscraper 유지
            try:
                text = scraper.get(url, timeout=20).text
            except Exception as e:
                print("WARN: quasarzone fetch failed:", repr(e))
                text = ""

            print("QUASARZONE URL:", url)
            print("QUASARZONE HTML length:", len(text))
            print("QUASARZONE matches:", len(re.findall(quasar_regex, text, re.MULTILINE)))

            if not text:
                return out

            for m in re.finditer(quasar_regex, text, re.MULTILINE):
                u = m.group("url")
                out.append({
                    "site": "quasarzone",
                    "board": board,
                    "title": m.group("title"),
                    "url": "https://quasarzone.com" + u if u.startswith("/") else u
                })

    return out


def scrape_mall_url(site: str, url: str) -> str:
    regex = None
    if site == "ppomppu":
        regex = r'div class=wordfix>링크:\s+(?P<mall_url>[^<]+)'
    elif site == "clien":
        regex = r'구매링크.+?>(?P<mall_url>[^<]+)<'
    elif site == "ruriweb":
        regex = r'원본출처.+?(?P<mall_url>https?://[^\s\"<]+)'
    elif site == "coolenjoy":
        regex = r'alt=\"관련링크\">\s+(?P<mall_url>[^<]+)<'
    elif site == "quasarzone":
        regex = r'링크\s+(?P<mall_url>https?://[^\s\"<]+)'

    if not regex:
        return ""

    full = url if url.startswith("http") else (get_url_prefix(site) + url)
    text = http_get_text(full, use_cloudscraper=(site == "quasarzone"))
    m = re.search(regex, text, re.MULTILINE)
    if not m:
        return ""
    return html.unescape(m.group("mall_url")).strip()


def format_message(template: str, title: str, site: str, board: str, url: str, mall_url: str) -> str:
    return (template
        .replace("{title}", title)
        .replace("{site}", site_map.get(site, site))
        .replace("{board}", board_map.get(board, board))
        .replace("{url}", url)
        .replace("{mall_url}", mall_url or "")
    )


def send_telegram(cfg: Dict, msg: str):
    if not cfg.get("telegram_enable"):
        return
    token = cfg.get("telegram_bot_token")
    chat_id = cfg.get("telegram_chat_id")
    if not token or not chat_id:
        return
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg},
        timeout=20
    ).raise_for_status()


def send_discord(cfg: Dict, msg: str):
    if not cfg.get("discord_enable"):
        return
    webhook = cfg.get("discord_webhook_url")
    if not webhook:
        return
    requests.post(webhook, json={"content": msg}, timeout=20).raise_for_status()


def send_homeassistant_notify(cfg: Dict, msg: str):
    if not cfg.get("ha_notify_enable"):
        return

    service = (cfg.get("ha_notify_service") or "").strip()
    if not service.startswith("notify."):
        return

    token = os.getenv("SUPERVISOR_TOKEN")
    if not token:
        return

    domain, svc = service.split(".", 1)

    url = f"http://supervisor/core/api/services/{domain}/{svc}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"message": msg}

    try:
        requests.post(url, headers=headers, json=payload, timeout=20).raise_for_status()
    except Exception:
        return


def should_send(cfg: Dict, title: str):
    keywords = [k.strip() for k in (cfg.get("hotdeal_alarm_keyword") or "").split(",") if k.strip()]
    send_all = bool(cfg.get("use_hotdeal_alarm"))
    send_kw = False
    send_kw_dist = False
    if cfg.get("use_hotdeal_keyword_alarm") and keywords:
        send_kw = any(k.lower() in title.lower() for k in keywords)
    if cfg.get("use_hotdeal_keyword_alarm_dist") and keywords:
        send_kw_dist = any(k.lower() in title.lower() for k in keywords)
    return send_all or send_kw, send_kw_dist


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    while True:
        cfg = load_config()
        state = load_state()

        try:
            items = scrape_board_items(cfg)
            for it in items:
                site = it["site"]
                board = it["board"]
                title = (it["title"] or "").strip()
                raw_url = it["url"]

                full_url = raw_url if raw_url.startswith("http") else (get_url_prefix(site) + raw_url)
                key = f"{site}:{board}:{full_url}"

                if state["seen"].get(key):
                    # 너무 시끄러우면 주석 처리 가능
                    # print(f"SKIP(seen): {site}/{board} | {title} | {full_url}")
                    continue

                # mall_url 캐시/추출
                mall_url = state["mall_cache"].get(key, "")
                if not mall_url:
                    mall_url = scrape_mall_url(site, raw_url)
                    if mall_url:
                        state["mall_cache"][key] = mall_url

                send_main, send_dist = should_send(cfg, title)

                if send_main:
                    msg = format_message(
                        cfg.get("alarm_message_template", "{title}\n{url}\n{mall_url}"),
                        title, site, board, full_url, mall_url
                    )
                    print(f"ALARM(main): {site_map.get(site, site)} / {board_map.get(board, board)} | {title} | {full_url} | mall={bool(mall_url)}")
                    send_telegram(cfg, msg)
                    send_discord(cfg, msg)
                    send_homeassistant_notify(cfg, msg)

                if send_dist:
                    msg = format_message(
                        cfg.get("alarm_message_template", "{title}\n{url}\n{mall_url}"),
                        title, site, board, full_url, mall_url
                    )
                    print(f"ALARM(dist): {site_map.get(site, site)} / {board_map.get(board, board)} | {title} | {full_url} | mall={bool(mall_url)}")
                    send_telegram(cfg, msg)
                    send_discord(cfg, msg)
                    send_homeassistant_notify(cfg, msg)

                state["seen"][key] = True
                save_state(state)

        except Exception as e:
            print("ERROR:", e)
            print(traceback.format_exc())

        interval = int(cfg.get("interval_min", 1))
        time.sleep(max(60, interval * 60))


if __name__ == "__main__":
    main()
