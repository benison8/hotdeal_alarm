import json, os, re, time, html, traceback
import sys
import math
from typing import Dict, List
from collections import Counter
from datetime import datetime

import requests
import cloudscraper


DATA_DIR = "/data"
STATE_FILE = os.path.join(DATA_DIR, "state.json")
CONFIG_PATH = os.getenv("CONFIG_PATH", "/data/options.json")


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
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
        "Connection": "close",
    })
    return s


# 전역 세션/스크레이퍼(매 사이클 생성 금지)
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
            return sc.get(url, timeout=20).text

        sess = get_global_sess()
        return sess.get(url, timeout=20).text

    except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, OSError) as e:
        log("WARN: http_get_text session error:", url, "err=", repr(e))
        time.sleep(1)
        try:
            sess = recreate_global_sess()
            return sess.get(url, timeout=20).text
        except Exception as e2:
            log("WARN: http_get_text retry failed:", url, "err=", repr(e2))
            return ""

    except Exception as e:
        log("WARN: http_get_text failed:", url, "err=", repr(e))
        if use_cloudscraper:
            time.sleep(1)
            try:
                sc = recreate_global_scraper()
                return sc.get(url, timeout=20).text
            except Exception as e2:
                log("WARN: http_get_text cloudscraper retry failed:", url, "err=", repr(e2))
                return ""
        return ""


def trim_state_to_firstpage(state: Dict, keep_keys: List[str], keep_factor: float, keep_min: int):
    if not keep_keys:
        return

    try:
        factor = float(keep_factor)
    except Exception:
        factor = 1.5

    try:
        km = int(keep_min)
    except Exception:
        km = 50

    limit = max(km, int(math.ceil(len(keep_keys) * max(1.0, factor))))

    recent = []
    seen_set = set()
    for k in keep_keys:
        if k in seen_set:
            continue
        recent.append(k)
        seen_set.add(k)
        if len(recent) >= limit:
            break

    keep = set(recent)

    for bucket in ("seen", "mall_cache", "fail_count"):
        d = state.get(bucket)
        if not isinstance(d, dict) or not d:
            continue
        for k in list(d.keys()):
            if k not in keep:
                del d[k]


def scrape_board_items(cfg: Dict) -> List[Dict]:
    out: List[Dict] = []

    def safe_get_text(url: str) -> str:
        return http_get_text(url, use_cloudscraper=False) or ""

    def safe_cloud_get_text(url: str) -> str:
        return http_get_text(url, use_cloudscraper=True) or ""

    # ppomppu (최상단 1개 스킵)
    if cfg.get("use_site_ppomppu"):
        boards = ["ppomppu", "ppomppu4", "ppomppu8", "money"]
        ppomppu_regex = r'title[\"\'] href=\"(?P<url>view\.php.+?)\"\s*>.+>(?P<title>.+)</span></a>'
        for board in boards:
            if not cfg.get(f"use_board_ppomppu_{board}"):
                continue

            url = f"https://www.ppomppu.co.kr/zboard/zboard.php?id={board}"
            text = safe_get_text(url)
            if not text:
                continue

            skip_first = True
            for m in re.finditer(ppomppu_regex, text, re.MULTILINE):
                if skip_first:
                    skip_first = False
                    continue
                out.append({"site": "ppomppu", "board": board, "title": m.group("title"), "url": m.group("url")})

    # clien
    if cfg.get("use_site_clien"):
        for board in ["allsell", "jirum"]:
            if not cfg.get(f"use_board_clien_{board}"):
                continue
            if board == "allsell":
                regex = r'class=\"list_subject\" href=\"(?P<url>.+?)\" .+\s+.+\s+.+?data-role=\"list-title-text\"\stitle=\"(?P<title>.+?)\"'
                url = f"https://www.clien.net/service/group/{board}"
            else:
                regex = r'href=\"(?P<url>/service/board/jirum/\d+)[^\"]*\"[^>]*>[^<]*<span[^>]*class=\"subject_fixed\"[^>]*>(?P<title>[^<]+)</span>'
                url = f"https://www.clien.net/service/board/{board}"

            text = safe_get_text(url)
            if not text:
                continue
            for m in re.finditer(regex, text, re.MULTILINE):
                out.append({"site": "clien", "board": board, "title": m.group("title"), "url": m.group("url")})

    # ruriweb
    if cfg.get("use_site_ruriweb"):
        for board in ["1020", "600004"]:
            if not cfg.get(f"use_board_ruriweb_{board}"):
                continue
            url = f"https://bbs.ruliweb.com/market/board/{board}"
            text = safe_get_text(url)
            if not text:
                continue
            regex = r'href=\"(?P<url>/market/board/\d+/read/\d+)[^\"]*\"[^>]*>(?P<title>[^<]+)</a>'
            for m in re.finditer(regex, text, re.MULTILINE):
                out.append({"site": "ruriweb", "board": board, "title": m.group("title"), "url": m.group("url")})

    # coolenjoy
    if cfg.get("use_site_coolenjoy"):
        boards = ["jirum"]
        for board in boards:
            if not cfg.get(f"use_board_coolenjoy_{board}"):
                continue
            regex = r'<td class=\"td_subject\">\s+<a href=\"(?P<url>.+)\">\s+(?:<font color=.+?>)?(?P<title>.+?)(?:</font>)?\s+<span class=\"sound_only\"'
            url = f"https://coolenjoy.net/bbs/{board}"
            text = safe_get_text(url)
            if not text:
                continue
            for m in re.finditer(regex, text, re.MULTILINE):
                u = m.group("url")
                out.append({
                    "site": "coolenjoy",
                    "board": board,
                    "title": m.group("title"),
                    "url": "https://coolenjoy.net" + u if u.startswith("/") else u
                })

    # quasarzone
    if cfg.get("use_site_quasarzone"):
        board = "qb_saleinfo"
        if cfg.get("use_board_quasarzone_qb_saleinfo"):
            url = f"https://quasarzone.com/bbs/{board}"
            quasar_regex = r'<p class=\"tit\">\s+<a href=\"(?P<url>.+)\"\s+class=.+>\s+.+\s+(?:<span class=\"ellipsis-with-reply-cnt\">)?(?P<title>.+?)(?:</span>)'

            text = safe_cloud_get_text(url)
            log("DEBUG: quasarzone list html length (cloudscraper):", len(text))

            matches = []
            if text:
                try:
                    matches = list(re.finditer(quasar_regex, text, re.MULTILINE))
                except Exception as e:
                    log("WARN: quasarzone regex error:", repr(e))
                    matches = []

            log("DEBUG: quasarzone regex matches (cloudscraper):", len(matches))

            for m in matches:
                u = m.group("url")
                out.append({
                    "site": "quasarzone",
                    "board": board,
                    "title": m.group("title"),
                    "url": "https://quasarzone.com" + u if u.startswith("/") else u
                })

            if (not text) or (len(matches) == 0):
                log("DEBUG: quasarzone fallback to http_get_text(use_cloudscraper=True)")
                text2 = http_get_text(url, use_cloudscraper=True)
                log("DEBUG: quasarzone list html length (fallback):", len(text2))

                matches2 = []
                if text2:
                    try:
                        matches2 = list(re.finditer(quasar_regex, text2, re.MULTILINE))
                    except Exception as e:
                        log("WARN: quasarzone regex error (fallback):", repr(e))
                        matches2 = []

                log("DEBUG: quasarzone regex matches (fallback):", len(matches2))

                for m in matches2:
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
         regex = r"<li class=['\"]topTitle-link(?:\s+partner)?['\"]>.*?<a href=['\"](?P<mall_url>https?://[^'\"]+)['\"]"
    elif site == "clien":
        regex = r'구매링크.+?>(?P<mall_url>[^<]+)<'
    elif site == "ruriweb":
        regex = r'원본출처.+?(?P<mall_url>https?://[^\s\"<]+)'
    elif site == "coolenjoy":
        regex = r'alt=\"관련링크\">\s+(?P<mall_url>[^<]+)<'
    elif site == "quasarzone":
        regex = r'<th>\s*링크.+?</th>\s*<td>\s*<a[^>]*>(?P<mall_url>https?://[^<\s]+)</a>'
    if not regex:
        return ""


    full = url if url.startswith("http") else (get_url_prefix(site) + url)
    text = http_get_text(full, use_cloudscraper=(site == "quasarzone"))
    if not text:
        return ""

    m = re.search(regex, text, re.MULTILINE | re.DOTALL)
    if not m:
        return ""

    return html.unescape(m.group("mall_url")).strip()



