#!/usr/bin/env python3
"""
진단 스크립트: 알림 기능의 각 단계를 테스트합니다.
"""
import json
import sys
import os

# 현재 폴더의 main.py를 import
import main

def test_diagnostic():
    print("=" * 60)
    print("HOTDEAL ALARM DIAGNOSTIC TEST")
    print("=" * 60)

    # 1. Config 로드
    print("\n[1] Loading config...")
    try:
        cfg = main.load_config()
        print("✓ Config loaded")
        print(f"  - use_site_quasarzone: {cfg.get('use_site_quasarzone')}")
        print(f"  - use_board_quasarzone_qb_saleinfo: {cfg.get('use_board_quasarzone_qb_saleinfo')}")
        print(f"  - use_hotdeal_alarm: {cfg.get('use_hotdeal_alarm')}")
        print(f"  - use_hotdeal_keyword_alarm: {cfg.get('use_hotdeal_keyword_alarm')}")
        print(f"  - hotdeal_alarm_keyword: {cfg.get('hotdeal_alarm_keyword')}")
        print(f"  - telegram_enable: {cfg.get('telegram_enable')}")
        print(f"  - telegram_chat_id: {cfg.get('telegram_chat_id', '')[:10]}***" if cfg.get('telegram_chat_id') else "  - telegram_chat_id: (empty)")
    except Exception as e:
        print(f"✗ Config error: {e}")
        return

    # 2. Quasarzone 수집 테스트
    print("\n[2] Testing Quasarzone scraping...")
    if cfg.get('use_site_quasarzone'):
        try:
            items = main.scrape_board_items({"use_site_quasarzone": True, "use_board_quasarzone_qb_saleinfo": cfg.get("use_board_quasarzone_qb_saleinfo")})
            quasarzone_items = [it for it in items if it.get("site") == "quasarzone"]
            print(f"✓ Quasarzone scraped: {len(quasarzone_items)} items")
            if quasarzone_items:
                for idx, item in enumerate(quasarzone_items[:3]):
                    print(f"  [{idx+1}] {item['title'][:50]}...")
                    print(f"      URL: {item['url']}")
            else:
                print("  ⚠ No items found (Quasarzone may have changed structure)")
        except Exception as e:
            print(f"✗ Quasarzone scrape error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("⚠ Quasarzone is disabled in config")

    # 3. 키워드 매칭 테스트
    print("\n[3] Testing keyword matching...")
    keyword_str = cfg.get('hotdeal_alarm_keyword', '')
    if keyword_str:
        keywords = [k.strip() for k in keyword_str.split(",") if k.strip()]
        print(f"✓ Keywords: {keywords}")
        
        # 테스트 제목들
        test_titles = [
            "AMD 라이젠 5950X 할인",
            "LG 모니터 49인치 특가",
            "CPU 벌크 판매",
        ]
        
        for title in test_titles:
            send_main, send_dist = main.should_send(cfg, title)
            match_result = "✓ MATCH" if send_main else "✗ NO MATCH"
            print(f"  {match_result}: {title}")
    else:
        print("⚠ No keywords configured")

    # 4. Telegram 연결 테스트
    print("\n[4] Testing Telegram connectivity...")
    if cfg.get('telegram_enable'):
        token = cfg.get('telegram_bot_token')
        chat_id = cfg.get('telegram_chat_id')
        if token and chat_id:
            print(f"✓ Telegram configured (token={token[:10]}..., chat_id={chat_id})")
            # 실제 전송 테스트는 하지 않음 (메시지 전송 비용 때문에)
            print("  (Skipping actual message send test)")
        else:
            print("⚠ Telegram token or chat_id is missing")
    else:
        print("⚠ Telegram is disabled in config")

    # 5. 알림 정책 분석
    print("\n[5] Analyzing alarm policy...")
    send_all = bool(cfg.get('use_hotdeal_alarm'))
    use_kw = bool(cfg.get('use_hotdeal_keyword_alarm'))
    use_kw_dist = bool(cfg.get('use_hotdeal_keyword_alarm_dist'))
    
    if send_all:
        print("✓ All items will be sent (use_hotdeal_alarm=true)")
    elif use_kw or use_kw_dist:
        print("✓ Only keyword-matching items will be sent")
    else:
        print("✗ No alarm policy active - no items will be sent")

    print("\n" + "=" * 60)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 60)
    
    issues = []
    if not cfg.get('use_site_quasarzone'):
        issues.append("❌ Quasarzone is disabled")
    if not cfg.get('telegram_enable'):
        issues.append("❌ Telegram is disabled")
    if not send_all and not use_kw and not use_kw_dist:
        issues.append("❌ No alarm policy is active")
    if use_kw and not keyword_str:
        issues.append("❌ Keyword alarm is on but no keywords are set")
    
    if issues:
        print("ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✓ All settings look correct")
        print("  If alarms still aren't working:")
        print("  1. Check the logs in Home Assistant")
        print("  2. Verify Quasarzone is actually scraping posts")
        print("  3. Test Telegram API directly with your token/chat_id")

if __name__ == "__main__":
    test_diagnostic()
