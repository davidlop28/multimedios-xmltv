# multimedios-xmltv

Scrapes the [Multimedios TV](https://www.multimediostv.com/programacion) programming schedule for Canal 6 Monterrey, México and outputs a standards-compliant XMLTV file. The file can be consumed directly by Plex, Jellyfin, Emby, Dispatcharr, and any other IPTV client that accepts XMLTV electronic programme guides (EPG).

## Quick start

### Minimal

```bash
docker run -d \
  -p 8787:8787 \
  -v epg-data:/output \
  ghcr.io/davidlopez/multimedios-xmltv:latest
```

### Full example with common options

```bash
docker run -d \
  --name multimedios-xmltv \
  -p 8787:8787 \
  -v epg-data:/output \
  -e TZ=America/Monterrey \
  -e CRON_SCHEDULE="0 23 * * *" \
  -e HTTP_PORT=8787 \
  -e CHANNEL_ID=multimedios.canal6.monterrey \
  -e CHANNEL_NAME="Canal 6 Multimedios Monterrey" \
  ghcr.io/davidlopez/multimedios-xmltv:latest
```

The container runs the scraper once on startup, then on the configured cron schedule. The resulting XML file is served over HTTP for the duration of the container's life.

## Configuration

All configuration is done via environment variables.

| Variable | Default | Description |
|---|---|---|
| `TZ` | `America/Monterrey` | IANA timezone used by the cron scheduler and by the scraper when computing programme start/stop times. |
| `CRON_SCHEDULE` | `0 23 * * *` | Cron expression controlling when the scraper runs (default: 11 pm daily). |
| `HTTP_PORT` | `8787` | Port the built-in HTTP server listens on inside the container. Map this with `-p`. |
| `OUTPUT_DIR` | `/output` | Directory where the XML file is written and served from. |
| `OUTPUT_FILE` | `/output/multimedios_mty.xml` | Full path of the XMLTV output file. |
| `SOURCE_URL` | `https://www.multimediostv.com/programacion` | Page to scrape. Override only if the site moves. |
| `RUN_ON_STARTUP` | `true` | Set to `false` to skip the initial scrape and only run on the cron schedule. |
| `CHANNEL_ID` | `multimedios.canal6.monterrey` | XMLTV `id` attribute for the channel element. |
| `CHANNEL_NAME` | `Canal 6 Multimedios Monterrey` | Display name written into the XMLTV file. |
| `CHANNEL_LANG` | `es` | Language code for title elements in the XMLTV output. |
| `TIMEOUT_SECONDS` | `30` | HTTP request timeout for scraping, in seconds. |
| `USER_AGENT` | `Mozilla/5.0 (compatible; multimedios-xmltv/1.0; …)` | User-Agent header sent to the source site. |

## HTTP endpoint

The container runs Python's built-in HTTP server on `HTTP_PORT`, serving all files from `OUTPUT_DIR`. After the first scrape completes the XMLTV file is available at:

```
http://<host>:<port>/multimedios_mty.xml
```

For example, if the container is on the same host as your media server:

```
http://localhost:8787/multimedios_mty.xml
```

The filename matches the basename of `OUTPUT_FILE`. If you override `OUTPUT_FILE`, adjust the URL accordingly.

## Plex setup

1. Open Plex Web and go to **Settings > Live TV & DVR**.
2. Add a new device and choose **XMLTV**.
3. Enter the EPG URL: `http://<host>:8787/multimedios_mty.xml`
4. Complete the channel mapping wizard.

## Jellyfin setup

1. Open the Jellyfin dashboard and go to **Live TV**.
2. Under **TV Guide Data Providers**, click **Add** and choose **XMLTV**.
3. Enter the URL: `http://<host>:8787/multimedios_mty.xml`
4. Save and trigger a guide data refresh.

## Cron schedule

The default schedule is `0 23 * * *` — once per day at 11 pm in the configured timezone (`TZ`). Multimedios typically publishes the next day's schedule in the late evening, so this timing keeps the guide current.

Override the schedule at container start:

```bash
# Run at 6 am and 11 pm every day
-e CRON_SCHEDULE="0 6,23 * * *"
```

The scheduler is [supercronic](https://github.com/aptible/supercronic), which honours the `TZ` environment variable for all cron expressions.

## Building locally

```bash
git clone https://github.com/davidlopez/multimedios-xmltv.git
cd multimedios-xmltv

docker build -t multimedios-xmltv .

docker run -d \
  -p 8787:8787 \
  -v epg-data:/output \
  multimedios-xmltv
```

## CI/CD

A GitHub Actions workflow (`.github/workflows/docker-publish.yml`) builds and pushes the image to the GitHub Container Registry on every push to `main`. Two tags are produced: `latest` and a short commit SHA tag (`sha-<hash>`).
