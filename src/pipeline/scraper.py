"""
Downloads .puz files from the NYT crossword archive for an active subscriber.

Authentication
--------------
Every request must carry a valid `NYT-S` session token. You can supply it two
ways:

  1. Directly, via the NYT_COOKIE environment variable (copy the value of the
     `NYT-S` cookie from an authenticated browser session), or
  2. By email + password, via `login()`, which performs the NYT account login
     and extracts the `NYT-S` token for you. Set NYT_EMAIL and NYT_PASSWORD.

The download endpoint and login flow are NYT-internal and may change; both are
isolated here so they are easy to update in one place.

Usage:
    from src.pipeline.scraper import sync_to_today
    sync_to_today()                      # uses NYT_COOKIE or NYT_EMAIL/PASSWORD
"""

import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# Endpoint that returns a printable .puz for a given ISO date (subscriber only).
NYT_PUZ_URL = "https://www.nytimes.com/svc/crosswords/v2/puzzle/print/{date}.puz"
# Account login endpoint used to exchange credentials for an NYT-S token.
NYT_LOGIN_URL = "https://myaccount.nytimes.com/svc/ios/v2/login"

DEFAULT_OUT = Path("data/raw_puz")
BENCHMARK_START = date(2026, 2, 1)
RATE_LIMIT_SECONDS = 1.5

# A Crosswords-app style User-Agent is expected by the login endpoint.
_LOGIN_HEADERS = {
    "User-Agent": "Crosswords/2.4.2 CFNetwork/1335.0.3 Darwin/21.6.0",
    "client_id": "ios.crosswords",
}


def login(email: str | None = None, password: str | None = None) -> str:
    """Authenticate with NYT credentials and return the `NYT-S` session token.

    Reads NYT_EMAIL / NYT_PASSWORD from the environment when arguments are
    omitted. Raises RuntimeError if the login does not yield an NYT-S token.
    """
    email = email or os.environ["NYT_EMAIL"]
    password = password or os.environ["NYT_PASSWORD"]

    resp = requests.post(
        NYT_LOGIN_URL,
        data={"login": email, "password": password},
        headers=_LOGIN_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()

    cookies = resp.json().get("data", {}).get("cookies", [])
    for cookie in cookies:
        if cookie.get("name") == "NYT-S":
            return cookie["cipheredValue"]
    raise RuntimeError("Login succeeded but no NYT-S token was returned.")


def resolve_cookie(cookie: str | None = None) -> str:
    """Resolve an NYT-S token from (in order): argument, NYT_COOKIE, or login()."""
    if cookie:
        return cookie
    if os.environ.get("NYT_COOKIE"):
        return os.environ["NYT_COOKIE"]
    return login()


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
    cookie = resolve_cookie(cookie)
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
