ARG BUILD_FROM
FROM ${BUILD_FROM}

SHELL ["/bin/ash", "-o", "pipefail", "-c"]

RUN apk add --no-cache python3 py3-pip

WORKDIR /app

COPY requirements.txt /app/requirements.txt

# Create venv and install deps into it (PEP 668 safe)
RUN python3 -m venv /opt/venv \
  && /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

COPY app/ /app/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
