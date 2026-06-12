"""
Builds a small synthetic 5x5 Monday-style .puz file for offline testing.

Grid layout ('.' = black square):

    A P P L E   <- 1-Across: APPLE  ("Fruit on a tree")
    L . . . A   <- 1-Down:   ALOFT  col 0: A-L-O-F-T
    O . . . R   <- 2-Down:   EARNS  col 4: E-A-R-N-S
    F . . . N
    T E S T S   <- 3-Across: TESTS  ("School exams")

All crossings verified:
    (4,0): ALOFT[4]=T == TESTS[0]=T  ✓
    (4,4): EARNS[4]=S == TESTS[4]=S  ✓

Clue numbers (standard crossword numbering):
    1 -> (0,0): starts 1-Across (APPLE) and 1-Down (ALOFT)
    2 -> (0,4): starts 2-Down   (EARNS)
    3 -> (4,0): starts 3-Across (TESTS)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import puz


def build() -> Path:
    out = Path("data/raw_puz")
    out.mkdir(parents=True, exist_ok=True)
    dest = out / "test_monday.puz"

    p = puz.Puzzle()
    p.title = "nytbench Test Puzzle"
    p.author = "nytbench"
    p.copyright = ""
    p.width = 5
    p.height = 5

    # Row-major; '.' = black square, letter = solution
    #              row0      row1      row2      row3      row4
    p.solution = "APPLE" + "L...A" + "O...R" + "F...N" + "TESTS"

    # '.' = black, '-' = unfilled white
    p.fill = "-----" + "-...-" + "-...-" + "-...-" + "-----"

    # Clue order: for each number ascending, Across before Down
    # Num 1: Across=APPLE, Down=ALOFT
    # Num 2: Down=EARNS  (no across at (0,4))
    # Num 3: Across=TESTS (no down at (4,0))
    p.clues = [
        "Fruit on a tree",    # 1-Across  APPLE
        "Up in the air",      # 1-Down    ALOFT
        "Merits; deserves",   # 2-Down    EARNS
        "School exams",       # 3-Across  TESTS
    ]

    p.save(str(dest))
    print(f"Saved: {dest.resolve()}")
    return dest


if __name__ == "__main__":
    build()
