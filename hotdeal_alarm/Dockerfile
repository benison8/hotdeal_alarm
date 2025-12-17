FROM ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18

WORKDIR /app

RUN apk add --no-cache bash dos2unix

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# 여기서 강제로 줄바꿈 문자를 한 번 더 제거합니다.
RUN dos2unix /app/run.sh && chmod a+x /app/run.sh

# S6-overlay 에러 방지를 위한 필수 설정
ENTRYPOINT []
CMD [ "/bin/bash", "/app/run.sh" ]
