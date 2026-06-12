"""
Applies inclusion/exclusion criteria to parsed puzzle JSON files.

Rules (in priority order):
  1. Publication date must be on or before CUTOFF_DATE (Feb 1 2026).
  2. Puzzles with rebus squares are discarded.
  3. Only standard 15x15 (weekday) and 21x21 (Sunday) grids are kept.
"""

import json
from datetime import date
from pathlib import Path

CUTOFF_DATE = date(2026, 2, 1)
ALLOWED_SIZES = {(15, 15), (21, 21)}


def passes_filters(puzzle: dict) -> tuple[bool, str]:
    """Return (True, "") if the puzzle passes all filters, else (False, reason)."""
    # Date cutoff
    try:
        pub_date = date.fromisoformat(puzzle["date"])
    except (KeyError, ValueError):
        return False, "unparseable date"

    if pub_date > CUTOFF_DATE:
        return False, f"after cutoff ({pub_date})"

    # No rebus
    if puzzle.get("has_rebus"):
        return False, "rebus puzzle"

    # Grid size
    size = (puzzle.get("width"), puzzle.get("height"))
    if size not in ALLOWED_SIZES:
        return False, f"non-standard grid size {size}"

    return True, ""


def filter_directory(json_dir: Path, out_dir: Path) -> list[Path]:
    """Copy passing JSON files (as symlinks) into out_dir, return accepted paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    accepted: list[Path] = []
    rejected = 0

    for json_path in sorted(Path(json_dir).glob("*.json")):
        puzzle = json.loads(json_path.read_text())
        ok, reason = passes_filters(puzzle)
        if ok:
            dest = out_dir / json_path.name
            if not dest.exists():
                dest.symlink_to(json_path.resolve())
            accepted.append(dest)
        else:
            rejected += 1
            print(f"  rejected {json_path.stem}: {reason}")

    print(f"  accepted {len(accepted)}, rejected {rejected}")
    return accepted
