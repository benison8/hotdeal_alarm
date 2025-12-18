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
  if use_cloudscraper:
    sc = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "android", "desktop": False})
    return sc.get(url, timeout=20).text
  return requests.get(url, timeout=20).text

def scrape_board_items(cfg: Dict) -> List[Dict]:
  out = []
  sess = requests.session()
  scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "android", "desktop": False})

  # ppomppu
  if cfg.get("use_site_ppomppu"):
    boards = ["ppomppu", "ppomppu4", "ppomppu8", "money"]
    regex = r'title[\"\'] href=\"(?P<url>view\.php.+?)\"\s*>.+>(?P<title>.+?)<'
    for board in boards:
      if not cfg.get(f"use_board_ppomppu_{board}"):
        continue
      text = scraper.get(f"https://www.ppomppu.co.kr/zboard/zboard.php?id={board}", timeout=20).text
      for m in re.finditer(regex, text, re.MULTILINE):
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
        # 원본 regex가 일부 잘려 보이므로, 안정적으로 title/url를 잡는 보수적 패턴으로 대체
        regex = r'href=\"(?P<url>/service/board/jirum/\d+)[^\"]*\"[^>]*>[^<]*<span[^>]*class=\"subject_fixed\"[^>]*>(?P<title>[^<]+)</span>'
        url = f"https://www.clien.net/service/board/{board}"
      text = sess.get(url, timeout=20).text
      for m in re.finditer(regex, text, re.MULTILINE):
        out.append({"site": "clien", "board": board, "title": m.group("title"), "url": m.group("url")})

  # ruriweb (원본 regex가 일부 잘려 보이므로 보수적 패턴)
  if cfg.get("use_site_ruriweb"):
    for board in ["1020", "600004"]:
      if not cfg.get(f"use_board_ruriweb_{board}"):
        continue
      url = f"https://bbs.ruliweb.com/market/board/{board}"
      text = sess.get(url, timeout=20).text
      regex = r'href=\"(?P<url>/market/board/\d+/read/\d+)[^\"]*\"[^>]*>(?P<title>[^<]+)</a>'
      for m in re.finditer(regex, text, re.MULTILINE):
        out.append({"site": "ruriweb", "board": board, "title": m.group("title"), "url": m.group("url")})

  # quasarzone
  if cfg.get("use_site_quasarzone"):
    board = "qb_saleinfo"
    if cfg.get("use_board_quasarzone_qb_saleinfo"):
      url = f"https://quasarzone.com/bbs/{board}"
      text = scraper.get(url, timeout=20).text
      regex = r'href=\"(?P<url>/bbs/qb_saleinfo/views/\d+)\"[^>]*>(?P<title>[^<]+)</a>'
      for m in re.finditer(regex, text, re.MULTILINE):
        u = m.group("url")
        out.append({"site": "quasarzone", "board": board, "title": m.group("title"), "url": "https://quasarzone.com" + u if u.startswith("/") else u})

  return out

def scrape_mall_url(site: str, url: str) -> str:
  # 원본의 상세페이지 정규식 아이디어 유지 [file:64]
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
  requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg},
                timeout=20).raise_for_status()

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

    # "notify.mobile_app_xxx" -> domain="notify", service="mobile_app_xxx"
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
        # 알림 실패가 크롤링을 막지 않게 조용히 무시(필요하면 로그로 변경)
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
          continue

        # mall_url 캐시/추출
        mall_url = state["mall_cache"].get(key, "")
        if not mall_url:
          mall_url = scrape_mall_url(site, raw_url)
          if mall_url:
            state["mall_cache"][key] = mall_url

        send_main, send_dist = should_send(cfg, title)
        if send_main:
          msg = format_message(cfg.get("alarm_message_template","{title}\n{url}\n{mall_url}"),
                               title, site, board, full_url, mall_url)
          send_telegram(cfg, msg)
          send_discord(cfg, msg)
          send_homeassistant_notify(cfg, msg)

        if send_dist:
          msg = format_message(cfg.get("alarm_message_template","{title}\n{url}\n{mall_url}"),
                               title, site, board, full_url, mall_url)
          # dist 채널을 따로 두고 싶으면 config를 분리하면 됨(원본은 message_id를 다르게 사용) [file:64]
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
