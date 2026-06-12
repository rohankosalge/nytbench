"""
Computes the "Flow" metric for a crossword grid.

Flow is a graph-theoretic measure of crossing density: the number of
intersections between across and down answers divided by the total number
of white squares. Higher flow => more constraints => (generally) harder
to solve by brute-force but easier to verify by crossing.

Metric concept derived from statistics published by XWord Info (xwordinfo.com),
an independent NYT crossword reference maintained by Jim Horne. Not affiliated
with this project.

Formula:
    flow = |{(r, c) : square is shared by an Across and a Down answer}|
           / |{(r, c) : square is white}|
"""

from pathlib import Path
import json


def _build_word_squares(puzzle: dict) -> tuple[set, set]:
    """Return (across_squares, down_squares) as sets of (row, col) tuples."""
    width = puzzle["width"]
    height = puzzle["height"]
    grid = puzzle["grid"]

    def is_black(r: int, c: int) -> bool:
        return grid[r * width + c] == "."

    across_squares: set[tuple[int, int]] = set()
    down_squares: set[tuple[int, int]] = set()

    for r in range(height):
        in_word = False
        for c in range(width):
            if is_black(r, c):
                in_word = False
                continue
            starts_word = c == 0 or is_black(r, c - 1)
            if starts_word:
                in_word = True
            if in_word:
                across_squares.add((r, c))

    for c in range(width):
        in_word = False
        for r in range(height):
            if is_black(r, c):
                in_word = False
                continue
            starts_word = r == 0 or is_black(r - 1, c)
            if starts_word:
                in_word = True
            if in_word:
                down_squares.add((r, c))

    return across_squares, down_squares


def compute_flow(puzzle: dict) -> float:
    """Return the Flow metric for the given parsed puzzle dict."""
    width = puzzle["width"]
    height = puzzle["height"]
    grid = puzzle["grid"]

    white_squares = sum(1 for sq in grid if sq != ".")
    if white_squares == 0:
        return 0.0

    across_sq, down_sq = _build_word_squares(puzzle)
    intersections = len(across_sq & down_sq)
    return intersections / white_squares


def annotate_flow(json_dir: Path) -> None:
    """Add a 'flow' key in-place to every JSON file in json_dir."""
    for json_path in sorted(Path(json_dir).glob("*.json")):
        puzzle = json.loads(json_path.read_text())
        if "flow" not in puzzle:
            puzzle["flow"] = compute_flow(puzzle)
            json_path.write_text(json.dumps(puzzle, indent=2))
