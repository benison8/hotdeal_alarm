FROM ghcr.io/home-assistant/base-python:3.11

WORKDIR /app

RUN apk add --no-cache bash

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .