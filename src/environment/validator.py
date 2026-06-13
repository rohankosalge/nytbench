"""
Strict constraint engine that checks whether a proposed answer physically fits.

Checks performed on WRITE:
  1. The clue number exists in the given direction.
  2. The answer contains only A-Z characters.
  3. The answer length matches the word's grid length.
  4. No character in the answer conflicts with a letter already on the board at
     a crossing square.

Check 4 requires awareness of the current board, so `validate_write` accepts
the live grid. When no grid is supplied the first three (board-independent)
checks still run and the crossing check is skipped.
"""

import re

_ALPHA = re.compile(r"^[A-Za-z]+$")


class Validator:
    def __init__(self, puzzle: dict) -> None:
        self._puzzle = puzzle
        self._width: int = puzzle["width"]
        self._clues_across: set[int] = {int(k) for k in puzzle["clues_across"]}
        self._clues_down: set[int] = {int(k) for k in puzzle["clues_down"]}
        # Flat grid indices occupied by each slot, keyed by (direction, number).
        self._slot_cells: dict[tuple[str, int], list[int]] = {}
        self._build_slots(puzzle)

    def _build_slots(self, puzzle: dict) -> None:
        from src.environment.state_tracker import _number_grid

        width = puzzle["width"]
        height = puzzle["height"]
        grid_fill = ["." if sq == "." else " " for sq in puzzle["grid"]]
        numbering = _number_grid(width, height, grid_fill)

        for num, (r, c) in numbering.items():
            if num in self._clues_across:
                cells, cc = [], c
                while cc < width and grid_fill[r * width + cc] != ".":
                    cells.append(r * width + cc)
                    cc += 1
                self._slot_cells[("across", num)] = cells

            if num in self._clues_down:
                cells, rr = [], r
                while rr < height and grid_fill[rr * width + c] != ".":
                    cells.append(rr * width + c)
                    rr += 1
                self._slot_cells[("down", num)] = cells

    def validate_write(
        self,
        direction: str,
        number: int,
        answer: str,
        grid: list[str] | None = None,
    ) -> tuple[bool, str]:
        """Validate a proposed WRITE, optionally against the current board.

        `grid` is the live board (flat, row-major): "." for black squares, " "
        for empty white squares, and an uppercase letter for a filled square.
        When provided, the answer is checked for conflicts with letters already
        placed at crossing squares.
        """
        clue_set = self._clues_across if direction == "across" else self._clues_down
        if number not in clue_set:
            return False, f"{number}-{direction.capitalize()} does not exist."

        if not _ALPHA.match(answer):
            return False, "Answer must contain only alphabetic characters."

        cells = self._slot_cells.get((direction, number))
        if cells is not None and len(answer) != len(cells):
            return False, (
                f"Answer length {len(answer)} does not match "
                f"grid length {len(cells)} for {number}-{direction.capitalize()}."
            )

        if grid is not None and cells is not None:
            for ch, idx in zip(answer.upper(), cells):
                existing = grid[idx]
                if existing not in (" ", ".") and existing.upper() != ch:
                    row, col = idx // self._width + 1, idx % self._width + 1
                    return False, (
                        f"{number}-{direction.capitalize()} conflicts at "
                        f"row {row}, col {col}: cannot place '{ch}' where "
                        f"'{existing.upper()}' is already on the board."
                    )

        return True, ""
