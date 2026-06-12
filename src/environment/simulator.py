"""
The main crossword board environment (referee).

Exposes a step-based interface that the agent orchestrator calls:
    env = CrosswordEnv(puzzle)
    obs  = env.reset()
    obs, reward, done, info = env.step(action)
"""

import copy
import json
from pathlib import Path

from src.environment.state_tracker import BoardState
from src.environment.validator import Validator


class CrosswordEnv:
    """A single-puzzle crossword environment."""

    def __init__(self, puzzle: dict) -> None:
        self.puzzle = puzzle
        self.solution = puzzle["solution"]
        self.validator = Validator(puzzle)
        self._state: BoardState | None = None

    @classmethod
    def from_json(cls, path: Path) -> "CrosswordEnv":
        return cls(json.loads(Path(path).read_text()))

    def reset(self) -> dict:
        """Clear the board and return the initial observation."""
        self._state = BoardState(self.puzzle)
        return self._observe()

    def step(self, action: dict) -> tuple[dict, float, bool, dict]:
        """Apply one agent action and return (observation, reward, done, info).

        action schema:
            {"type": "WRITE",    "direction": "across"|"down", "number": int, "answer": str}
            {"type": "ERASE",    "direction": "across"|"down", "number": int}
            {"type": "GET_CLUE", "direction": "across"|"down", "number": int}
        """
        assert self._state is not None, "call reset() before step()"
        info: dict = {}

        atype = action["type"]
        if atype == "GET_CLUE":
            clue = self._state.get_clue(action["direction"], action["number"])
            info["clue"] = clue
            reward = 0.0

        elif atype == "WRITE":
            ok, msg = self.validator.validate_write(
                action["direction"], action["number"], action["answer"]
            )
            if ok:
                self._state.write(action["direction"], action["number"], action["answer"])
                reward = 0.0
            else:
                info["error"] = msg
                reward = 0.0

        elif atype == "ERASE":
            self._state.erase(action["direction"], action["number"])
            reward = 0.0

        else:
            raise ValueError(f"Unknown action type: {atype!r}")

        done = self._state.is_complete()
        if done:
            reward = 1.0 if self._state.matches_solution(self.solution) else 0.0

        return self._observe(), reward, done, info

    def _observe(self) -> dict:
        return {
            "grid": copy.copy(self._state.grid),
            "unsolved_across": list(self._state.unsolved_across),
            "unsolved_down": list(self._state.unsolved_down),
        }
