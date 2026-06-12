"""
End-to-end dataset construction pipeline.

Typical usage — initial build:
    python scripts/build_dataset.py

Subsequent runs to stay up to date:
    python scripts/build_dataset.py --sync

Manual date range:
    python scripts/build_dataset.py --start 2026-02-01 --end 2026-06-12

Steps:
  1. Scrape .puz files from NYT (requires NYT_COOKIE env var)
  2. Parse each .puz into a canonical JSON state
  3. Apply filters (benchmark date floor, no rebus, standard grid size)
  4. Annotate each puzzle with its Flow metric
  5. Organise puzzles into per-weekday stratified splits
"""

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

from src.pipeline.scraper import BENCHMARK_START, download_range, sync_to_today
from src.pipeline.parser import parse_all
from src.pipeline.filters import filter_directory
from src.pipeline.flow_calc import annotate_flow


def main() -> None:
    parser = argparse.ArgumentParser(description="Build / update the nytbench dataset.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--sync",
        action="store_true",
        help=(
            "Incremental mode: download any puzzles missing between "
            "Feb 1 2026 and today, then re-run all downstream steps."
        ),
    )
    group.add_argument("--start", help="Start date YYYY-MM-DD (ignored if --sync)")
    parser.add_argument("--end", default=None, help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--out", default="data", help="Root output directory")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip download step")
    args = parser.parse_args()

    out = Path(args.out)
    raw_dir = out / "raw_puz"
    json_dir = out / "processed_json"
    filtered_dir = out / "filtered_json"
    splits_dir = out / "stratified_splits"

    # Step 1: Scrape
    if args.skip_scrape:
        print("[1/5] Skipping scrape (--skip-scrape)")
    elif args.sync:
        print("[1/5] Syncing new puzzles to today")
        sync_to_today(raw_dir)
    else:
        start = date.fromisoformat(args.start) if args.start else BENCHMARK_START
        end = date.fromisoformat(args.end) if args.end else date.today()
        print(f"[1/5] Scraping puzzles {start} → {end}")
        download_range(start, end, raw_dir)

    # Step 2: Parse (skips already-parsed files)
    print("[2/5] Parsing .puz → JSON")
    parse_all(raw_dir, json_dir)

    # Step 3: Filter
    print("[3/5] Applying filters")
    filter_directory(json_dir, filtered_dir)

    # Step 4: Flow annotation (skips already-annotated files)
    print("[4/5] Annotating Flow metric")
    annotate_flow(filtered_dir)

    # Step 5: Stratified splits (copies only new files)
    print("[5/5] Building stratified splits by weekday")
    _build_splits(filtered_dir, splits_dir)

    print("\nDone. Dataset ready in:", out.resolve())


def _build_splits(filtered_dir: Path, splits_dir: Path) -> None:
    """Distribute puzzles into per-weekday subdirectories."""
    splits_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    for json_path in sorted(Path(filtered_dir).glob("*.json")):
        puzzle = json.loads(json_path.read_text())
        weekday = (puzzle.get("weekday") or "unknown").lower()
        day_dir = splits_dir / weekday
        day_dir.mkdir(exist_ok=True)
        dest = day_dir / json_path.name
        if not dest.exists():
            shutil.copy2(json_path, dest)
        counts[weekday] = counts.get(weekday, 0) + 1

    order = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in order:
        n = counts.get(day, 0)
        if n:
            print(f"  {day:>12}: {n} puzzles")


if __name__ == "__main__":
    main()
