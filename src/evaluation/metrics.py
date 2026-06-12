"""
Aggregates per-puzzle grade dicts into benchmark-level summary statistics.

Expected input: a list of episode result dicts, each with keys:
  solved, fill_rate, accuracy, turns, tool_calls, weekday, date
"""

from collections import defaultdict
from typing import Any


def aggregate(results: list[dict[str, Any]]) -> dict:
    """Return overall and per-weekday summary statistics."""
    if not results:
        return {}

    overall = _summarise(results)
    by_day: dict[str, list] = defaultdict(list)
    for r in results:
        day = r.get("weekday") or "Unknown"
        by_day[day].append(r)

    return {
        "overall": overall,
        "by_weekday": {day: _summarise(rs) for day, rs in sorted(by_day.items())},
        "n": len(results),
    }


def _summarise(results: list[dict]) -> dict:
    n = len(results)
    solve_rate = sum(1 for r in results if r.get("solved")) / n
    fill_rate = sum(r.get("fill_rate", 0.0) for r in results) / n
    accuracy = sum(r.get("accuracy", 0.0) for r in results) / n
    turns = sum(r.get("turns", 0) for r in results) / n
    tool_calls = sum(r.get("tool_calls", 0) for r in results) / n

    return {
        "n": n,
        "solve_rate": round(solve_rate, 4),
        "fill_rate": round(fill_rate, 4),
        "accuracy": round(accuracy, 4),
        "mean_turns": round(turns, 2),
        "mean_tool_calls": round(tool_calls, 2),
    }


def print_report(summary: dict) -> None:
    """Print a human-readable benchmark report to stdout."""
    overall = summary.get("overall", {})
    print(f"\n{'='*50}")
    print(f"  nytbench results  (n={summary.get('n', 0)})")
    print(f"{'='*50}")
    print(f"  Solve rate:       {overall.get('solve_rate', 0):.1%}")
    print(f"  Fill rate:        {overall.get('fill_rate', 0):.1%}")
    print(f"  Accuracy:         {overall.get('accuracy', 0):.1%}")
    print(f"  Mean turns:       {overall.get('mean_turns', 0):.1f}")
    print(f"  Mean tool calls:  {overall.get('mean_tool_calls', 0):.1f}")
    print(f"\n  By weekday:")
    for day, stats in summary.get("by_weekday", {}).items():
        print(
            f"    {day:<12} solve={stats['solve_rate']:.1%}  "
            f"fill={stats['fill_rate']:.1%}  turns={stats['mean_turns']:.0f}"
        )
    print(f"{'='*50}\n")
