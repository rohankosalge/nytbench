"""
The agent's working board and its text observation.

`AgentBoard` is a coordinate-addressed view of a puzzle that the bare-bones loop
mutates directly via WRITE/ERASE. It also renders the observation the model
sees each turn.

The observation favours tokens over pixels: rather than drawing a 15x15 ASCII
grid, it lists each clue with its starting coordinate and current fill state,
for example:

    Across:
      1 @(1,1): Fruit on a tree — A _ _ _ E
      3 @(1,5): School exams — _ _ _ _ _

The underscores convey the answer length, the letters convey progress, and the
@(x,y) tells the model where to WRITE. This is compact and model-agnostic.

Coordinates: x = column (1..width), y = row (1..height), 1-indexed, top-left
origin. The flat grid index of (x, y) is (y-1) * width + (x-1).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.environment.state_tracker import _number_grid


@dataclass
class Slot:
    number: int
    direction: str  # "across" | "down"
    clue: str
    cells: list[tuple[int, int]]  # (x, y) squares in order

    @property
    def length(self) -> int:
        return len(self.cells)

    @property
    def start(self) -> tuple[int, int]:
        return self.cells[0]


class AgentBoard:
    def __init__(self, puzzle: dict) -> None:
        self.width: int = puzzle["width"]
        self.height: int = puzzle["height"]
        self._grid: list[str] = puzzle["grid"]  # "." black, " " white
        self.clues_across = {int(k): v for k, v in puzzle["clues_across"].items()}
        self.clues_down = {int(k): v for k, v in puzzle["clues_down"].items()}

        # Current letters the agent has placed: (x, y) -> single uppercase char.
        self.fill: dict[tuple[int, int], str] = {}

        self.slots: list[Slot] = self._build_slots()
        self._by_key: dict[tuple[int, str], Slot] = {
            (s.number, s.direction): s for s in self.slots
        }

    # ── geometry ────────────────────────────────────────────────────────
    def _is_black_rc(self, r: int, c: int) -> bool:
        return self._grid[r * self.width + c] == "."

    def is_black(self, x: int, y: int) -> bool:
        return self._is_black_rc(y - 1, x - 1)

    def in_bounds(self, x: int, y: int) -> bool:
        return 1 <= x <= self.width and 1 <= y <= self.height

    def _build_slots(self) -> list[Slot]:
        w, h = self.width, self.height
        numbering = _number_grid(w, h, self._grid)  # {num: (r, c)}
        slots: list[Slot] = []
        for num, (r, c) in sorted(numbering.items()):
            starts_across = (c == 0 or self._is_black_rc(r, c - 1)) and (
                c + 1 < w and not self._is_black_rc(r, c + 1)
            )
            starts_down = (r == 0 or self._is_black_rc(r - 1, c)) and (
                r + 1 < h and not self._is_black_rc(r + 1, c)
            )
            if starts_across:
                cells, cc = [], c
                while cc < w and not self._is_black_rc(r, cc):
                    cells.append((cc + 1, r + 1))
                    cc += 1
                slots.append(Slot(num, "across", self.clues_across.get(num, ""), cells))
            if starts_down:
                cells, rr = [], r
                while rr < h and not self._is_black_rc(rr, c):
                    cells.append((c + 1, rr + 1))
                    rr += 1
                slots.append(Slot(num, "down", self.clues_down.get(num, ""), cells))
        return slots

    def slot(self, number: int, direction: str) -> Slot | None:
        return self._by_key.get((number, direction))

    # ── mutations ───────────────────────────────────────────────────────
    def write(self, word: str, x: int, y: int, direction: str = "across") -> tuple[bool, str]:
        """Place `word` starting at (x, y) going `direction`.

        Rejects (without changing the board) if the word would run off the grid
        or cross a black square. Returns (ok, message).
        """
        word = word.upper()
        dx, dy = (1, 0) if direction == "across" else (0, 1)

        targets: list[tuple[int, int]] = []
        cx, cy = x, y
        for _ in range(len(word)):
            if not self.in_bounds(cx, cy):
                return False, f"out of bounds at ({cx},{cy})"
            if self.is_black(cx, cy):
                return False, f"black square at ({cx},{cy})"
            targets.append((cx, cy))
            cx, cy = cx + dx, cy + dy

        for (tx, ty), ch in zip(targets, word):
            self.fill[(tx, ty)] = ch
        return True, f"wrote {word} at ({x},{y}) {direction}"

    def erase(self, x: int, y: int) -> tuple[bool, str]:
        """Clear a single square."""
        if not self.in_bounds(x, y):
            return False, f"out of bounds at ({x},{y})"
        if self.is_black(x, y):
            return False, f"black square at ({x},{y})"
        self.fill.pop((x, y), None)
        return True, f"erased ({x},{y})"

    # ── reads ───────────────────────────────────────────────────────────
    def state_string(self, slot: Slot) -> str:
        """Render a slot's current fill as 'A _ _ _ E'."""
        return " ".join(self.fill.get(cell, "_") for cell in slot.cells)

    def clue_text(self, number: int, direction: str) -> str | None:
        s = self.slot(number, direction)
        return s.clue if s else None

    def white_squares(self) -> int:
        return sum(1 for ch in self._grid if ch != ".")

    def is_complete(self) -> bool:
        """True once every white square holds a letter."""
        for y in range(1, self.height + 1):
            for x in range(1, self.width + 1):
                if not self.is_black(x, y) and (x, y) not in self.fill:
                    return False
        return True

    # ── observation ─────────────────────────────────────────────────────
    def render_observation(self) -> str:
        filled = len(self.fill)
        total = self.white_squares()
        lines = [f"Grid {self.width}x{self.height} — {filled}/{total} squares filled."]

        for direction, header in (("across", "Across:"), ("down", "Down:")):
            section = [s for s in self.slots if s.direction == direction]
            if not section:
                continue
            lines.append("")
            lines.append(header)
            for s in sorted(section, key=lambda s: s.number):
                sx, sy = s.start
                lines.append(
                    f"  {s.number} @({sx},{sy}): {s.clue} — {self.state_string(s)}"
                )
        return "\n".join(lines)
