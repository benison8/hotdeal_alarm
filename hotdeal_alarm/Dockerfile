ARG BUILD_FROM
FROM ${BUILD_FROM}

SHELL ["/bin/ash", "-o", "pipefail", "-c"]

# Install python + pip
RUN apk add --no-cache python3 py3-pip

WORKDIR /app

# requirements.txt is in add-on root (COPY requirements.txt . 형태)
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Your app code
COPY app/ /app/

# Entrypoint
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD [ "/run.sh" ]
