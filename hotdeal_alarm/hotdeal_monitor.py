import requests
from bs4 import BeautifulSoup
import time
import argparse
import json
import os # 환경 변수를 위해 추가

# --- Home Assistant API 호출 함수 ---
def send_ha_notification(title, message):
    """Home Assistant 알림 서비스 호출"""
    # 애드온 환경 변수에서 HA 접속 정보 가져오기
    HA_URL = os.environ.get('SUPERVISOR_HOST', 'http://supervisor') 
    HA_TOKEN = os.environ.get('SUPERVISOR_TOKEN') 
    
    # Home Assistant 알림 서비스 엔드포인트
    NOTIFICATION_URL = f"{HA_URL}/core/api/services/notify/mobile_app_your_device" 
    # 'mobile_app_your_device'는 사용자의 실제 알림 서비스 이름으로 변경해야 합니다!
    
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "title": title,
        "message": message,
        "data": {
            "tag": "hotdeal-alarm", # 알림 그룹화 태그
        }
    }
    
    try:
        response = requests.post(NOTIFICATION_URL, headers=headers, data=json.dumps(payload), verify=False)
        response.raise_for_status()
        print(f"Notification sent successfully: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Error sending HA notification: {e}")

# --- 기존 스크립트 로직 수정 ---
def get_hotdeal_list(url):
    """주어진 URL에서 핫딜 리스트를 스크래핑하고 파싱합니다."""
    # (기존 스크립트의 requests 및 BeautifulSoup 로직 이식)
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 핫딜 리스트를 파싱하는 로직을 여기에 구현
        # 예: deal_list = [{'title': '딜 제목', 'url': '딜 URL', 'unique_id': '...'}]
        # 실제 파싱 코드는 사용자님의 깃허브 스크립트 내용을 기반으로 완성해야 합니다.
        
        # 임시 데이터 반환 (실제 스크립트 로직으로 대체 필요)
        return [{'title': '임시 핫딜: 새 키보드', 'url': 'http://testurl.com/keyb', 'unique_id': 'keyb_123'}]

    except Exception as e:
        print(f"Scraping error: {e}")
        return []

def monitor_hotdeals(url, interval_minutes):
    """핫딜을 주기적으로 모니터링하고 새 딜이 발견되면 알림을 보냅니다."""
    interval_seconds = interval_minutes * 60
    
    # 이미 알림을 보낸 딜의 ID를 저장할 집합
    known_deals = set() 
    
    while True:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Checking hotdeals at {url}...")
        
        current_deals = get_hotdeal_list(url)
        
        for deal in current_deals:
            deal_id = deal.get('unique_id') # 스크래핑 시 딜을 유일하게 식별할 수 있는 ID (필수)
            
            if deal_id and deal_id not in known_deals:
                print(f"-> NEW HOTDEAL found: {deal['title']}")
                # Home Assistant로 알림 보내기
                send_ha_notification(
                    title="🔥 새 핫딜 알림", 
                    message=f"{deal['title']} - 자세히 보기: {deal['url']}"
                )
                known_deals.add(deal_id)
            elif deal_id:
                known_deals.add(deal_id) # 이미 알려진 딜도 다시 추가 (리스트 변경 대비)
        
        # 딜이 너무 많아 메모리 문제가 생기지 않도록 set 크기 제한 (옵션)
        if len(known_deals) > 500:
            known_deals = set(list(known_deals)[-250:])
            
        print(f"Waiting for {interval_minutes} minutes...")
        time.sleep(interval_seconds)

# --- 메인 실행 블록 ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hotdeal Monitor Add-on")
    parser.add_argument('--interval', type=int, required=True, help="Monitoring interval in minutes.")
    parser.add_argument('--url', type=str, required=True, help="Target hotdeal board URL.")
    
    args = parser.parse_args()
    
    monitor_hotdeals(args.url, args.interval)