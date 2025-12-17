FROM ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.18

WORKDIR /app

RUN apk add --no-cache dos2unix
COPY . .
RUN dos2unix /app/run.sh  # 윈도우 줄바꿈 문자를 리눅스용으로 강제 변환
RUN chmod a+x /app/run.sh

COPY . .


RUN chmod a+x /app/run.sh
ENTRYPOINT []
CMD [ "/bin/bash", "/app/run.sh" ]