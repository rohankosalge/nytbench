"""
Deterministic end-to-end test of the parser, validator, and simulator.

Run with:
    python scripts/test_simulator.py

No LLM or network calls. The test uses data/raw_puz/test_monday.puz which
must exist (create it first with: python scripts/make_test_puz.py).

Puzzle layout (5x5):
    A P P L E   <- 1-Across: APPLE
    L . . . A   <- 1-Down:   ALOFT   2-Down: EARNS
    O . . . R
    F . . . N
    T E S T S   <- 3-Across: TESTS

All crossings verified:
    (4,0): ALOFT[4]=T == TESTS[0]=T
    (4,4): EARNS[4]=S == TESTS[4]=S

Expected clue numbers:
    1-Across: APPLE (len 5)
    3-Across: TESTS (len 5)
    1-Down:   ALOFT (len 5)
    2-Down:   EARNS (len 5)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.parser import parse_puz
from src.environment.simulator import CrosswordEnv


PUZ_PATH = Path("data/raw_puz/test_monday.puz")
PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"

_results: list[tuple[str, bool]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    tag = PASS if condition else FAIL
    suffix = f"  ({detail})" if detail and not condition else ""
    print(f"  [{tag}] {label}{suffix}")
    _results.append((label, condition))


# ─────────────────────────────────────────────────────────────
# Phase 1 – Parser
# ─────────────────────────────────────────────────────────────
print("\n── Phase 1: Parser ──────────────────────────────────────")

if not PUZ_PATH.exists():
    print(f"  Missing {PUZ_PATH}. Run: python scripts/make_test_puz.py")
    sys.exit(1)

puzzle = parse_puz(PUZ_PATH)
print("  JSON output:")
print("  " + json.dumps(puzzle, indent=4).replace("\n", "\n  "))

check("width == 5",           puzzle["width"] == 5)
check("height == 5",          puzzle["height"] == 5)
check("has_rebus is False",   puzzle["has_rebus"] is False)
check("grid has 25 squares",  len(puzzle["grid"]) == 25)
check("solution has 25 sq",   len(puzzle["solution"]) == 25)

# Black square positions: (1,1),(1,2),(1,3),(2,1),(2,2),(2,3),(3,1),(3,2),(3,3)
black_indices = {6, 7, 8, 11, 12, 13, 16, 17, 18}
actual_black = {i for i, sq in enumerate(puzzle["grid"]) if sq == "."}
check("black squares correct", actual_black == black_indices,
      f"got {sorted(actual_black)}")

check("1-Across clue present", 1 in puzzle["clues_across"])
check("3-Across clue present", 3 in puzzle["clues_across"])
check("1-Down clue present",   1 in puzzle["clues_down"])
check("2-Down clue present",   2 in puzzle["clues_down"])

solution_str = "".join(puzzle["solution"])
check("solution encodes APPLE at row 0", solution_str[:5] == "APPLE",
      f"got {solution_str[:5]!r}")
check("solution encodes TESTS at row 4", solution_str[20:25] == "TESTS",
      f"got {solution_str[20:25]!r}")

# ─────────────────────────────────────────────────────────────
# Phase 2 – Validator (via env.step)
# ─────────────────────────────────────────────────────────────
print("\n── Phase 2: Validator ───────────────────────────────────")

env = CrosswordEnv(puzzle)
obs = env.reset()

# 2a. Valid write — correct length, no black squares
obs, reward, done, info = env.step(
    {"type": "WRITE", "direction": "across", "number": 1, "answer": "APPLE"}
)
check("WRITE APPLE 1-Across accepted (no error)", "error" not in info, info.get("error", ""))
check("1-Across removed from unsolved",           1 not in obs["unsolved_across"])

# 2b. Wrong length
obs2, _, _, info2 = env.step(
    {"type": "WRITE", "direction": "across", "number": 3, "answer": "OOPS"}
)
check("WRITE wrong-length word rejected",         "error" in info2, "no error returned")

# 2c. Non-existent clue number
obs3, _, _, info3 = env.step(
    {"type": "WRITE", "direction": "across", "number": 99, "answer": "HELLO"}
)
check("WRITE non-existent clue rejected",         "error" in info3)

# 2d. Non-alpha characters
obs4, _, _, info4 = env.step(
    {"type": "WRITE", "direction": "across", "number": 3, "answer": "T3STS"}
)
check("WRITE non-alpha answer rejected",          "error" in info4)

# 2e. Non-existent direction/number for ERASE
env.step({"type": "ERASE", "direction": "across", "number": 1})
check("ERASE restores 1-Across to unsolved",
      1 in env._state.unsolved_across)

# 2f. GET_CLUE returns correct text
obs5, _, _, info5 = env.step(
    {"type": "GET_CLUE", "direction": "across", "number": 1}
)
check("GET_CLUE returns non-empty string",        bool(info5.get("clue")))
check("GET_CLUE content matches expected",
      "fruit" in info5.get("clue", "").lower(),
      f"got {info5.get('clue')!r}")

# ─────────────────────────────────────────────────────────────
# Phase 3 – Full solve → done=True, reward=1.0
# ─────────────────────────────────────────────────────────────
print("\n── Phase 3: Full solve ──────────────────────────────────")

env.reset()
for direction, number, answer in [
    ("across", 1, "APPLE"),
    ("across", 3, "TESTS"),
    ("down",   1, "ALOFT"),
    ("down",   2, "EARNS"),
]:
    obs, reward, done, info = env.step(
        {"type": "WRITE", "direction": direction, "number": number, "answer": answer}
    )
    if "error" in info:
        print(f"    error on {number}-{direction}: {info['error']}")

check("board complete after all writes",   done)
check("reward == 1.0 on correct solution", reward == 1.0, f"reward={reward}")
check("unsolved_across is empty",          len(obs["unsolved_across"]) == 0)
check("unsolved_down is empty",            len(obs["unsolved_down"]) == 0)

# ─────────────────────────────────────────────────────────────
# Phase 4 – Wrong answer → reward=0.0
# ─────────────────────────────────────────────────────────────
print("\n── Phase 4: Incorrect solve ─────────────────────────────")

env.reset()
for direction, number, answer in [
    ("across", 1, "GRAPE"),  # wrong — GRAPE ≠ APPLE
    ("across", 3, "TESTS"),
    ("down",   1, "ALOFT"),
    ("down",   2, "EARNS"),
]:
    obs, reward, done, info = env.step(
        {"type": "WRITE", "direction": direction, "number": number, "answer": answer}
    )

check("board complete with wrong answer",  done)
check("reward == 0.0 on wrong solution",   reward == 0.0, f"reward={reward}")

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
passed = sum(1 for _, ok in _results if ok)
total  = len(_results)
print(f"\n── Results: {passed}/{total} passed ─────────────────────────")
if passed < total:
    print("  Failed checks:")
    for label, ok in _results:
        if not ok:
            print(f"    ✗ {label}")
    sys.exit(1)
else:
    print("  All checks passed.")
