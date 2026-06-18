"""
The multi-agent orchestrator.

`MultiAgentSolver` drives the four specialists over an `AgentBoard`, reproducing
the arc a human follows on a grid:

  1. Sprinter pass — lock in the gimmes, fill-in-the-blanks, and short words at
     near-certain confidence to build the crossing scaffold.
  2. Constraint passes — repeatedly route each unfinished slot to the Pattern
     Matcher (it has fixed letters) or the Lateral Thinker (it is wordplay),
     propagating letters until the board stops changing.
  3. Conflict resolution — whenever a placement would clash with an existing
     crossing answer, the Eraser decides which guess is weaker and clears it so
     the slot can be re-solved.

Placement provenance is tracked per slot, and the board's fill is always the
exact replay of the recorded placements. That invariant makes "erase a word"
trivial: drop its placement and rebuild.
"""

from __future__ import annotations

from typing import Callable

from src.agent.multi import classify
from src.agent.multi.agents import (
    Eraser,
    LateralThinker,
    PatternMatcher,
    Proposal,
    Sprinter,
    SyntaxExtractor,
    SyntaxSpec,
    spec_allows,
)
from src.agent.observation import AgentBoard, Slot

LLM = Callable[[str, list[dict]], str]

SlotKey = tuple[int, str]


