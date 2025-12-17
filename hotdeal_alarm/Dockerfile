ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

RUN apk add --no-cache bash

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .
