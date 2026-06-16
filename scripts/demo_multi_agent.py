"""
Deterministic walk-through of the multi-agent solver.

Run with:
    python scripts/demo_multi_agent.py

Drives the four specialists end to end with a scripted (fake) model — no network
and no real LLM. It prints the live agent hand-off so you can watch the human-like
arc: Sprinter scaffolding -> Pattern Matcher / Lateral Thinker constraint fill ->
Eraser backtracking on a conflict.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agent.multi.orchestrator import MultiAgentSolver, solve_puzzle
from src.agent.observation import AgentBoard

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
_results: list[tuple[str, bool]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    tag = PASS if condition else FAIL
    suffix = f"  ({detail})" if detail and not condition else ""
    print(f"  [{tag}] {label}{suffix}")
    _results.append((label, condition))


class ClueKeyedLLM:
    """Canned replies keyed by the primary `Clue:` line of the request."""

    def __init__(self, routes: dict[str, str]) -> None:
        self._routes = routes

    def __call__(self, system: str, messages: list[dict]) -> str:
        clue_line = messages[-1]["content"].splitlines()[0]
        for needle, reply in self._routes.items():
            if needle in clue_line:
                return reply
        return "ABSTAIN"


def _fixed(reply: str):
    def _llm(system, messages):
        return reply
    return _llm


class RoleKeyedLLM:
    """Canned replies keyed by which specialist's system prompt is calling."""

    def __init__(self, by_role: dict[str, str]) -> None:
        self._by_role = by_role

    def __call__(self, system: str, messages: list[dict]) -> str:
        for needle, reply in self._by_role.items():
            if needle in system:
                return reply
        return "ABSTAIN"


def _single_slot_puzzle(solution_word: str, clue: str) -> dict:
    n = len(solution_word)
    return {
        "width": n,
        "height": 1,
        "grid": [" "] * n,
        "solution": list(solution_word),
        "clues_across": {1: clue},
        "clues_down": {},
    }


def _apple_puzzle() -> dict:
    rows = ["APPLE", "L...A", "O...R", "F...N", "TESTS"]
    solution = list("".join(rows))
    grid = ["." if ch == "." else " " for ch in solution]
    return {
        "width": 5,
        "height": 5,
        "grid": grid,
        "solution": solution,
        "clues_across": {1: "Fruit in the '___ a day' adage", 3: "Standardized ___ in school"},
        "clues_down": {1: "Up in the air", 2: "Hauls in, as a salary?"},
    }


def _grid3() -> dict:
    rows = ["CAT", "ARE", "RED"]
    solution = list("".join(rows))
    return {
        "width": 3,
        "height": 3,
        "grid": [" "] * 9,
        "solution": solution,
        "clues_across": {1: "Feline", 4: "They ___ here", 5: "Crimson"},
        "clues_down": {1: "Auto", 2: "Conjugation of 'to be'", 3: "Inspiring talks brand?"},
    }


# ─────────────────────────────────────────────────────────────
# Phase 1 – Full solve, all three solver roles
# ─────────────────────────────────────────────────────────────
print("\n── Phase 1: Full solve (Sprinter -> Pattern -> Lateral) ──")

llm = ClueKeyedLLM({
    "a day": "ANSWER: APPLE\nCONFIDENCE: high",          # 1-Across  (Sprinter, fill-in-blank)
    "Standardized": "ANSWER: TESTS\nCONFIDENCE: high",   # 3-Across  (Sprinter, fill-in-blank)
    "Up in the air": "ANSWER: ALOFT\nCONFIDENCE: high",  # 1-Down    (Pattern Matcher)
    "salary": (                                          # 2-Down    (Lateral Thinker, "?")
        "The clue puns on bringing home a paycheck.\n"
        "ANSWER: EARNS\nCONFIDENCE: high"
    ),
})
result = solve_puzzle(llm, _apple_puzzle(), verbose=True)

board = result["board"]
expected = _apple_puzzle()["solution"]
matches = all(
    board.fill.get((x, y)) == expected[(y - 1) * 5 + (x - 1)]
    for y in range(1, 6) for x in range(1, 6)
    if not board.is_black(x, y)
)
agents_used = {e["agent"] for e in result["log"] if e["action"] == "place"}

check("puzzle solved completely", result["complete"])
check("board matches the solution", matches)
check("Sprinter, Pattern, and Lateral all placed words",
      agents_used == {"sprinter", "pattern", "lateral"}, f"used {agents_used}")

# ─────────────────────────────────────────────────────────────
# Phase 2 – Eraser evicts the weaker crossing word
# ─────────────────────────────────────────────────────────────
print("\n── Phase 2: Eraser conflict resolution ──────────────────")

solver = MultiAgentSolver(_fixed("CLEAR: 1 down"))
board = AgentBoard(_grid3())
solver.board = board
solver._build_cell_index()

placed_weak = solver._place(board.slot(1, "down"), "COT", "medium", "sprinter")
print(f"  Sprinter writes a weak 1-Down = COT  -> placed={placed_weak}")
placed_strong = solver._place(board.slot(4, "across"), "ARE", "high", "sprinter")
print(f"  Strong 4-Across = ARE clashes at (1,2); Eraser runs -> placed={placed_strong}")

check("weak COT was evicted", (1, "down") not in solver.placements)
check("strong ARE stands", (4, "across") in solver.placements)
check("shared square now holds the winner's letter", board.fill.get((1, 2)) == "A")
check("evicted word's other cells were cleared", (1, 1) not in board.fill)

# ─────────────────────────────────────────────────────────────
# Phase 3 – Syntax extractor guards the scaffold
# ─────────────────────────────────────────────────────────────
print("\n── Phase 3: Syntax extraction filters the Sprinter ──────")

guard_llm = RoleKeyedLLM({
    "Syntax Extractor": "PART_OF_SPEECH: verb\nTENSE: present\nPLURAL: false\nREQUIRED_SUFFIX: -s",
    "Sprinter": "ANSWER: BOLT\nCONFIDENCE: high",   # ignores the -s constraint
})
guarded = solve_puzzle(guard_llm, _single_slot_puzzle("ZIPS", "Hurries off, slangily"), verbose=True)
print("  Sprinter proposed BOLT for a clue whose answer must end in -s.")
check("structurally wrong BOLT was rejected", (1, "across") not in guarded["placements"])
check("board left empty rather than seeded with a bad letter", not guarded["board"].fill)

ok_llm = RoleKeyedLLM({
    "Syntax Extractor": "PART_OF_SPEECH: verb\nTENSE: present\nPLURAL: false\nREQUIRED_SUFFIX: -s",
    "Sprinter": "ANSWER: ZIPS\nCONFIDENCE: high",
})
okay = solve_puzzle(ok_llm, _single_slot_puzzle("ZIPS", "Hurries off, slangily"))
check("suffix-compliant ZIPS was accepted", okay["placements"].get((1, "across"), {}).get("word") == "ZIPS")

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
