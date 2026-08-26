import json
import os
import re
import time
import html
import traceback
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
    try:
        factor = float(keep_factor)
    except Exception:
        factor = 1.5

    try:
        km = int(keep_min)
    except Exception:
        km = 50

    base = len(keep_keys) if keep_keys else 0
    limit = max(km, int(math.ceil(base * max(1.0, factor))))

    seen = state.get("seen")
    if isinstance(seen, dict) and seen:
        items = []
        for k, v in seen.items():
            ts = v if isinstance(v, (int, float)) else 0
            items.append((k, ts))

        items.sort(key=lambda x: x[1], reverse=True)
        keep_seen = set(k for k, _ in items[:limit])

        for k in list(seen.keys()):
            if k not in keep_seen:
                del seen[k]

    keep = set(keep_keys) if keep_keys else set()
    for bucket in ("mall_cache", "fail_count"):
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

    # 1. ppomppu (뽐뿌)
    if cfg.get("use_site_ppomppu"):
        boards = ["ppomppu", "ppomppu4", "ppomppu8", "money"]
        ppomppu_regex = r'<a[^>]*href="(?P<url>view\.php\?id=[^"]*?no=\d+[^"]*)"[^>]*>(?P<title>[\s\S]*?)</a>'

        for board in boards:
            if not cfg.get(f"use_board_ppomppu_{board}"):
                continue

            url = f"https://www.ppomppu.co.kr/zboard/zboard.php?id={board}"
            text = safe_get_text(url)
            log(f"DEBUG: ppomppu ({board}) list html length:", len(text))
            if not text:
                continue

            raw_matches = list(re.finditer(ppomppu_regex, text, re.MULTILINE))
            seen_urls = set()
            board_items = []

            for m in raw_matches:
                u = html.unescape(m.group("url")).strip()
                t = clean_html_title(m.group("title"))

                if not t or len(t) < 2 or u in seen_urls:
                    continue
                seen_urls.add(u)

                board_items.append({
                    "site": "ppomppu",
                    "board": board,
                    "title": t,
                    "url": u,
                })

            log(f"DEBUG: ppomppu ({board}) regex matches:", len(board_items))

            # 최상단 1개(공지/인기글) 스킵 처리
            if board_items:
                out.extend(board_items[1:])

    # 2. clien (클리앙)
    if cfg.get("use_site_clien"):
        # jirum(알뜰구매)의 리스트/갤러리 레이아웃 및 allsell(사고팔고) 모두 지원
        clien_regex = r'<a[^>]*href="(?P<url>/service/(?:board|group)/[^"]+/\d+[^"]*)"[^>]*>(?P<title>[\s\S]*?)</a>'

        for board in ["allsell", "jirum"]:
            if not cfg.get(f"use_board_clien_{board}"):
                continue

            url = f"https://www.clien.net/service/group/{board}" if board == "allsell" else f"https://www.clien.net/service/board/{board}"
            text = safe_get_text(url)
            log(f"DEBUG: clien ({board}) list html length:", len(text))
            if not text:
                continue

            raw_matches = list(re.finditer(clien_regex, text, re.MULTILINE))
            seen_urls = set()
            board_items = []

            for m in raw_matches:
                u = m.group("url").strip()
                t = clean_html_title(m.group("title"))
                if not t or len(t) < 2 or u in seen_urls:
                    continue
                seen_urls.add(u)

                board_items.append({
                    "site": "clien",
                    "board": board,
                    "title": t,
                    "url": u,
                })

            log(f"DEBUG: clien ({board}) regex matches:", len(board_items))
            out.extend(board_items)

    # 3. ruriweb (루리웹)
    if cfg.get("use_site_ruriweb"):
        ruri_regex = r'<a[^>]*href="(?P<url>(?:https?://bbs\.ruliweb\.com)?/market/board/\d+/read/\d+[^"]*)"[^>]*>(?P<title>[\s\S]*?)</a>'

        for board in ["1020", "600004"]:
            if not cfg.get(f"use_board_ruriweb_{board}"):
                continue

            url = f"https://bbs.ruliweb.com/market/board/{board}"
            text = safe_get_text(url)
            log(f"DEBUG: ruriweb ({board}) list html length:", len(text))
            if not text:
                continue

            raw_matches = list(re.finditer(ruri_regex, text, re.MULTILINE))
            seen_urls = set()
            board_items = []

            for m in raw_matches:
                u = m.group("url").strip()
                t = clean_html_title(m.group("title"))
                if not t or len(t) < 2 or u in seen_urls:
                    continue
                seen_urls.add(u)

                board_items.append({
                    "site": "ruriweb",
                    "board": board,
                    "title": t,
                    "url": u,
                })

            log(f"DEBUG: ruriweb ({board}) regex matches:", len(board_items))
            out.extend(board_items)

    # 4. coolenjoy (쿨엔조이)
    if cfg.get("use_site_coolenjoy"):
        boards = ["jirum"]
        cool_regex = r'<a[^>]*href="(?P<url>(?:https?://coolenjoy\.net)?/bbs/jirum/\d+[^"]*|\./\d+[^"]*)"[^>]*>(?P<title>[\s\S]*?)</a>'

        for board in boards:
            if not cfg.get(f"use_board_coolenjoy_{board}"):
                continue

            url = f"https://coolenjoy.net/bbs/{board}"
            text = safe_get_text(url)
            log(f"DEBUG: coolenjoy ({board}) list html length:", len(text))
            if not text:
                continue

            raw_matches = list(re.finditer(cool_regex, text, re.MULTILINE))
            seen_urls = set()
            board_items = []

            for m in raw_matches:
                u = m.group("url").strip()
                if u.startswith("./"):
                    u = f"https://coolenjoy.net/bbs/jirum/{u[2:]}"
                elif u.startswith("/"):
                    u = "https://coolenjoy.net" + u

                t = clean_html_title(m.group("title"))
                if not t or len(t) < 2 or u in seen_urls:
                    continue
                seen_urls.add(u)

                board_items.append({
                    "site": "coolenjoy",
                    "board": board,
                    "title": t,
                    "url": u,
                })

            log(f"DEBUG: coolenjoy ({board}) regex matches:", len(board_items))
            out.extend(board_items)

    # 5. quasarzone (퀘이사존)
    if cfg.get("use_site_quasarzone"):
        board = "qb_saleinfo"
        if cfg.get("use_board_quasarzone_qb_saleinfo"):
            url = f"https://quasarzone.com/bbs/{board}"
            quasar_regex = r'<a[^>]*href="(?P<url>/bbs/qb_saleinfo/views/\d+)"[^>]*>[\s\S]*?<span[^>]*class="ellipsis-with-reply-cnt"[^>]*>(?P<title>[\s\S]*?)</span>'

            text = safe_cloud_get_text(url)
            log("DEBUG: quasarzone (qb_saleinfo) list html length (cloudscraper):", len(text))

            matches = []
            if text:
                try:
                    matches = list(re.finditer(quasar_regex, text, re.MULTILINE))
                except Exception as e:
                    log("WARN: quasarzone regex error:", repr(e))
                    matches = []

            log("DEBUG: quasarzone (qb_saleinfo) regex matches (cloudscraper):", len(matches))

            for m in matches:
                u = m.group("url")
                out.append({
                    "site": "quasarzone",
                    "board": board,
                    "title": clean_html_title(m.group("title")),
                    "url": "https://quasarzone.com" + u if u.startswith("/") else u,
                })

            if (not text) or (len(matches) == 0):
                log("DEBUG: quasarzone fallback to http_get_text(use_cloudscraper=True)")
                text2 = http_get_text(url, use_cloudscraper=True)
                log("DEBUG: quasarzone (qb_saleinfo) list html length (fallback):", len(text2))

                matches2 = []
                if text2:
                    try:
                        matches2 = list(re.finditer(quasar_regex, text2, re.MULTILINE))
                    except Exception as e:
                        log("WARN: quasarzone regex error (fallback):", repr(e))
                        matches2 = []

                log("DEBUG: quasarzone (qb_saleinfo) regex matches (fallback):", len(matches2))

                for m in matches2:
                    u = m.group("url")
                    out.append({
                        "site": "quasarzone",
                        "board": board,
                        "title": clean_html_title(m.group("title")),
                        "url": "https://quasarzone.com" + u if u.startswith("/") else u,
                    })

    return out


