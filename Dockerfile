FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# install supercronic
ADD https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

COPY scrape.py /app/scrape.py
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV OUTPUT_DIR=/output
ENV OUTPUT_FILE=/output/multimedios_mty.xml
EXPOSE 8787

ENTRYPOINT ["/entrypoint.sh"]

