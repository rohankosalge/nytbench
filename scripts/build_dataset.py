"""
End-to-end dataset construction pipeline.

Usage:
    python scripts/build_dataset.py \\
        --start 2020-01-01 \\
        --end   2026-02-01 \\
        --out   data/

Steps:
  1. Scrape .puz files from NYT (requires NYT_COOKIE env var)
  2. Parse each .puz into a JSON state
  3. Apply filters (date cutoff, no rebus, standard grid size)
  4. Annotate each puzzle with its Flow metric
  5. Organise puzzles into stratified splits by weekday
"""

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

from src.pipeline.scraper import download_range
from src.pipeline.parser import parse_all
from src.pipeline.filters import filter_directory
from src.pipeline.flow_calc import annotate_flow


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the nytbench dataset.")
    parser.add_argument("--start", default="2020-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", default="2026-02-01", help="End date YYYY-MM-DD (inclusive)")
    parser.add_argument("--out", default="data", help="Root output directory")
    parser.add_argument("--skip-scrape", action="store_true", help="Skip download step")
    args = parser.parse_args()

    out = Path(args.out)
    raw_dir = out / "raw_puz"
    json_dir = out / "processed_json"
    filtered_dir = out / "filtered_json"
    splits_dir = out / "stratified_splits"

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    # Step 1: Scrape
    if not args.skip_scrape:
        print(f"[1/5] Scraping puzzles {start} → {end}")
        download_range(start, end, raw_dir)
    else:
        print("[1/5] Skipping scrape (--skip-scrape)")

    # Step 2: Parse
    print("[2/5] Parsing .puz → JSON")
    parse_all(raw_dir, json_dir)

    # Step 3: Filter
    print("[3/5] Applying filters")
    filter_directory(json_dir, filtered_dir)

    # Step 4: Flow annotation
    print("[4/5] Annotating Flow metric")
    annotate_flow(filtered_dir)

    # Step 5: Stratified splits
    print("[5/5] Building stratified splits")
    _build_splits(filtered_dir, splits_dir)

    print("\nDone. Dataset is ready in:", out.resolve())


def _build_splits(filtered_dir: Path, splits_dir: Path) -> None:
    splits_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}

    for json_path in sorted(filtered_dir.glob("*.json")):
        puzzle = json.loads(json_path.read_text())
        weekday = (puzzle.get("weekday") or "Unknown").lower()
        day_dir = splits_dir / weekday
        day_dir.mkdir(exist_ok=True)
        dest = day_dir / json_path.name
        if not dest.exists():
            shutil.copy2(json_path, dest)
        counts[weekday] = counts.get(weekday, 0) + 1

    for day, n in sorted(counts.items()):
        print(f"  {day}: {n} puzzles")


if __name__ == "__main__":
    main()
