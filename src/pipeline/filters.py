"""
Applies inclusion/exclusion criteria to parsed puzzle JSON files.

The benchmark uses puzzles published ON OR AFTER BENCHMARK_START (Feb 1 2026).
Puzzles before that date risk appearing in model training corpora and are
excluded to prevent contamination.

Additional rules:
  - Rebus puzzles are discarded (they break the one-letter-per-square action
    space). See `detect_rebus_by_length` for the detection mechanism.
  - Only standard 15x15 (weekday) and 21x21 (Sunday) grids are kept.
  - Puzzles with a white square whose solution is not a single A-Z letter are
    discarded (they are unsolvable through the action space). See
    `detect_non_alpha_squares`.
"""

import json
from datetime import date
from pathlib import Path

BENCHMARK_START = date(2026, 2, 1)
ALLOWED_SIZES = {(15, 15), (21, 21)}


def detect_rebus_by_length(puzzle: dict) -> tuple[bool, str]:
    """Detect a rebus by cross-referencing answer length against grid squares.

    Each slot in `puzzle["entries"]` records `len` (the number of physical grid
    squares allocated to the clue) and `answer` (the true solution, with any
    rebus square expanded to its full multi-character string). In a standard
    puzzle every answer occupies exactly one character per square, so
    len(answer) == len. If an answer is *longer* than its allocated squares,
    one or more squares must hold multiple characters — i.e. it is a rebus.

    Returns (True, reason) if a rebus is detected, else (False, "").
    """
    entries = puzzle.get("entries")
    if not entries:
        # Fall back to the precomputed flag for older JSON without entries.
        return (bool(puzzle.get("has_rebus")), "rebus (flagged)" if puzzle.get("has_rebus") else "")

    for direction in ("across", "down"):
        for entry in entries.get(direction, []):
            slot_squares = entry["len"]
            answer_len = len(entry["answer"])
            if answer_len > slot_squares:
                return (
                    True,
                    f"rebus at {entry['num']}-{direction.capitalize()}: "
                    f"answer {entry['answer']!r} ({answer_len} chars) "
                    f"exceeds {slot_squares} squares",
                )
            if answer_len < slot_squares:
                # Malformed entry (answer shorter than its slot) — also unusable.
                return (
                    True,
                    f"length mismatch at {entry['num']}-{direction.capitalize()}: "
                    f"answer {entry['answer']!r} ({answer_len} chars) "
                    f"shorter than {slot_squares} squares",
                )
    return (False, "")


def detect_non_alpha_squares(puzzle: dict) -> tuple[bool, str]:
    """Detect white squares whose solution is not a single A-Z letter.

    A white cell holding a blank/space (or any non-letter) is a parsing artifact:
    it cannot be filled through the one-letter-per-square action space, and the
    validator rejects non-alphabetic writes, so the puzzle is unsolvable as a
    benchmark item. Returns (True, reason) if any such square exists.
    """
    width = puzzle.get("width") or 1
    for i, sq in enumerate(puzzle.get("solution", [])):
        if sq == ".":
            continue
        if len(sq) != 1 or not sq.isalpha():
            return True, (
                f"non-alphabetic white square at row {i // width + 1}, "
                f"col {i % width + 1}: {sq!r}"
            )
    return False, ""


def passes_filters(puzzle: dict) -> tuple[bool, str]:
    """Return (True, "") if the puzzle passes all filters, else (False, reason)."""
    try:
        pub_date = date.fromisoformat(puzzle["date"])
    except (KeyError, ValueError):
        return False, "unparseable date"

    if pub_date < BENCHMARK_START:
        return False, f"before benchmark start ({pub_date})"

    is_rebus, reason = detect_rebus_by_length(puzzle)
    if is_rebus:
        return False, reason

    bad_square, reason = detect_non_alpha_squares(puzzle)
    if bad_square:
        return False, reason

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
