FROM ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치
RUN apk add --no-cache bash

# 종속성 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# 실행 권한 부여
RUN chmod a+x /app/hotdeal_alarm.py

# [중요] S6-overlay를 완전히 무시하고 파이썬을 직접 실행합니다.
# ENTRYPOINT를 [""]로 비우는 것이 핵심입니다.
ENTRYPOINT [""]
CMD ["python3", "-u", "/app/hotdeal_alarm.py"]