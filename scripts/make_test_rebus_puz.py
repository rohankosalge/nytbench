"""
Builds a synthetic 5x5 .puz file containing a rebus square, for testing the
rebus filter. Identical grid to make_test_puz.py, but cell (0,0) holds the
two-character rebus "AB" instead of a single letter.

    [AB] P P L E   <- 1-Across answer expands to "ABPPLE" (6 chars, 5 squares)
      L  . . . A
      O  . . . R
      F  . . . N
      T  E S T S

Because the true answer for 1-Across is longer than the five squares allocated
to it, the length cross-reference in filters.detect_rebus_by_length flags this
puzzle as a rebus and it is discarded.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import puz


def build() -> Path:
    out = Path("data/raw_puz")
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "test_rebus.puz"

    p = puz.Puzzle()
    p.title = "nytbench Rebus Test Puzzle"
    p.author = "nytbench"
    p.copyright = ""
    p.width = 5
    p.height = 5

    # The solution grid stores the rebus cell's first letter ('A'); the full
    # "AB" string lives in the rebus table written below.
    p.solution = "APPLE" + "L...A" + "O...R" + "F...N" + "TESTS"
    p.fill = "-----" + "-...-" + "-...-" + "-...-" + "-----"
    p.clues = [
        "Fruit on a tree (with a rebus)",  # 1-Across
        "Up in the air",                   # 1-Down
        "Merits; deserves",                # 2-Down
        "School exams",                    # 3-Across
    ]

    # Mark cell index 0 (row 0, col 0) as a rebus holding "AB".
    rebus = p.rebus()
    rebus.add_rebus_squares(0, "AB")
    rebus.save()

    p.save(str(dest))
    print(f"Saved: {dest.resolve()}")
    return dest


if __name__ == "__main__":
    build()
