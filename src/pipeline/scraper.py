"""
Scrapes .puz files from the NYT Games archive using a subscriber session cookie.

Usage:
    Set NYT_COOKIE in your environment (the value of the `NYT-S` cookie from
    an authenticated browser session), then call `download_range` or
    `sync_to_today` for incremental updates.
"""

import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

NYT_PUZ_URL = "https://www.nytimes.com/svc/crosswords/v2/puzzle/print/{date}.puz"
DEFAULT_OUT = Path("data/raw_puz")
BENCHMARK_START = date(2026, 2, 1)
RATE_LIMIT_SECONDS = 1.5


def _session(cookie: str) -> requests.Session:
    s = requests.Session()
    s.cookies.set("NYT-S", cookie, domain=".nytimes.com")
    s.headers.update({"User-Agent": "nytbench/0.1 (+github)"})
    return s


def _latest_downloaded(out_dir: Path) -> date | None:
    """Return the most recent puzzle date already on disk, or None."""
    dates = []
    for p in out_dir.glob("*.puz"):
        try:
            dates.append(date.fromisoformat(p.stem))
        except ValueError:
            pass
    return max(dates) if dates else None


def sync_to_today(
    out_dir: Path = DEFAULT_OUT,
    cookie: str | None = None,
    start: date = BENCHMARK_START,
) -> list[Path]:
    """Incrementally download any puzzles missing between `start` and today.

    On the first run this fetches everything from `start` to today.
    On subsequent runs it resumes from the day after the latest file on disk,
    so re-running the script is always safe and efficient.
    """
    latest = _latest_downloaded(Path(out_dir))
    resume_from = (latest + timedelta(days=1)) if latest else start
    today = date.today()

    if resume_from > today:
        print(f"  already up to date (latest: {latest})")
        return []

    print(f"  fetching {resume_from} → {today}")
    return download_range(resume_from, today, out_dir, cookie)


def download_range(
    start: date,
    end: date,
    out_dir: Path = DEFAULT_OUT,
    cookie: str | None = None,
) -> list[Path]:
    """Download .puz files for every calendar day in [start, end].

    Already-present files are skipped. Returns paths of successfully
    downloaded files only (skips are not included).
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
