"""
Overlays the agent's final grid with the ground-truth solution from the .puz file
and computes per-puzzle correctness.
"""

import json
from pathlib import Path


def grade(agent_grid: list[str], solution: list[str]) -> dict:
    """Compare agent_grid against solution, return a result dict.

    Both lists have the same length. Black squares ('.') are skipped.
    """
    total_white = sum(1 for sq in solution if sq != ".")
    correct = 0
    filled = 0

    for agent_sq, sol_sq in zip(agent_grid, solution):
        if sol_sq == ".":
            continue
        if agent_sq != " ":
            filled += 1
        if agent_sq == sol_sq:
            correct += 1

    fill_rate = filled / total_white if total_white else 0.0
    accuracy = correct / total_white if total_white else 0.0
    solved = correct == total_white

    return {
        "solved": solved,
        "fill_rate": round(fill_rate, 4),
        "accuracy": round(accuracy, 4),
        "correct_squares": correct,
        "total_white_squares": total_white,
    }


def grade_from_files(agent_grid: list[str], puzzle_json_path: Path) -> dict:
    """Convenience wrapper that loads the solution from a JSON file."""
    puzzle = json.loads(Path(puzzle_json_path).read_text())
    result = grade(agent_grid, puzzle["solution"])
    result["date"] = puzzle.get("date")
    result["weekday"] = puzzle.get("weekday")
    return result
