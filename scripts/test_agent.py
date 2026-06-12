"""
Deterministic test of the bare-bones agent interface.

Run with:
    python scripts/test_agent.py

Covers the action parser, the AgentBoard coordinate writes/erases, the
observation rendering, and the full loop driven by a scripted (fake) model. No
network or real LLM calls.

Uses data/raw_puz/test_monday.puz (create with: python scripts/make_test_puz.py)

Grid:
    A P P L E   1-Across @(1,1)   3-Across @(1,5)=TESTS
    L . . . A   1-Down   @(1,1)=ALOFT
    O . . . R   2-Down   @(5,1)=EARNS
    F . . . N
    T E S T S
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.actions import Done, Erase, GetClue, NoOp, Write, parse_action
from src.agent.loop import run_agent
from src.agent.observation import AgentBoard
from src.pipeline.parser import parse_puz

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
_results: list[tuple[str, bool]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    tag = PASS if condition else FAIL
    suffix = f"  ({detail})" if detail and not condition else ""
    print(f"  [{tag}] {label}{suffix}")
    _results.append((label, condition))


class ScriptedLLM:
    """Returns a fixed sequence of replies, ignoring the prompt."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls = 0

    def __call__(self, system: str, messages: list[dict]) -> str:
        reply = self._replies[self.calls]
        self.calls += 1
        return reply


puzzle = parse_puz(Path("data/raw_puz/test_monday.puz"))

# ─────────────────────────────────────────────────────────────
# Phase 1 – Action parser
# ─────────────────────────────────────────────────────────────
print("\n── Phase 1: Action parser ───────────────────────────────")

a = parse_action("GET_CLUE(1, across)")
check("parses GET_CLUE", isinstance(a, GetClue) and a.number == 1 and a.direction == "across")

a = parse_action("WRITE(APPLE, 1, 1)")
check("parses WRITE (default across)",
      isinstance(a, Write) and a.word == "APPLE" and a.x == 1 and a.y == 1 and a.direction == "across")

a = parse_action("WRITE(ALOFT, 1, 1, down)")
check("parses WRITE with down direction",
      isinstance(a, Write) and a.direction == "down")

a = parse_action('WRITE("EARNS", 5, 1, down)')
check("parses quoted word", isinstance(a, Write) and a.word == "EARNS")

a = parse_action("ERASE(3, 2)")
check("parses ERASE", isinstance(a, Erase) and a.x == 3 and a.y == 2)

a = parse_action("I think the answer is DONE here.")
check("parses DONE", isinstance(a, Done))

a = parse_action("hmm let me think about this")
check("unparseable -> NoOp", isinstance(a, NoOp))

a = parse_action("Let's try WRITE(apple, 1, 1) now")
check("lowercase word is uppercased", isinstance(a, Write) and a.word == "APPLE")

# ─────────────────────────────────────────────────────────────
# Phase 2 – Board geometry + observation
# ─────────────────────────────────────────────────────────────
print("\n── Phase 2: Board + observation ─────────────────────────")

board = AgentBoard(puzzle)
check("4 slots built", len(board.slots) == 4, f"got {len(board.slots)}")
check("1-Across starts at (1,1)", board.slot(1, "across").start == (1, 1))
check("3-Across starts at (1,5)", board.slot(3, "across").start == (1, 5))
check("1-Down starts at (1,1)", board.slot(1, "down").start == (1, 1))
check("2-Down starts at (5,1)", board.slot(2, "down").start == (5, 1))
check("white square count is 16", board.white_squares() == 16, f"got {board.white_squares()}")

obs = board.render_observation()
check("observation has Across header", "Across:" in obs)
check("observation has Down header", "Down:" in obs)
check("observation shows a clue", "Fruit on a tree" in obs)
check("observation shows start coord", "@(1,1)" in obs)
check("empty slot rendered with underscores", "_ _ _ _ _" in obs)

# ─────────────────────────────────────────────────────────────
# Phase 3 – Writes, erases, completion
# ─────────────────────────────────────────────────────────────
print("\n── Phase 3: Writes / erases ─────────────────────────────")

ok, _ = board.write("APPLE", 1, 1, "across")
check("WRITE across accepted", ok)
check("state shows A P P L E", board.state_string(board.slot(1, "across")) == "A P P L E")
check("crossing cell shared with 1-Down", board.fill[(1, 1)] == "A")

ok, msg = board.write("APPLE", 2, 2, "across")
check("WRITE onto black square rejected", ok is False and "black" in msg)

ok, msg = board.write("APPLES", 1, 1, "across")
check("WRITE running off grid rejected", ok is False and "out of bounds" in msg)

board.write("ALOFT", 1, 1, "down")
check("1-Down state shows A L O F T", board.state_string(board.slot(1, "down")) == "A L O F T")

ok, _ = board.erase(1, 1)
check("ERASE clears the square", ok and (1, 1) not in board.fill)

ok, msg = board.erase(2, 2)
check("ERASE on black square rejected", ok is False and "black" in msg)

# ─────────────────────────────────────────────────────────────
# Phase 4 – Full loop with a scripted model
# ─────────────────────────────────────────────────────────────
print("\n── Phase 4: Bare-bones loop ─────────────────────────────")

fresh = AgentBoard(puzzle)
llm = ScriptedLLM([
    "WRITE(APPLE, 1, 1)",
    "WRITE(TESTS, 1, 5)",
    "WRITE(ALOFT, 1, 1, down)",
    "WRITE(EARNS, 5, 1, down)",
    "DONE",  # safety net; loop should stop on completion before reaching this
])
result = run_agent(llm, fresh, max_turns=20)

check("loop reports completion", result["complete"] is True)
check("loop stopped at 4 turns (on completion)", result["turns"] == 4, f"turns={result['turns']}")
check("board is fully filled", fresh.is_complete())
check("transcript has 8 messages (4 user + 4 assistant)",
      len(result["transcript"]) == 8, f"got {len(result['transcript'])}")

# A loop that never solves should stop at max_turns.
stuck_board = AgentBoard(puzzle)
stuck_llm = ScriptedLLM(["thinking..."] * 5)
stuck = run_agent(stuck_llm, stuck_board, max_turns=5)
check("unsolved loop hits max_turns", stuck["turns"] == 5 and stuck["complete"] is False)

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in _results if ok)
total = len(_results)
print(f"\n── Results: {passed}/{total} passed ─────────────────────────")
if passed < total:
    print("  Failed checks:")
    for label, ok in _results:
        if not ok:
            print(f"    ✗ {label}")
    sys.exit(1)
print("  All checks passed.")