def format_message(template: str, title: str, site: str, board: str, url: str, mall_url: str) -> str:
    template = (template or "").replace("\\n", "\n")
    return (template
        .replace("{title}", title)
        .replace("{site}", site_map.get(site, site))
        .replace("{board}", board_map.get(board, board))
        .replace("{url}", url)
        .replace("{mall_url}", mall_url or "")
    )


def send_telegram(cfg: Dict, msg: str) -> bool:
    if not cfg.get("telegram_enable"):
        return False
    token = cfg.get("telegram_bot_token")
    chat_id = cfg.get("telegram_chat_id")
    if not token or not chat_id:
        return False
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": msg},
            timeout=20
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
            log("DEBUG: state sizes after trim:", {k: len(state.get(k, {})) for k in ("seen", "mall_cache", "fail_count")})

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
                    mall_url = state["mall_cache"].get(key, "")
                    if not mall_url:
                        mall_url = scrape_mall_url(site, raw_url)
                        if mall_url:
                            state["mall_cache"][key] = mall_url

                if not (send_main or send_dist):
                    continue

                msg = format_message(
                    cfg.get("alarm_message_template", "{title}\n{url}\n{mall_url}"),
                    title, site, board, full_url, mall_url
                )

                sent_any = False

                if send_main:
                    log(f"ALARM(main): {site_map.get(site, site)} / {board_map.get(board, board)} | {title} | {full_url} | mall={bool(mall_url)}")
                    sent_any = (send_telegram(cfg, msg) or sent_any)
                    sent_any = (send_discord(cfg, msg) or sent_any)
                    sent_any = (send_homeassistant_notify(cfg, msg) or sent_any)

                if send_dist:
                    log(f"ALARM(dist): {site_map.get(site, site)} / {board_map.get(board, board)} | {title} | {full_url} | mall={bool(mall_url)}")
                    sent_any = (send_telegram(cfg, msg) or sent_any)
                    sent_any = (send_discord(cfg, msg) or sent_any)
                    sent_any = (send_homeassistant_notify(cfg, msg) or sent_any)

                if sent_any:
                    state["seen"][key] = True
                    if key in state["fail_count"]:
                        del state["fail_count"][key]
                    save_state(state)
                else:
                    cur = int(state["fail_count"].get(key, 0)) + 1
                    state["fail_count"][key] = cur

                    if max_fail > 0 and cur >= max_fail:
                        log(f"WARN: send failed {cur} times; give up and mark seen: {key}")
                        state["seen"][key] = True
                        del state["fail_count"][key]
                    else:
                        log(f"WARN: no channel succeeded; will retry next cycle ({cur}/{max_fail or '∞'}): {key}")

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
