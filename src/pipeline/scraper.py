"""
Scrapes .puz files from the NYT Games archive using a subscriber session cookie.

Usage:
    Set NYT_COOKIE in your environment (the value of the `NYT-S` cookie from
    an authenticated browser session), then call `download_range`.
"""

import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

NYT_PUZ_URL = "https://www.nytimes.com/svc/crosswords/v2/puzzle/print/{date}.puz"
DEFAULT_OUT = Path("data/raw_puz")
RATE_LIMIT_SECONDS = 1.5


def _session(cookie: str) -> requests.Session:
    s = requests.Session()
    s.cookies.set("NYT-S", cookie, domain=".nytimes.com")
    s.headers.update({"User-Agent": "nytbench/0.1 (+github)"})
    return s


def download_range(
    start: date,
    end: date,
    out_dir: Path = DEFAULT_OUT,
    cookie: str | None = None,
) -> list[Path]:
    """Download .puz files for every day in [start, end].

    Returns a list of paths to successfully downloaded files.
    """
    cookie = cookie or os.environ["NYT_COOKIE"]
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = _session(cookie)
    downloaded: list[Path] = []
    current = start

    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        dest = out_dir / f"{date_str}.puz"

        if dest.exists():
            downloaded.append(dest)
            current += timedelta(days=1)
            continue

        url = NYT_PUZ_URL.format(date=date_str)
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            downloaded.append(dest)
            print(f"  downloaded {date_str}")
        except requests.HTTPError as exc:
            print(f"  skip {date_str}: {exc}")

        time.sleep(RATE_LIMIT_SECONDS)
        current += timedelta(days=1)

    return downloaded