class MultiAgentSolver:
    def __init__(self, llm: LLM, emit: Callable[[dict], None] | None = None) -> None:
        self.syntax = SyntaxExtractor(llm)
        self.sprinter = Sprinter(llm)
        self.pattern = PatternMatcher(llm)
        self.lateral = LateralThinker(llm)
        self.eraser = Eraser(llm)

        # Optional event sink. When set, every logged action is streamed to it
        # alongside a snapshot of the board's fill at that instant — enough to
        # replay the solve square-by-square (see scripts/record_solve.py).
        self._emit = emit

        # Per-run state (initialized in solve()).
        self.board: AgentBoard | None = None
        self.placements: dict[SlotKey, dict] = {}
        self.log: list[dict] = []
        self.llm_calls = 0
        self._cell_to_slotkeys: dict[tuple[int, int], list[SlotKey]] = {}
        self._attempted: set[tuple[SlotKey, str]] = set()
        self._verbose = False

    # ── public entry points ──────────────────────────────────────────────
    def solve(
        self,
        board: AgentBoard,
        max_rounds: int = 8,
        verbose: bool = False,
    ) -> dict:
        self.board = board
        self.placements = {}
        self.log = []
        self.llm_calls = 0
        self._attempted = set()
        self._verbose = verbose
        self._build_cell_index()

        self._sprinter_pass()

        for _ in range(max_rounds):
            if board.is_complete():
                break
            progress = self._constraint_pass(allow_open=False)
            if progress == 0:
                # Nothing moved with fixed letters; try opening blank slots.
                progress = self._constraint_pass(allow_open=True)
            if progress == 0:
                break

        return {
            "board": board,
            "complete": board.is_complete(),
            "placements": {k: dict(v) for k, v in self.placements.items()},
            "llm_calls": self.llm_calls,
            "log": self.log,
        }

    # ── phases ───────────────────────────────────────────────────────────
    def _sprinter_pass(self) -> None:
        """First pass: only structural gimmes, committed at high confidence.

        Each clue is first run through the Syntax Extractor, turning it into a
        strict grammatical spec. The Sprinter is handed that spec as an absolute
        filter, and the orchestrator independently rejects any answer that breaks
        the required suffix — so the scaffold it lays down is structurally sound.
        """
        targets = [s for s in self.board.slots if classify.is_sprinter_target(s)]
        # Fill-in-the-blanks first, then by length — the surest points up front.
        targets.sort(
            key=lambda s: (0 if classify.is_fill_in_blank(s.clue) else 1, s.length)
        )
        for slot in targets:
            if classify.slot_is_filled(self.board, slot):
                continue
            self.llm_calls += 1
            spec = self.syntax.extract(slot.clue, slot.length)
            self._note(
                self.syntax.name, (slot.number, slot.direction), "spec",
                detail=spec.describe().replace("\n", " ").replace("  ", " "),
            )
            proposal = self._run(self.sprinter, slot, spec=spec)
            if proposal is None:
                continue
            self._consider(slot, proposal, self.sprinter.name, require_high=True, spec=spec)

    def _constraint_pass(self, allow_open: bool) -> int:
        """One sweep of the Pattern Matcher / Lateral Thinker over open slots.

        Returns the number of slots newly placed this sweep.
        """
        progress = 0
        for slot in self.board.slots:
            if classify.slot_is_filled(self.board, slot):
                continue

            if classify.is_wordplay(slot.clue):
                agent = self.lateral
            elif classify.slot_has_partial(self.board, slot) or allow_open:
                agent = self.pattern
            else:
                continue

            proposal = self._run(agent, slot)
            if proposal is None:
                continue
            if self._consider(slot, proposal, agent.name):
                progress += 1
        return progress

    # ── agent invocation ─────────────────────────────────────────────────
    def _run(
        self, agent, slot: Slot, spec: SyntaxSpec | None = None
    ) -> Proposal | None:
        """Call an agent on a slot, skipping unchanged re-attempts.

        A slot is re-attempted only when its pattern has changed since the last
        try with the same agent — otherwise the reply would be identical.
        """
        key = (slot.number, slot.direction)
        pattern = classify.slot_pattern(self.board, slot)
        attempt_key = (key, f"{agent.name}:{pattern}")
        if attempt_key in self._attempted:
            return None
        self._attempted.add(attempt_key)

        self.llm_calls += 1
        if agent is self.sprinter:
            return agent.propose(slot.clue, slot.length, pattern, spec=spec)
        crossings = self._crossing_context(slot)
        return agent.propose(slot.clue, slot.length, pattern, crossings)

    def _consider(
        self,
        slot: Slot,
        proposal: Proposal,
        agent_name: str,
        require_high: bool = False,
        spec: SyntaxSpec | None = None,
    ) -> bool:
        """Validate a proposal and try to place it. Returns True if placed."""
        key = (slot.number, slot.direction)
        if not proposal.committed:
            self._note(agent_name, key, "abstain", reasoning=proposal.reasoning)
            return False

        word = proposal.answer
        if len(word) != slot.length:
            self._note(
                agent_name, key, "reject", word=word,
                detail=f"length {len(word)} != slot {slot.length}",
                confidence=proposal.confidence, reasoning=proposal.reasoning,
            )
            return False
        if require_high and proposal.confidence != "high":
            self._note(
                agent_name, key, "skip-low", word=word,
                detail=f"confidence {proposal.confidence}",
                confidence=proposal.confidence, reasoning=proposal.reasoning,
            )
            return False
        if spec is not None:
            ok, reason = spec_allows(word, spec)
            if not ok:
                # Backstop: the grammatical constraint is non-negotiable.
                self._note(
                    agent_name, key, "reject", word=word, detail=reason,
                    confidence=proposal.confidence, reasoning=proposal.reasoning,
                )
                return False

        return self._place(
            slot, word, proposal.confidence, agent_name, reasoning=proposal.reasoning
        )

    # ── placement & conflict resolution ──────────────────────────────────
    def _place(
        self, slot: Slot, word: str, confidence: str, agent_name: str,
        reasoning: str = "",
    ) -> bool:
        key = (slot.number, slot.direction)
        conflicts = self._conflicts(slot, word)

        if conflicts:
            if not self._resolve_conflicts(slot, word, confidence, agent_name, conflicts):
                return False  # the new word lost — leave the board untouched.

        ok, msg = self.board.write(word, slot.start[0], slot.start[1], slot.direction)
        if not ok:
            self._note(agent_name, key, "reject", word=word, detail=msg)
            return False

        self.placements[key] = {
            "word": word,
            "confidence": confidence,
            "agent": agent_name,
        }
        self._note(
            agent_name, key, "place", word=word, detail=confidence,
            confidence=confidence, reasoning=reasoning,
        )
        return True

    def _resolve_conflicts(
        self,
        slot: Slot,
        word: str,
        confidence: str,
        agent_name: str,
        conflicts: list[tuple],
    ) -> bool:
        """Run the Eraser on each clash. Returns True if the new word may stand.

        For every conflicting crossing answer the Eraser picks a loser. If it
        ever rules against the new word, we abandon the placement. Otherwise we
        clear all the beaten crossing answers and rebuild the board.
        """
        new_key = (slot.number, slot.direction)
        to_clear: set[SlotKey] = set()

        for cell, existing_ch, new_ch, crossing_key in conflicts:
            if crossing_key is None:
                return False  # unattributable letter; do not gamble on it.

            existing = self.placements[crossing_key]
            cross_slot = self.board.slot(*crossing_key)

            self.llm_calls += 1
            verdict = self.eraser.decide(
                a_number=slot.number,
                a_direction=slot.direction,
                a_clue=slot.clue,
                a_word=word,
                a_confidence=confidence,
                b_number=crossing_key[0],
                b_direction=crossing_key[1],
                b_clue=cross_slot.clue,
                b_word=existing["word"],
                b_confidence=existing["confidence"],
                conflict_square=cell,
            )

            if verdict.key == crossing_key:
                to_clear.add(crossing_key)
                self._note(
                    self.eraser.name, crossing_key, "erase",
                    word=existing["word"],
                    detail=f"loses to {new_key[0]}-{new_key[1]} {word}",
                )
            else:
                # New word is the loser (or the Eraser was undecided): keep board.
                self._note(
                    self.eraser.name, new_key, "blocked", word=word,
                    detail=f"kept {crossing_key[0]}-{crossing_key[1]} {existing['word']}",
                )
                return False

        for k in to_clear:
            self.placements.pop(k, None)
        self._rebuild_fill()

        # After clearing, the new word must fit cleanly; bail if anything remains.
        return not self._conflicts(slot, word)

    def _conflicts(self, slot: Slot, word: str) -> list[tuple]:
        """Cells where `word` disagrees with a letter already on the board.

        Each entry is (cell, existing_char, new_char, crossing_slot_key).
        """
        out = []
        skey = (slot.number, slot.direction)
        for cell, ch in zip(slot.cells, word):
            existing = self.board.fill.get(cell)
            if existing is not None and existing != ch:
                out.append((cell, existing, ch, self._owner_of(cell, exclude=skey)))
        return out

    def _owner_of(self, cell: tuple[int, int], exclude: SlotKey) -> SlotKey | None:
        """The placed slot (other than `exclude`) that wrote `cell`, if any."""
        for k in self._cell_to_slotkeys.get(cell, ()):
            if k != exclude and k in self.placements:
                return k
        return None

    def _rebuild_fill(self) -> None:
        """Replay every recorded placement so fill == union of placements."""
        self.board.fill.clear()
        for (number, direction), rec in self.placements.items():
            slot = self.board.slot(number, direction)
            self.board.write(rec["word"], slot.start[0], slot.start[1], direction)

    # ── context helpers ──────────────────────────────────────────────────
    def _build_cell_index(self) -> None:
        index: dict[tuple[int, int], list[SlotKey]] = {}
        for s in self.board.slots:
            for cell in s.cells:
                index.setdefault(cell, []).append((s.number, s.direction))
        self._cell_to_slotkeys = index

    def _crossing_context(self, slot: Slot) -> list[str]:
        """Short descriptions of the perpendicular answers this slot crosses."""
        out: list[str] = []
        seen: set[SlotKey] = set()
        skey = (slot.number, slot.direction)
        for cell in slot.cells:
            for k in self._cell_to_slotkeys.get(cell, ()):
                if k == skey or k in seen:
                    continue
                seen.add(k)
                cross = self.board.slot(*k)
                state = self.board.state_string(cross)
                out.append(f'{k[0]}-{k[1]}: "{cross.clue}" — {state}')
        return out

    def _note(
        self,
        agent: str,
        key: SlotKey,
        action: str,
        word: str | None = None,
        detail: str = "",
        confidence: str | None = None,
        reasoning: str | None = None,
    ) -> None:
        entry = {
            "agent": agent,
            "slot": f"{key[0]}-{key[1]}",
            "action": action,
            "word": word,
            "detail": detail,
        }
        self.log.append(entry)
        if self._verbose:
            w = f" {word}" if word else ""
            d = f" ({detail})" if detail else ""
            print(f"  [{agent:8}] {action:8} {key[0]}-{key[1]}{w}{d}")
        if self._emit is not None:
            # board.fill is always current here: placements are written before
            # the "place" note, and _rebuild_fill() runs before erase notes.
            self._emit({
                **entry,
                "confidence": confidence,
                "reasoning": reasoning,
                "fill": {f"{x},{y}": ch for (x, y), ch in self.board.fill.items()},
            })


def solve_puzzle(llm: LLM, puzzle: dict, **kwargs) -> dict:
    """Convenience wrapper: build a board from a puzzle dict and solve it."""
    board = AgentBoard(puzzle)
    return MultiAgentSolver(llm).solve(board, **kwargs)


def run_episode(
    llm: LLM, puzzle: dict, max_rounds: int = 8, verbose: bool = False
) -> dict:
    """Solve one puzzle and return a benchmark-shaped episode result.

    The returned `grid` is in the grader's format (see `AgentBoard.to_grid`).
    `turns` is the number of model calls made across all agents; this solver uses
    no external tools, so `tool_calls` is 0.
    """
    board = AgentBoard(puzzle)
    result = MultiAgentSolver(llm).solve(board, max_rounds=max_rounds, verbose=verbose)
    return {
        "grid": board.to_grid(),
        "complete": result["complete"],
        "turns": result["llm_calls"],
        "tool_calls": 0,
        "placements": result["placements"],
        "log": result["log"],
    }
