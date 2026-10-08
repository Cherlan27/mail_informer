FROM python:3.12-slim

ARG TARGETARCH=amd64
ARG SUPERCRONIC_VERSION=v0.2.33

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSLo /usr/local/bin/supercronic \
       "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-${TARGETARCH}" \
    && chmod +x /usr/local/bin/supercronic \
    && apt-get purge -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml constraints.txt ./
COPY mail_informer ./mail_informer
RUN pip install --no-cache-dir -c constraints.txt .

COPY crontab entrypoint.sh ./
RUN chmod +x entrypoint.sh \n    && useradd --create-home --uid 1000 app
USER app

ENTRYPOINT ["./entrypoint.sh"]
