# 홈어시스턴트 베이스 이미지 사용 (파이썬 포함)
ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18
FROM ${BUILD_FROM}

# 작업 디렉토리 설정
WORKDIR /app

# 필요한 패키지 설치
RUN apk add --no-cache bash

# 파일 복사
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# 실행 권한 부여
RUN chmod a+x /app/run.sh

# 컨테이너 실행 시 run.sh를 직접 실행하도록 설정
CMD [ "/app/run.sh" ]

