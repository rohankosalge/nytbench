"""
Applies inclusion/exclusion criteria to parsed puzzle JSON files.

The benchmark uses puzzles published ON OR AFTER BENCHMARK_START (Feb 1 2026).
Puzzles before that date risk appearing in model training corpora and are
excluded to prevent contamination.

Additional rules:
  2. Puzzles with rebus squares are discarded (non-uniform action space).
  3. Only standard 15x15 (weekday) and 21x21 (Sunday) grids are kept.
"""

import json
from datetime import date
from pathlib import Path

BENCHMARK_START = date(2026, 2, 1)
ALLOWED_SIZES = {(15, 15), (21, 21)}


def passes_filters(puzzle: dict) -> tuple[bool, str]:
    """Return (True, "") if the puzzle passes all filters, else (False, reason)."""
    try:
        pub_date = date.fromisoformat(puzzle["date"])
    except (KeyError, ValueError):
        return False, "unparseable date"

    if pub_date < BENCHMARK_START:
        return False, f"before benchmark start ({pub_date})"

    if puzzle.get("has_rebus"):
        return False, "rebus puzzle"

    size = (puzzle.get("width"), puzzle.get("height"))
    if size not in ALLOWED_SIZES:
        return False, f"non-standard grid size {size}"

    return True, ""


def filter_directory(json_dir: Path, out_dir: Path) -> list[Path]:
    """Symlink passing JSON files into out_dir, return accepted paths."""
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
