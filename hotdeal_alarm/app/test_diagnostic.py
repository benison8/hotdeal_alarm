#!/usr/bin/env python3
"""
진단 스크립트: 알림 기능의 각 단계를 테스트합니다.
"""
import json
import sys
import os
import time

# 현재 폴더의 main.py를 import
import main

def test_diagnostic():
    print("=" * 80)
    print("HOTDEAL ALARM DIAGNOSTIC TEST v2")
    print("=" * 80)

    # 1. Config 로드
    print("\n[1] Loading config...")
    try:
        cfg = main.load_config()
        print("✓ Config loaded from:", main.CONFIG_PATH)
        print(f"  - use_hotdeal_alarm: {cfg.get('use_hotdeal_alarm')} (모든 글 알림)")
        print(f"  - use_hotdeal_keyword_alarm: {cfg.get('use_hotdeal_keyword_alarm')} (키워드 알림 메인)")
        print(f"  - use_hotdeal_keyword_alarm_dist: {cfg.get('use_hotdeal_keyword_alarm_dist')} (키워드 알림 분산)")
        print(f"  - hotdeal_alarm_keyword: '{cfg.get('hotdeal_alarm_keyword')}'")
        print(f"\n  - Enabled Sites:")
        for site in ["ppomppu", "clien", "ruriweb", "quasarzone"]:
            if cfg.get(f"use_site_{site}"):
                boards = [b for b in ["ppomppu", "ppomppu4", "ppomppu8", "money", "allsell", "jirum", "1020", "600004", "qb_saleinfo"] 
                         if cfg.get(f"use_board_{site}_{b}")]
                print(f"    ✓ {site}: {boards}")
        print(f"\n  - Telegram: {cfg.get('telegram_enable')} (ID: {cfg.get('telegram_chat_id', '')[:10]}***" if cfg.get('telegram_chat_id') else "  - Telegram: False")
    except Exception as e:
        print(f"✗ Config error: {e}")
        import traceback
        traceback.print_exc()
        return

    # 2. 모든 사이트 수집 테스트
    print("\n[2] Testing all sites scraping (this may take 30-60 seconds)...")
    try:
        start = time.time()
        items = main.scrape_board_items(cfg)
        elapsed = time.time() - start
        print(f"✓ Scraping completed in {elapsed:.1f}s")
        print(f"  - Total items: {len(items)}")
        
        from collections import Counter
        c = Counter((it.get("site"), it.get("board")) for it in items)
        for (site, board), count in sorted(c.items()):
            print(f"    - {site}/{board}: {count} items")
        
        if len(items) == 0:
            print("  ⚠ WARNING: No items scraped from any site!")
            print("     Check if:")
            print("     1. All sites are enabled in config")
            print("     2. Network connection is working")
            print("     3. Each site parser is correct")
        else:
            print(f"\n  Sample items:")
            for idx, item in enumerate(items[:5]):
                print(f"    [{idx+1}] {item['site']}/{item['board']}: {item['title'][:50]}...")
    except Exception as e:
        print(f"✗ Scraping error: {e}")
        import traceback
        traceback.print_exc()
        return

    # 3. 키워드 매칭 테스트
    print("\n[3] Testing keyword matching...")
    keyword_str = cfg.get('hotdeal_alarm_keyword', '')
    keywords = [k.strip() for k in keyword_str.split(",") if k.strip()]
    
    if keywords:
        print(f"✓ Configured keywords: {keywords}")
        send_all = bool(cfg.get('use_hotdeal_alarm'))
        use_kw = bool(cfg.get('use_hotdeal_keyword_alarm'))
        
        if send_all:
            print("  → Policy: SEND ALL (use_hotdeal_alarm=true)")
        elif use_kw:
            print("  → Policy: SEND ONLY MATCHING (use_hotdeal_keyword_alarm=true)")
            
            # 실제 수집한 아이템으로 테스트
            if items:
                match_count = 0
                for item in items[:20]:
                    send_main, send_dist = main.should_send(cfg, item['title'])
                    if send_main:
                        match_count += 1
                        print(f"    ✓ MATCH: {item['title'][:60]}...")
                print(f"  → Matching items in first 20: {match_count}/{min(20, len(items))}")
                
                if match_count == 0:
                    print("  ⚠ WARNING: No items matched keywords!")
                    print("     First 3 titles for inspection:")
                    for item in items[:3]:
                        print(f"       - {item['title']}")
            else:
                print("  ⚠ No items to test (check [2] Scraping result)")
        else:
            print("  ⚠ WARNING: No keyword settings despite use_hotdeal_keyword_alarm=true")
    else:
        print("⚠ No keywords configured (empty or not set)")
        print(f"  → hotdeal_alarm_keyword = '{keyword_str}'")
        send_all = bool(cfg.get('use_hotdeal_alarm'))
        if not send_all:
            print("  ⚠ CRITICAL: No alarm policy active!")
            print("     Either:")
            print("     1. Enable use_hotdeal_alarm (send all items)")
            print("     2. Set keywords and enable use_hotdeal_keyword_alarm")

    # 4. 알림 전송 방법 테스트
    print("\n[4] Testing notification methods...")
    methods_enabled = []
    if cfg.get('telegram_enable'):
        token = cfg.get('telegram_bot_token')
        chat_id = cfg.get('telegram_chat_id')
        if token and chat_id:
            methods_enabled.append("Telegram ✓")
        else:
            print("  ⚠ Telegram enabled but missing token or chat_id")
    
    if cfg.get('discord_enable'):
        webhook = cfg.get('discord_webhook_url')
        if webhook:
            methods_enabled.append("Discord ✓")
        else:
            print("  ⚠ Discord enabled but webhook URL missing")
    
    if cfg.get('ha_notify_enable'):
        service = cfg.get('ha_notify_service', '').strip()
        if service.startswith("notify."):
            methods_enabled.append(f"HA Notify ({service}) ✓")
        else:
            print("  ⚠ HA Notify enabled but invalid service format")
    
    if methods_enabled:
        print(f"✓ Enabled notification methods: {', '.join(methods_enabled)}")
    else:
        print("✗ No notification methods enabled!")
        print("  Enable at least one of: Telegram, Discord, or HA Notify")

    # 5. 최종 진단
    print("\n" + "=" * 80)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 80)
    
    issues = []
    
    # 문제 1: 게시물 수집 안 됨
    if len(items) == 0:
        issues.append("❌ CRITICAL: No items scraped from any site")
        issues.append("   → Check site enabled status, network, and parsers")
    
    # 문제 2: 알림 정책 없음
    send_all = bool(cfg.get('use_hotdeal_alarm'))
    use_kw = bool(cfg.get('use_hotdeal_keyword_alarm'))
    if not send_all and not use_kw:
        issues.append("❌ CRITICAL: No alarm policy enabled")
        issues.append("   → Enable either use_hotdeal_alarm or use_hotdeal_keyword_alarm")
    
    # 문제 3: 키워드 기반이지만 키워드 없음
    if use_kw and not keywords:
        issues.append("❌ CRITICAL: Keyword alarm enabled but no keywords set")
        issues.append("   → Set hotdeal_alarm_keyword (e.g., 'GPU,CPU,SSD')")
    
    # 문제 4: 알림 방법 없음
    if not methods_enabled:
        issues.append("❌ CRITICAL: No notification methods configured")
        issues.append("   → Enable Telegram, Discord, or HA Notify")
    
    if issues:
        print("⚠ ISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✓ All settings look correct!")
        print("\nExpected behavior:")
        print("  - Items should be scraped every cycle")
        print("  - Matching items should trigger notifications")
        print("  - Notifications should arrive via configured methods")
        print("\nIf still no notifications:")
        print("  1. Check addon restart logs in Home Assistant")
        print("  2. Verify settings actually updated (cycle through config)")
        print("  3. Monitor addon logs for 1-2 minutes")
        print("  4. Check if items already in 'state.json' (seen cache)")

if __name__ == "__main__":
    test_diagnostic()
