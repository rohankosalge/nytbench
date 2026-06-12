"""
Tracks the mutable board state during a benchmark episode.

Maintains:
  - grid: list of characters (" " for unfilled, letter for filled, "." for black)
  - unsolved_across / unsolved_down: sets of clue numbers not yet correctly filled
"""


class BoardState:
    def __init__(self, puzzle: dict) -> None:
        self.puzzle = puzzle
        self.width: int = puzzle["width"]
        self.height: int = puzzle["height"]
        self.solution: list[str] = puzzle["solution"]
        self.clues_across: dict = {int(k): v for k, v in puzzle["clues_across"].items()}
        self.clues_down: dict = {int(k): v for k, v in puzzle["clues_down"].items()}

        # Start with all non-black squares empty
        self.grid: list[str] = [
            "." if sq == "." else " " for sq in puzzle["grid"]
        ]

        # Build number->square-index mappings
        self._across_indices: dict[int, list[int]] = {}
        self._down_indices: dict[int, list[int]] = {}
        self._build_indices(puzzle)

        self.unsolved_across: set[int] = set(self.clues_across.keys())
        self.unsolved_down: set[int] = set(self.clues_down.keys())

    # ------------------------------------------------------------------
    # Index construction
    # ------------------------------------------------------------------

    def _build_indices(self, puzzle: dict) -> None:
        numbering = _number_grid(self.width, self.height, self.grid)
        for num, (r, c) in numbering.items():
            # Across
            if num in self.clues_across:
                indices = []
                cc = c
                while cc < self.width and self.grid[r * self.width + cc] != ".":
                    indices.append(r * self.width + cc)
                    cc += 1
                self._across_indices[num] = indices
            # Down
            if num in self.clues_down:
                indices = []
                rr = r
                while rr < self.height and self.grid[rr * self.width + c] != ".":
                    indices.append(rr * self.width + c)
                    rr += 1
                self._down_indices[num] = indices

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_clue(self, direction: str, number: int) -> str:
        if direction == "across":
            return self.clues_across.get(number, f"No {number}-Across clue found.")
        return self.clues_down.get(number, f"No {number}-Down clue found.")

    def write(self, direction: str, number: int, answer: str) -> None:
        answer = answer.upper()
        indices = self._indices(direction, number)
        for i, idx in enumerate(indices):
            if i < len(answer):
                self.grid[idx] = answer[i]
        self._refresh_solved(direction, number)

    def erase(self, direction: str, number: int) -> None:
        for idx in self._indices(direction, number):
            if self.grid[idx] != ".":
                self.grid[idx] = " "
        if direction == "across":
            self.unsolved_across.add(number)
        else:
            self.unsolved_down.add(number)

    def is_complete(self) -> bool:
        return all(sq != " " for sq in self.grid)

    def matches_solution(self, solution: list[str]) -> bool:
        for sq, sol in zip(self.grid, solution):
            if sq == ".":
                continue
            if sq != sol:
                return False
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _indices(self, direction: str, number: int) -> list[int]:
        mapping = self._across_indices if direction == "across" else self._down_indices
        return mapping.get(number, [])

    def _refresh_solved(self, direction: str, number: int) -> None:
        indices = self._indices(direction, number)
        sol_word = "".join(self.solution[i] for i in indices)
        cur_word = "".join(self.grid[i] for i in indices)
        target_set = self.unsolved_across if direction == "across" else self.unsolved_down
        if cur_word == sol_word:
            target_set.discard(number)
        else:
            target_set.add(number)


def _number_grid(width: int, height: int, grid: list[str]) -> dict[int, tuple[int, int]]:
    """Assign standard crossword numbers and return {number: (row, col)}."""

    def is_black(r: int, c: int) -> bool:
        return grid[r * width + c] == "."

    numbering: dict[int, tuple[int, int]] = {}
    n = 1
    for r in range(height):
        for c in range(width):
            if is_black(r, c):
                continue
            starts_across = (c == 0 or is_black(r, c - 1)) and (
                c + 1 < width and not is_black(r, c + 1)
            )
            starts_down = (r == 0 or is_black(r - 1, c)) and (
                r + 1 < height and not is_black(r + 1, c)
            )
            if starts_across or starts_down:
                numbering[n] = (r, c)
                n += 1
    return numbering
