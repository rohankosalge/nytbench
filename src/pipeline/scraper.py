"""
Downloads NYT crossword puzzles for an active subscriber.

Data source
-----------
NYT removed the legacy printable ``.puz`` endpoint, so puzzles are now fetched
from the JSON API in two steps:

  1. List puzzle IDs for a date range via the v3 ``puzzles.json`` endpoint.
  2. Download each puzzle body (grid, clues, answers) via the v6
     ``puzzle/{id}.json`` endpoint.

The v6 endpoint returns 403 unless the request carries the
``x-games-auth-bypass: true`` header in addition to a valid ``NYT-S`` cookie;
both are applied by :func:`_session`. The raw v6 JSON is saved verbatim to disk
(one ``{date}.json`` per puzzle) and canonicalised later by ``parser.py``.

Authentication
--------------
Every request must carry a valid `NYT-S` session token. You can supply it two
ways:

  1. Directly, via the NYT_COOKIE environment variable (copy the value of the
     `NYT-S` cookie from an authenticated browser session), or
  2. By email + password, via `login()`, which performs the NYT account login
     and extracts the `NYT-S` token for you. Set NYT_EMAIL and NYT_PASSWORD.

The endpoints and login flow are NYT-internal and may change; they are isolated
here so they are easy to update in one place.

Usage:
    from src.pipeline.scraper import sync_to_today
    sync_to_today()                      # uses NYT_COOKIE or NYT_EMAIL/PASSWORD
"""

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests

# Lists puzzle metadata (including IDs) for a date range. Cookie-authenticated.
NYT_LIST_URL = "https://www.nytimes.com/svc/crosswords/v3/puzzles.json"
# Returns a single puzzle body (grid, clues, answers) by numeric puzzle ID.
NYT_PUZZLE_URL = "https://www.nytimes.com/svc/crosswords/v6/puzzle/{id}.json"
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
    s.headers.update(
        {
            "User-Agent": "nytbench/0.1 (+github)",
            # Required by the v6 puzzle endpoint; without it every request 403s.
            "x-games-auth-bypass": "true",
        }
    )
    return s


def list_puzzle_ids(
    start: date,
    end: date,
    session: requests.Session,
    publish_type: str = "daily",
) -> dict[date, int]:
    """Return a {publish_date: puzzle_id} map for [start, end] via the v3 list API."""
    params = {
        "publish_type": publish_type,
        "date_start": start.isoformat(),
        "date_end": end.isoformat(),
        # The endpoint defaults to 100 results; raise it to cover any range.
        "limit": (end - start).days + 5,
    }
    resp = session.get(NYT_LIST_URL, params=params, timeout=20)
    resp.raise_for_status()
    out: dict[date, int] = {}
    for entry in resp.json().get("results", []):
        out[date.fromisoformat(entry["print_date"])] = entry["puzzle_id"]
    return out


def _latest_downloaded(out_dir: Path) -> date | None:
    """Return the most recent puzzle date already on disk, or None."""
    dates = []
    for p in out_dir.glob("*.json"):
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
    """Download puzzle JSON for every published day in [start, end].

    Already-present files are skipped. Returns paths of successfully
    downloaded files only (skips are not included).
    """
    cookie = resolve_cookie(cookie)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    session = _session(cookie)
    ids = list_puzzle_ids(start, end, session)
    downloaded: list[Path] = []

    for pub_date in sorted(ids):
        date_str = pub_date.isoformat()
        dest = out_dir / f"{date_str}.json"

        if dest.exists():
            continue

        url = NYT_PUZZLE_URL.format(id=ids[pub_date])
        try:
            resp = session.get(url, timeout=15)
            resp.raise_for_status()
            # Validate it parses before writing, so a partial/HTML error body
            # never lands on disk as a "puzzle".
            dest.write_text(json.dumps(resp.json()))
            downloaded.append(dest)
            print(f"  downloaded {date_str}")
        except (requests.HTTPError, ValueError) as exc:
            print(f"  skip {date_str}: {exc}")

        time.sleep(RATE_LIMIT_SECONDS)

    return downloaded
