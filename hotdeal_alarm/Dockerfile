# 홈어시스턴트 파이썬 베이스 이미지
FROM ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18

# 작업 디렉토리 설정
WORKDIR /app

# 윈도우 줄바꿈 문제를 해결하기 위한 dos2unix 설치
RUN apk add --no-cache bash dos2unix

# 종속성 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 소스 복사
COPY . .

# 윈도우 줄바꿈(\r) 제거 및 실행 권한 부여
RUN dos2unix /app/run.sh && chmod a+x /app/run.sh

# 중요: S6 오버레이 시스템을 완전히 우회합니다.
ENTRYPOINT []
CMD [ "/bin/bash", "/app/run.sh" ]