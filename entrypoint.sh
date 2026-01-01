#!/bin/sh
set -eu

: "${CRON_SCHEDULE:=0 23 * * *}"                 # default: 11pm daily
: "${TZ:=America/Monterrey}"
: "${HTTP_PORT:=8787}"
: "${OUTPUT_DIR:=/output}"
: "${OUTPUT_FILE:=/output/multimedios_mty.xml}"
: "${SOURCE_URL:=https://www.multimediostv.com/programacion}"
: "${RUN_ON_STARTUP:=true}"

mkdir -p "$OUTPUT_DIR"

echo "TZ=$TZ"
echo "CRON_SCHEDULE=$CRON_SCHEDULE"
echo "HTTP_PORT=$HTTP_PORT"
echo "OUTPUT_FILE=$OUTPUT_FILE"
echo "SOURCE_URL=$SOURCE_URL"

# Cron file
cat > /etc/crontab <<EOF
$CRON_SCHEDULE python /app/scrape.py >> /var/log/epg.log 2>&1
EOF

# Run once at startup (optional)
if [ "$RUN_ON_STARTUP" = "true" ]; then
  echo "Running scrape once on startup..."
  python /app/scrape.py >> /var/log/epg.log 2>&1 || true
fi

# Serve /output over HTTP
echo "Starting HTTP server on :$HTTP_PORT serving $OUTPUT_DIR"
python -m http.server "$HTTP_PORT" --directory "$OUTPUT_DIR" --bind 0.0.0.0 \
  >> /var/log/http.log 2>&1 &

# Run cron scheduler in foreground
exec /usr/local/bin/supercronic /etc/crontab

