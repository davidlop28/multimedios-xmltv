#!/usr/bin/env python3
"""
scrape.py — Multimedios Monterrey programming page -> XMLTV

- Fetches SOURCE_URL (default: https://www.multimediostv.com/programacion)
- Parses schedule sections like "Programación de Jueves 1"
- Extracts times (HH:MM) and titles
- Outputs a standards-friendly XMLTV file for Emby/Dispatcharr

Environment variables:
  SOURCE_URL      - page to scrape
  OUTPUT_FILE     - where to write XMLTV
  CHANNEL_ID      - XMLTV channel id
  CHANNEL_NAME    - display name in XMLTV
  CHANNEL_LANG    - title lang attribute (default: es)
  TIMEZONE        - IANA timezone (default: America/Monterrey)
  USER_AGENT      - HTTP User-Agent string
  TIMEOUT_SECONDS - request timeout (default: 30)
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import List, Optional

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET


# -----------------------------
# Config via environment
# -----------------------------

SOURCE_URL = os.getenv("SOURCE_URL", "https://www.multimediostv.com/programacion")
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "/output/multimedios_mty.xml")

CHANNEL_ID = os.getenv("CHANNEL_ID", "multimedios.canal6.monterrey")
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "Canal 6 Multimedios Monterrey")
CHANNEL_LANG = os.getenv("CHANNEL_LANG", "es")

TIMEZONE = os.getenv("TIMEZONE", "America/Monterrey")
TZ = ZoneInfo(TIMEZONE)

USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; multimedios-xmltv/1.0; +https://github.com/)",
)
TIMEOUT_SECONDS = int(os.getenv("TIMEOUT_SECONDS", "30"))


# -----------------------------
# Parsing helpers
# -----------------------------

# Example header on page: "Programación de Jueves 1"
SECTION_RE = re.compile(
    r"Programación\s+de\s+([A-Za-zÁÉÍÓÚáéíóúñÑ]+)\s+(\d{1,2})",
    re.IGNORECASE,
)

# Time line like "00:00"
TIME_RE = re.compile(r"^\s*(\d{2}:\d{2})\s*$")

# Spanish weekday -> Python weekday (Mon=0..Sun=6)
WEEKDAY_ES = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}


@dataclass
class Programme:
    start: datetime
    stop: datetime
    title: str


def xmltv_dt(dt: datetime) -> str:
    """XMLTV wants: YYYYMMDDHHMMSS +/-ZZZZ"""
    return dt.strftime("%Y%m%d%H%M%S %z")


def _indent_xml(elem: ET.Element, level: int = 0) -> None:
    """Pretty-print indentation for ElementTree (Python <3.9 friendly)."""
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            _indent_xml(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def choose_date_for_section(target_weekday: int, target_day: int, today: date) -> date:
    """
    The page often shows weekday + day-of-month but not month/year.
    We infer month/year by checking nearby months and picking the date closest to 'today'
    that matches both weekday and day-of-month.
    """
    candidates: List[date] = []

    # Consider previous, current, next month (buffer against month boundaries)
    for month_offset in (-1, 0, 1):
        first_of_month = date(today.year, today.month, 1)
        approx = first_of_month + timedelta(days=31 * month_offset)
        y, m = approx.year, approx.month
        try:
            d = date(y, m, target_day)
        except ValueError:
            continue
        if d.weekday() == target_weekday:
            candidates.append(d)

    if not candidates:
        # Fallback: assume current month/day, even if weekday mismatch.
        # Better than producing nothing.
        try:
            return date(today.year, today.month, target_day)
        except ValueError:
            return today

    candidates.sort(key=lambda d: abs((d - today).days))
    return candidates[0]


def extract_lines(html: str) -> List[str]:
    """
    Turn the page into a reasonably stable list of text lines.
    We keep it simple: soup.get_text('\n'), strip, drop blanks.
    """
    soup = BeautifulSoup(html, "html.parser")
    raw_lines = soup.get_text("\n").splitlines()
    lines = [ln.strip() for ln in raw_lines if ln and ln.strip()]
    return lines


def parse_schedule(html: str) -> List[Programme]:
    """
    Parse the Multimedios programming page into Programme objects.
    We look for:
      - Section headers "Programación de <weekday> <day>"
      - time lines "HH:MM"
      - title lines immediately after a time line

    Then we compute stop times as the next start time, and last one ends at 00:00 next day.
    """
    lines = extract_lines(html)
    today_local = datetime.now(TZ).date()

    programmes: List[Programme] = []
    current_date: Optional[date] = None
    pending_start_time: Optional[time] = None

    i = 0
    while i < len(lines):
        ln = lines[i]

        # New day/section?
        m = SECTION_RE.search(ln)
        if m:
            weekday_es = m.group(1).lower()
            daynum = int(m.group(2))
            wd = WEEKDAY_ES.get(weekday_es)
            if wd is None:
                current_date = None
            else:
                current_date = choose_date_for_section(wd, daynum, today_local)

            pending_start_time = None
            i += 1
            continue

        # Time line?
        mt = TIME_RE.match(ln)
        if mt and current_date is not None:
            hh, mm = map(int, mt.group(1).split(":"))
            pending_start_time = time(hh, mm)
            i += 1
            continue

        # Title after a time line
        if pending_start_time is not None and current_date is not None:
            title = ln

            # Guard against weird artifacts: sometimes the next line might be another time.
            # If that happens, skip until we find a real title.
            if TIME_RE.match(title):
                # keep pending time and move on
                i += 1
                continue

            start_dt = datetime.combine(current_date, pending_start_time).replace(tzinfo=TZ)
            programmes.append(Programme(start=start_dt, stop=start_dt, title=title))
            pending_start_time = None
            i += 1
            continue

        i += 1

    # Sort and compute stop times
    programmes.sort(key=lambda p: p.start)

    # If no programmes, return early
    if not programmes:
        return programmes

    for idx in range(len(programmes)):
        if idx + 1 < len(programmes):
            programmes[idx].stop = programmes[idx + 1].start
        else:
            # Last programme: end at midnight next day
            last_start = programmes[idx].start
            programmes[idx].stop = (last_start + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

    # Filter out invalid segments
    programmes = [p for p in programmes if p.title and p.stop > p.start]

    # Optional: remove duplicates if page repeats lines (rare)
    deduped: List[Programme] = []
    seen = set()
    for p in programmes:
        key = (p.start, p.stop, p.title)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)

    return deduped


def build_xmltv(programmes: List[Programme]) -> ET.ElementTree:
    tv = ET.Element("tv", attrib={"generator-info-name": "multimedios-xmltv-scraper"})

    ch = ET.SubElement(tv, "channel", attrib={"id": CHANNEL_ID})
    dn = ET.SubElement(ch, "display-name")
    dn.text = CHANNEL_NAME

    for p in programmes:
        prog = ET.SubElement(
            tv,
            "programme",
            attrib={
                "start": xmltv_dt(p.start),
                "stop": xmltv_dt(p.stop),
                "channel": CHANNEL_ID,
            },
        )
        title = ET.SubElement(prog, "title", attrib={"lang": CHANNEL_LANG})
        title.text = p.title

    tree = ET.ElementTree(tv)
    _indent_xml(tv)
    return tree


def fetch_html(url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.text


def ensure_output_dir(path: str) -> None:
    out_dir = os.path.dirname(path) or "."
    os.makedirs(out_dir, exist_ok=True)


def main() -> None:
    print(f"[INFO] Fetching: {SOURCE_URL}")
    html = fetch_html(SOURCE_URL)

    programmes = parse_schedule(html)
    if not programmes:
        print("[ERROR] No programmes parsed. The page layout may have changed.", file=sys.stderr)
        sys.exit(2)

    ensure_output_dir(OUTPUT_FILE)

    tree = build_xmltv(programmes)
    tree.write(OUTPUT_FILE, encoding="utf-8", xml_declaration=True)

    first = programmes[0].start
    last = programmes[-1].stop
    print(f"[OK] Wrote {len(programmes)} programmes to {OUTPUT_FILE}")
    print(f"[OK] Range: {first.isoformat()} -> {last.isoformat()}")
    print(f"[OK] Channel id: {CHANNEL_ID}")


if __name__ == "__main__":
    main()

