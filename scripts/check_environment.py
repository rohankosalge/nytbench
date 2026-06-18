"""
Oracle check for the benchmark environment — no model, no API calls, no cost.

Feeds each puzzle's own ground-truth solution back through the two scoring
components and asserts they behave correctly:

  1. Grader: grading the solution against itself must yield a perfect score
     (solved, accuracy 1.0, fill 1.0), and a deliberately corrupted grid must
     NOT be solved. This proves the grader detects both perfect and imperfect
     fills.
  2. Referee (CrosswordEnv): replaying the ground-truth answers through the
     step() interface must end with done=True and reward=1.0, with the final
     board matching the solution. This proves the validator/state-tracker accept
     correct fills and the win condition fires.

It is an *oracle*: the "agent" always plays perfectly, so a passing run means
the scoring/referee machinery is wired correctly, independent of any model.

Usage:
    python scripts/check_environment.py                 # checks every puzzle in the splits
    python scripts/check_environment.py --puzzles 5     # quick smoke (first 5)
    python scripts/check_environment.py --splits-dir data/filtered_json
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running directly (python scripts/check_environment.py) without PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.environment.simulator import CrosswordEnv
from src.evaluation.grader import grade


def _find_puzzles(splits_dir: Path) -> list[Path]:
    """Collect puzzle JSON files from a splits dir (recursively) or a flat dir."""
    paths = sorted(splits_dir.rglob("*.json"))
    return paths


def _check_data(puzzle: dict) -> tuple[bool, str]:
    """Every white square must hold an A-Z letter (a well-formed, solvable grid).

    A white cell holding a space/blank is a parsing artifact: no agent can place
    a letter there through the action space, and the validator rejects non-alpha
    writes — so the puzzle is unsolvable as a benchmark item. This is a DATA
    problem, kept separate from the scoring-machinery checks below.
    """
    width = puzzle["width"]
    offenders = [
        (i // width + 1, i % width + 1, sq)
        for i, sq in enumerate(puzzle["solution"])
        if sq != "." and not (len(sq) == 1 and sq.isalpha())
    ]
    if offenders:
        sample = ", ".join(f"r{r}c{c}={v!r}" for r, c, v in offenders[:3])
        more = f" (+{len(offenders) - 3} more)" if len(offenders) > 3 else ""
        return False, f"{len(offenders)} white square(s) are not a single A-Z letter: {sample}{more}"
    return True, ""


def _check_grader(puzzle: dict) -> tuple[bool, str]:
    """Scoring machinery: a perfect grid is recognised as solved; a corruption isn't."""
    solution = puzzle["solution"]

    perfect = grade(solution, solution)
    if not (perfect["solved"] and perfect["accuracy"] == 1.0):
        return False, f"perfect solution was not scored as solved: {perfect}"

    # Corrupt the first white square and confirm the grader notices.
    corrupted = list(solution)
    for i, sq in enumerate(corrupted):
        if sq != ".":
            corrupted[i] = "A" if sq != "A" else "B"
            break
    bad = grade(corrupted, solution)
    if bad["solved"] or bad["accuracy"] >= 1.0:
        return False, f"corrupted grid still scored as solved/perfect: {bad}"

    return True, ""


def _check_referee(env: CrosswordEnv) -> tuple[bool, str]:
    """Replaying ground-truth answers must end solved (done + reward 1.0)."""
    env.reset()
    entries = env.puzzle["entries"]
    reward, done, obs = 0.0, False, None

    for direction in ("across", "down"):
        for entry in entries[direction]:
            obs, reward, done, info = env.step(
                {
                    "type": "WRITE",
                    "direction": direction,
                    "number": entry["num"],
                    "answer": entry["answer"],
                }
            )
            if info.get("error"):
                return False, (
                    f"referee rejected ground-truth {entry['num']}-{direction}: "
                    f"{info['error']}"
                )

    if not done:
        return False, "board not complete after writing every ground-truth answer"
    if reward != 1.0:
        return False, f"final reward was {reward}, expected 1.0"

    # Belt and suspenders: the final board must grade as solved too.
    final = grade(obs["grid"], env.solution)
    if not final["solved"]:
        return False, f"final board did not grade as solved: {final}"

    return True, ""


def main() -> None:
    parser = argparse.ArgumentParser(description="Oracle check for the benchmark environment.")
    parser.add_argument(
        "--splits-dir",
        default="data/stratified_splits",
        help="Directory of puzzle JSON (searched recursively). "
        "Falls back to data/filtered_json if empty.",
    )
    parser.add_argument("--puzzles", type=int, default=None, help="Limit to the first N puzzles")
    args = parser.parse_args()

    splits_dir = Path(args.splits_dir)
    puzzles = _find_puzzles(splits_dir)
    if not puzzles:
        fallback = Path("data/filtered_json")
        puzzles = _find_puzzles(fallback)
        if puzzles:
            print(f"  (no puzzles in {splits_dir}, using {fallback})")

    if not puzzles:
        print("No puzzles found. Run scripts/build_dataset.py first.")
        sys.exit(1)

    if args.puzzles is not None:
        puzzles = puzzles[: args.puzzles]

    machinery_failures: list[str] = []  # the scoring/referee code is wrong
    data_issues: list[str] = []         # the puzzle itself is malformed
    for path in puzzles:
        puzzle = json.loads(path.read_text())

        # Scoring machinery is independent of data cleanliness — always check it.
        ok, reason = _check_grader(puzzle)
        if not ok:
            machinery_failures.append(f"{path.stem} [grader]: {reason}")

        # A malformed grid can't be replayed (validator rejects non-alpha), so
        # flag it as a data issue and skip the referee replay for it.
        ok, reason = _check_data(puzzle)
        if not ok:
            data_issues.append(f"{path.stem}: {reason}")
            continue

        ok, reason = _check_referee(CrosswordEnv(puzzle))
        if not ok:
            machinery_failures.append(f"{path.stem} [referee]: {reason}")

    checked = len(puzzles)
    if data_issues:
        print(f"\nDATA ISSUES — {len(data_issues)} malformed puzzle(s) (not a code bug):")
        for d in data_issues:
            print(f"  - {d}")
    if machinery_failures:
        print(f"\nMACHINERY FAILURES — {len(machinery_failures)} (scoring/referee is wrong):")
        for f in machinery_failures:
            print(f"  - {f}")

    if machinery_failures or data_issues:
        sys.exit(1)

    print(f"\nOK — all {checked} puzzles pass the grader + referee oracle.")


if __name__ == "__main__":
    main()
