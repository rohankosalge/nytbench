"""
Parses .puz files into a canonical JSON representation using puzpy.

Each output JSON has the schema:
{
  "date":         "YYYY-MM-DD",
  "weekday":      "Monday" | ... | "Sunday",
  "width":        int,
  "height":       int,
  "grid":         list[str],         # "." for black, " " for empty white
  "solution":     list[str],         # "." for black, one letter per white square
  "clues_across": {number: clue},
  "clues_down":   {number: clue},
  "entries": {                       # per-slot ground truth, used by the rebus filter
    "across": [{"num": int, "clue": str, "len": int, "answer": str}, ...],
    "down":   [{"num": int, "clue": str, "len": int, "answer": str}, ...]
  },
  "has_rebus":    bool               # derived from the length cross-reference below
}

`len` is the number of physical grid squares allocated to the slot.
`answer` is the true solution, with any rebus square expanded to its full
multi-character string. For a standard (non-rebus) puzzle, len(answer) == len
for every slot. When a rebus is present, at least one slot has
len(answer) > len, which is exactly how the rebus filter detects it.
"""

import json
from datetime import date
from pathlib import Path

import puz

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _slot_indices(entry: dict, width: int) -> list[int]:
    """Return the grid square indices occupied by a clue entry."""
    start = entry["cell"]
    length = entry["len"]
    step = 1 if entry["dir"] == "across" else width
    return [start + i * step for i in range(length)]


def _expand_answer(puzzle: puz.Puzzle, rebus, entry: dict, width: int) -> str:
    """Reconstruct the true answer for a slot, expanding any rebus squares.

    For a normal square the single solution letter is used. For a rebus square
    the full multi-character string from the .puz rebus table is substituted,
    so the returned answer can be longer than the slot's square count.
    """
    chars: list[str] = []
    for idx in _slot_indices(entry, width):
        if rebus is not None and rebus.is_rebus_square(idx):
            chars.append(rebus.get_rebus_solution(idx) or puzzle.solution[idx])
        else:
            chars.append(puzzle.solution[idx])
    return "".join(chars)


def _build_entries(puzzle: puz.Puzzle) -> dict:
    """Build the across/down entry lists with rebus-expanded answers."""
    numbering = puzzle.clue_numbering()
    width = puzzle.width

    try:
        rebus = puzzle.rebus()
        if not rebus.has_rebus():
            rebus = None
    except Exception:
        rebus = None

    def pack(entries: list[dict]) -> list[dict]:
        packed = []
        for e in entries:
            packed.append(
                {
                    "num": e["num"],
                    "clue": e["clue"],
                    "len": e["len"],
                    "answer": _expand_answer(puzzle, rebus, e, width),
                }
            )
        return packed

    return {
        "across": pack(numbering.across),
        "down": pack(numbering.down),
    }


def parse_puz(puz_path: Path) -> dict:
    """Parse a single .puz file and return the canonical dict."""
    puzzle = puz.read(str(puz_path))
    stem = puz_path.stem  # expected format: YYYY-MM-DD

    try:
        pub_date = date.fromisoformat(stem)
        weekday = WEEKDAYS[pub_date.weekday()]
    except ValueError:
        weekday = None

    numbering = puzzle.clue_numbering()
    clues_across = {entry["num"]: entry["clue"] for entry in numbering.across}
    clues_down = {entry["num"]: entry["clue"] for entry in numbering.down}

    # puzpy fill uses '-' for empty white squares; normalise to ' '
    grid = ["." if ch == "." else " " for ch in puzzle.fill]
    # puzpy solution uses '.' for black squares, uppercase letters otherwise
    solution = list(puzzle.solution)

    entries = _build_entries(puzzle)
    # Single source of truth: a rebus exists iff some slot's true answer is
    # longer than the number of squares allocated to it.
    has_rebus = any(
        len(e["answer"]) != e["len"]
        for e in entries["across"] + entries["down"]
    )

    return {
        "date": stem,
        "weekday": weekday,
        "width": puzzle.width,
        "height": puzzle.height,
        "grid": grid,
        "solution": solution,
        "clues_across": clues_across,
        "clues_down": clues_down,
        "entries": entries,
        "has_rebus": has_rebus,
    }


def parse_v6_json(json_path: Path) -> dict:
    """Parse a raw NYT v6 puzzle JSON file into the canonical dict.

    The v6 body lays the grid out row-major in ``cells``: a black square is an
    empty object, a white square carries ``answer`` (the full solution string
    for that square, multi-character on a rebus), ``label`` (its grid number),
    and ``clues`` (indices into the ``clues`` list). Each clue carries its
    ``cells`` (grid indices), ``direction``, ``label``, and ``text``.
    """
    raw = json.loads(json_path.read_text())
    body = raw["body"][0]
    width = body["dimensions"]["width"]
    height = body["dimensions"]["height"]
    cells = body["cells"]
    stem = json_path.stem  # expected format: YYYY-MM-DD

    try:
        pub_date = date.fromisoformat(stem)
        weekday = WEEKDAYS[pub_date.weekday()]
    except ValueError:
        weekday = None

    # A cell is white iff it carries an answer; black squares are empty objects.
    def is_white(cell: dict) -> bool:
        return bool(cell) and "answer" in cell

    grid = [" " if is_white(c) else "." for c in cells]
    # One entry per square: the full answer string for a white square (a single
    # letter except on rebus squares, which the filter later discards), "." for
    # black squares.
    solution = [c["answer"] if is_white(c) else "." for c in cells]

    def _clue_text(clue: dict) -> str:
        return "".join(part.get("plain", "") for part in clue.get("text", []))

    clues_across: dict[int, str] = {}
    clues_down: dict[int, str] = {}
    entries: dict[str, list[dict]] = {"across": [], "down": []}

    for clue in body["clues"]:
        num = int(clue["label"])
        text = _clue_text(clue)
        answer = "".join(cells[i].get("answer", "") for i in clue["cells"])
        record = {
            "num": num,
            "clue": text,
            "len": len(clue["cells"]),
            "answer": answer,
        }
        if clue["direction"].lower() == "across":
            clues_across[num] = text
            entries["across"].append(record)
        else:
            clues_down[num] = text
            entries["down"].append(record)

    entries["across"].sort(key=lambda e: e["num"])
    entries["down"].sort(key=lambda e: e["num"])

    # Single source of truth: a rebus exists iff some slot's true answer is
    # longer than the number of squares allocated to it.
    has_rebus = any(
        len(e["answer"]) != e["len"]
        for e in entries["across"] + entries["down"]
    )

    return {
        "date": stem,
        "weekday": weekday,
        "width": width,
        "height": height,
        "grid": grid,
        "solution": solution,
        "clues_across": clues_across,
        "clues_down": clues_down,
        "entries": entries,
        "has_rebus": has_rebus,
    }


def parse_all(raw_dir: Path, out_dir: Path) -> list[Path]:
    """Parse every raw puzzle in raw_dir and write canonical JSON to out_dir.

    Handles both the current NYT v6 JSON files (``*.json``) and legacy ``.puz``
    files (used by the test fixtures).
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    sources = sorted(Path(raw_dir).glob("*.json")) + sorted(Path(raw_dir).glob("*.puz"))
    for src in sources:
        dest = out_dir / f"{src.stem}.json"
        if dest.exists():
            written.append(dest)
            continue
        try:
            data = parse_v6_json(src) if src.suffix == ".json" else parse_puz(src)
            dest.write_text(json.dumps(data, indent=2))
            written.append(dest)
        except Exception as exc:
            print(f"  parse error {src.name}: {exc}")

    return written