def scrape_mall_url(site: str, url: str) -> str:
    regex = None
    if site == "ppomppu":
        regex = r'class="[^"]*topTitle-link[^"]*"[^>]*href="(?P<mall_url>https?://[^"]+)"'
    elif site == "clien":
        regex = r'class="[^"]*outlink[^"]*"[^>]*href="(?P<mall_url>https?://[^"]+)"'
    elif site == "ruriweb":
        regex = r'class="[^"]*(?:source_url|url)[^"]*"[^>]*href="(?P<mall_url>https?://[^"]+)"'
    elif site == "coolenjoy":
        regex = r'alt="관련링크"[^>]*>[\s\S]*?<a[^>]*href="(?P<mall_url>https?://[^"]+)"'
    elif site == "quasarzone":
        regex = r'<th>\s*링크\s*</th>[\s\S]*?<td>[\s\S]*?<a[^>]*href="(?P<mall_url>https?://[^"]+)"'

    if not regex:
        return ""

    full = url if url.startswith("http") else (get_url_prefix(site) + url)
    text = http_get_text(full, use_cloudscraper=(site == "quasarzone"))
    if not text:
        return ""

    m = re.search(regex, text, re.MULTILINE)
    if not m:
        return ""

    return html.unescape(m.group("mall_url")).strip()


def format_message(template: str, title: str, site: str, board: str, url: str, mall_url: str) -> str:
    template = (template or "").replace("\\n", "\n")
    return (
        template.replace("{title}", title)
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
                    sent_any = (send_telegram(cfg, msg) or sent_any)
                    sent_any = (send_discord(cfg, msg) or sent_any)
                    sent_any = (send_homeassistant_notify(cfg, msg) or sent_any)

                if send_dist:
                    log(
                        f"ALARM(dist): {site_map.get(site, site)} / {board_map.get(board, board)} | {title} | {full_url} | mall={bool(mall_url)}"
                    )
                    sent_any = (send_telegram(cfg, msg) or sent_any)
                    sent_any = (send_discord(cfg, msg) or sent_any)
                    sent_any = (send_homeassistant_notify(cfg, msg) or sent_any)

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
