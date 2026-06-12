"""
Deterministic test of the rebus filter and inclusion rules.

Run with:
    python scripts/test_filters.py

Covers:
  - Real non-rebus puzzle (test_monday.puz) is NOT flagged.
  - Real rebus puzzle (test_rebus.puz) IS flagged via the length cross-reference.
  - The length cross-reference on hand-crafted JSON (positive + negative).
  - passes_filters date floor and grid-size rules.

No network or LLM calls. Generate the fixtures first:
    python scripts/make_test_puz.py
    python scripts/make_test_rebus_puz.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline.parser import parse_puz
from src.pipeline.filters import detect_rebus_by_length, passes_filters

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
_results: list[tuple[str, bool]] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    tag = PASS if condition else FAIL
    suffix = f"  ({detail})" if detail and not condition else ""
    print(f"  [{tag}] {label}{suffix}")
    _results.append((label, condition))


def _entry(num, length, answer, clue="x"):
    return {"num": num, "clue": clue, "len": length, "answer": answer}


def _puzzle(across, down, *, date="2026-03-02", w=15, h=15):
    return {
        "date": date,
        "weekday": "Monday",
        "width": w,
        "height": h,
        "entries": {"across": across, "down": down},
    }


# ─────────────────────────────────────────────────────────────
# Phase 1 – Length cross-reference on hand-crafted entries
# ─────────────────────────────────────────────────────────────
print("\n── Phase 1: Length cross-reference (unit) ───────────────")

clean = _puzzle(
    across=[_entry(1, 5, "APPLE"), _entry(3, 5, "TESTS")],
    down=[_entry(1, 5, "ALOFT"), _entry(2, 5, "EARNS")],
)
is_rebus, reason = detect_rebus_by_length(clean)
check("clean puzzle not flagged", is_rebus is False, reason)

# Answer longer than slot → rebus
rebus_long = _puzzle(
    across=[_entry(1, 5, "ABPPLE")],  # 6 chars in 5 squares
    down=[_entry(1, 5, "ALOFT")],
)
is_rebus, reason = detect_rebus_by_length(rebus_long)
check("answer longer than slot flagged", is_rebus is True)
check("reason names the slot", "1-Across" in reason, reason)

# Answer shorter than slot → also flagged (malformed)
short = _puzzle(across=[_entry(1, 5, "CAT")], down=[_entry(1, 5, "ALOFT")])
is_rebus, reason = detect_rebus_by_length(short)
check("answer shorter than slot flagged", is_rebus is True, reason)

# Rebus only on a Down slot is still caught
down_rebus = _puzzle(
    across=[_entry(1, 5, "APPLE")],
    down=[_entry(1, 5, "ALOFTX")],  # 6 chars in 5 squares
)
is_rebus, reason = detect_rebus_by_length(down_rebus)
check("down-slot rebus flagged", is_rebus is True)
check("reason names down slot", "1-Down" in reason, reason)

# Missing entries → fall back to has_rebus flag
legacy = {"date": "2026-03-02", "width": 15, "height": 15, "has_rebus": True}
is_rebus, _ = detect_rebus_by_length(legacy)
check("legacy has_rebus fallback works", is_rebus is True)

# ─────────────────────────────────────────────────────────────
# Phase 2 – Real .puz fixtures
# ─────────────────────────────────────────────────────────────
print("\n── Phase 2: Real .puz fixtures ──────────────────────────")

mono = parse_puz(Path("data/raw_puz/test_monday.puz"))
is_rebus, reason = detect_rebus_by_length(mono)
check("test_monday.puz not flagged", is_rebus is False, reason)
check("test_monday has_rebus == False", mono["has_rebus"] is False)
check("1-Across answer is APPLE", mono["entries"]["across"][0]["answer"] == "APPLE")

reb = parse_puz(Path("data/raw_puz/test_rebus.puz"))
is_rebus, reason = detect_rebus_by_length(reb)
check("test_rebus.puz flagged", is_rebus is True)
check("test_rebus has_rebus == True", reb["has_rebus"] is True)
check("rebus answer expands to ABPPLE",
      reb["entries"]["across"][0]["answer"] == "ABPPLE",
      reb["entries"]["across"][0]["answer"])

# ─────────────────────────────────────────────────────────────
# Phase 3 – passes_filters end-to-end rules
# ─────────────────────────────────────────────────────────────
print("\n── Phase 3: passes_filters rules ────────────────────────")

ok, reason = passes_filters(
    _puzzle(across=[_entry(1, 5, "APPLE")], down=[_entry(1, 5, "ALOFT")])
)
check("standard 15x15 after cutoff accepted", ok, reason)

ok, reason = passes_filters(
    _puzzle(across=[_entry(1, 5, "APPLE")], down=[_entry(1, 5, "ALOFT")],
            date="2025-12-31")
)
check("puzzle before Feb 1 2026 rejected", ok is False)
check("rejection reason mentions benchmark start", "benchmark start" in reason, reason)

ok, reason = passes_filters(
    _puzzle(across=[_entry(1, 5, "ABPPLE")], down=[_entry(1, 5, "ALOFT")])
)
check("rebus puzzle rejected by passes_filters", ok is False)

ok, reason = passes_filters(
    _puzzle(across=[_entry(1, 5, "APPLE")], down=[_entry(1, 5, "ALOFT")],
            w=13, h=13)
)
check("non-standard grid size rejected", ok is False)
check("size rejection reason mentions grid size", "grid size" in reason, reason)

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
