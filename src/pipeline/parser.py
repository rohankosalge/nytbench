"""
Parses .puz files into a canonical JSON representation using puzpy.

Each output JSON has the schema:
{
  "date":        "YYYY-MM-DD",
  "weekday":     "Monday" | ... | "Sunday",
  "width":       int,
  "height":      int,
  "grid":        list[str],        # "." for black, " " for empty
  "solution":    list[str],        # "." for black, letter for answer
  "clues_across": {number: clue},
  "clues_down":   {number: clue},
  "has_rebus":   bool
}
"""

import json
from datetime import date
from pathlib import Path

import puz

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _detect_rebus(puzzle: puz.Puzzle) -> bool:
    """Return True if any square requires more than one character."""
    try:
        return puzzle.rebus().has_rebus()
    except Exception:
        return False


def parse_puz(puz_path: Path) -> dict:
    """Parse a single .puz file and return the canonical dict."""
    puzzle = puz.read(str(puz_path))
    stem = puz_path.stem  # expected format: YYYY-MM-DD

    try:
        pub_date = date.fromisoformat(stem)
        weekday = WEEKDAYS[pub_date.weekday()]
    except ValueError:
        pub_date = None
        weekday = None

    numbering = puzzle.clue_numbering()

    clues_across = {entry["num"]: entry["clue"] for entry in numbering.across}
    clues_down = {entry["num"]: entry["clue"] for entry in numbering.down}

    # puzpy fill uses '-' for empty white squares; normalise to ' '
    grid = ["." if ch == "." else " " for ch in puzzle.fill]
    # puzpy solution uses '.' for black squares, uppercase letters otherwise
    solution = list(puzzle.solution)

    return {
        "date": stem,
        "weekday": weekday,
        "width": puzzle.width,
        "height": puzzle.height,
        "grid": grid,
        "solution": solution,
        "clues_across": clues_across,
        "clues_down": clues_down,
        "has_rebus": _detect_rebus(puzzle),
    }


def parse_all(puz_dir: Path, out_dir: Path) -> list[Path]:
    """Parse every .puz in puz_dir and write JSON files to out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for puz_path in sorted(Path(puz_dir).glob("*.puz")):
        dest = out_dir / f"{puz_path.stem}.json"
        if dest.exists():
            written.append(dest)
            continue
        try:
            data = parse_puz(puz_path)
            dest.write_text(json.dumps(data, indent=2))
            written.append(dest)
        except Exception as exc:
            print(f"  parse error {puz_path.name}: {exc}")

    return written
