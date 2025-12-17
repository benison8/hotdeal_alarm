FROM homeassistant/amd64-base-python:3.11

WORKDIR /app

RUN apk add --no-cache bash

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

# ENTRYPOINT, CMD 절대 지정하지 말 것
