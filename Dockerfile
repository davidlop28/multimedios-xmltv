FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# install supercronic
RUN curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 \
    -o /usr/local/bin/supercronic \
    && echo "87625cd179eff21226f0be6f2f47dd357037064598e6c1f9ffcbd0335d402bbd  /usr/local/bin/supercronic" | sha256sum -c \
    && chmod +x /usr/local/bin/supercronic

COPY scrape.py /app/scrape.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV OUTPUT_DIR=/output
ENV OUTPUT_FILE=/output/multimedios_mty.xml
EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f "http://localhost:${HTTP_PORT:-8787}/$(basename ${OUTPUT_FILE:-multimedios_mty.xml})" || exit 1

ENTRYPOINT ["/entrypoint.sh"]

