"""
Referee tests for the crossing-conflict check in the Validator.

The key scenario: an agent writes one word, then tries to write a second word
that crosses it with an incompatible letter at the shared square. The validator
must reject the second write with its standardized "conflicts" error.

Grid used (5x5):

    A P P L E   1-Across: APPLE      3-Across: TESTS
    L . . . A   1-Down:   ALOFT      2-Down:   EARNS
    O . . . R
    F . . . N
    T E S T S

1-Across and 1-Down share the top-left square (row 1, col 1). 1-Across and
2-Down share (row 1, col 5).
"""

import pytest

from src.environment.simulator import CrosswordEnv
from src.environment.validator import Validator


def _puzzle() -> dict:
    rows = ["APPLE", "L...A", "O...R", "F...N", "TESTS"]
    solution = list("".join(rows))
    grid = ["." if ch == "." else " " for ch in solution]
    return {
        "width": 5,
        "height": 5,
        "grid": grid,
        "solution": solution,
        "clues_across": {1: "Fruit on a tree", 3: "School exams"},
        "clues_down": {1: "Up in the air", 2: "Merits; deserves"},
    }


def _blank_grid(puzzle: dict) -> list[str]:
    return list(puzzle["grid"])


# ── Validator unit level ─────────────────────────────────────────────────

def test_conflicting_crossing_word_is_rejected():
    """Two words crossing with incompatible letters must be rejected."""
    puzzle = _puzzle()
    validator = Validator(puzzle)
    grid = _blank_grid(puzzle)

    # Place APPLE across the top row: A at (row1, col1) onward.
    for i, ch in enumerate("APPLE"):
        grid[i] = ch

    # 1-Down starts at the same top-left square. Its first letter must agree
    # with the 'A' already placed by 1-Across. "ZLOFT" starts with Z -> clash.
    ok, msg = validator.validate_write("down", 1, "ZLOFT", grid)

    assert ok is False
    assert "conflict" in msg.lower()
    assert "row 1, col 1" in msg  # standardized location in the error


def test_compatible_crossing_word_is_accepted():
    """A crossing word that agrees at the shared square is accepted."""
    puzzle = _puzzle()
    validator = Validator(puzzle)
    grid = _blank_grid(puzzle)
    for i, ch in enumerate("APPLE"):
        grid[i] = ch

    # ALOFT shares its leading 'A' with APPLE -> no conflict.
    ok, msg = validator.validate_write("down", 1, "ALOFT", grid)

    assert ok is True
    assert msg == ""


def test_conflict_check_skipped_without_grid():
    """Without a board, the crossing check cannot and does not run."""
    validator = Validator(_puzzle())
    # No grid supplied: a well-formed, correct-length answer passes.
    ok, msg = validator.validate_write("down", 1, "ZLOFT")
    assert ok is True
    assert msg == ""


# ── Through the full environment (referee in action) ─────────────────────

def test_env_rejects_conflicting_write_and_keeps_board_intact():
    """End-to-end: env.step surfaces the conflict and does not mutate the board."""
    env = CrosswordEnv(_puzzle())
    env.reset()

    _, _, _, info = env.step(
        {"type": "WRITE", "direction": "across", "number": 1, "answer": "APPLE"}
    )
    assert "error" not in info

    obs, _, _, info = env.step(
        {"type": "WRITE", "direction": "down", "number": 1, "answer": "ZLOFT"}
    )
    assert "error" in info
    assert "conflict" in info["error"].lower()

    # The rejected write must not have touched the board: top-left stays 'A'.
    assert obs["grid"][0] == "A"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
