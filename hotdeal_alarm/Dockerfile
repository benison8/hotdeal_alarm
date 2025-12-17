# 홈어시스턴트 파이썬 베이스 이미지 사용
FROM ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18

# 작업 디렉토리 설정
WORKDIR /app

# 시스템 패키지 및 종속성 설치
RUN apk add --no-cache bash
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY . .

# 실행 권한 부여
RUN chmod a+x /app/run.sh

# 중요: S6 관리자를 거치지 않고 bash를 통해 직접 run.sh를 실행합니다.
# ENTRYPOINT를 비우고 CMD로만 실행하여 pid 1 문제를 회피합니다.
ENTRYPOINT []
CMD [ "/bin/bash", "/app/run.sh" ]
