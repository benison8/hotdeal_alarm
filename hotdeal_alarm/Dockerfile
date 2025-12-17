FROM ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18

WORKDIR /app

# 필요한 패키지 설치
RUN apk add --no-cache bash

# 종속성 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 현재 폴더의 모든 파일을 /app으로 복사
COPY . .

# [수정] chmod 명령어가 실패할 수 있으므로 삭제합니다. 
# 대신 파이썬 명령어로 직접 실행하면 권한 문제가 발생하지 않습니다.
ENTRYPOINT []
CMD ["python3", "-u", "hotdeal_alarm.py"]