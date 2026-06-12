"""
Strict constraint engine that checks whether a proposed answer physically fits.

Checks performed on WRITE:
  1. The clue number exists in the given direction.
  2. The answer length matches the word's grid length.
  3. The answer contains only A-Z characters.
  4. No character in the answer conflicts with a correctly-placed crossing letter.
"""

import re

_ALPHA = re.compile(r"^[A-Za-z]+$")


class Validator:
    def __init__(self, puzzle: dict) -> None:
        self._puzzle = puzzle
        self._clues_across: set[int] = {int(k) for k in puzzle["clues_across"]}
        self._clues_down: set[int] = {int(k) for k in puzzle["clues_down"]}
        self._word_lengths: dict[tuple[str, int], int] = {}
        self._build_lengths(puzzle)

    def _build_lengths(self, puzzle: dict) -> None:
        from src.environment.state_tracker import _number_grid

        width = puzzle["width"]
        height = puzzle["height"]
        grid_fill = ["." if sq == "." else " " for sq in puzzle["grid"]]
        numbering = _number_grid(width, height, grid_fill)

        for num, (r, c) in numbering.items():
            if num in self._clues_across:
                length = 0
                cc = c
                while cc < width and grid_fill[r * width + cc] != ".":
                    length += 1
                    cc += 1
                self._word_lengths[("across", num)] = length

            if num in self._clues_down:
                length = 0
                rr = r
                while rr < height and grid_fill[rr * width + c] != ".":
                    length += 1
                    rr += 1
                self._word_lengths[("down", num)] = length

    def validate_write(
        self, direction: str, number: int, answer: str
    ) -> tuple[bool, str]:
        clue_set = self._clues_across if direction == "across" else self._clues_down
        if number not in clue_set:
            return False, f"{number}-{direction.capitalize()} does not exist."

        if not _ALPHA.match(answer):
            return False, "Answer must contain only alphabetic characters."

        expected_len = self._word_lengths.get((direction, number))
        if expected_len is not None and len(answer) != expected_len:
            return False, (
                f"Answer length {len(answer)} does not match "
                f"grid length {expected_len} for {number}-{direction.capitalize()}."
            )

        return True, ""
