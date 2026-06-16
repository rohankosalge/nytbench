"""
Clue and slot classification — the routing primitives.

These are pure functions over a clue string or an `(AgentBoard, Slot)` pair. The
orchestrator composes them to decide which specialist should attempt a slot:

  - Sprinter targets are structural: short slots (<=4 letters) and
    fill-in-the-blank clues, where a confident first-pass answer is plausible.
  - Wordplay clues (a trailing "?", an abbreviation, or a theme/example marker)
    route to the Lateral Thinker.
  - Everything else with at least one fixed crossing letter routes to the
    Pattern Matcher.

Keeping these as standalone predicates makes the routing logic testable without
a model in the loop.
"""

from __future__ import annotations

import re

from src.agent.observation import AgentBoard, Slot

SHORT_SLOT_MAX = 4

# A run of two or more underscores, or one or more dashes, is the usual rendering
# of a fill-in-the-blank gap ("___ of my eye", "Pop-up ad, e.g.").
_BLANK_RE = re.compile(r"_{2,}|-{2,}|—{2,}")

# Markers that signal an abbreviated or shortened answer, or an example/theme.
_WORDPLAY_MARKERS = (
    "abbr",
    "for short",
    "briefly",
    "in brief",
    "e.g.",
    "i.e.",
    ": var",
    "informally",
)


def is_fill_in_blank(clue: str) -> bool:
    """True when the clue contains a blank to fill in."""
    return bool(_BLANK_RE.search(clue))


def has_abbreviation_marker(clue: str) -> bool:
    """True when the clue hints the answer is abbreviated or an example."""
    low = clue.lower()
    return any(marker in low for marker in _WORDPLAY_MARKERS)


def is_wordplay(clue: str) -> bool:
    """True for clues that need lateral decoding rather than plain recall.

    A trailing question mark is the canonical pun/double-meaning flag; the
    abbreviation and example markers cover the rest.
    """
    return clue.strip().endswith("?") or has_abbreviation_marker(clue)


def is_short_slot(slot: Slot) -> bool:
    return slot.length <= SHORT_SLOT_MAX


def is_sprinter_target(slot: Slot) -> bool:
    """Structural eligibility for the first pass.

    The Sprinter only *attempts* short slots and fill-in-the-blank clues; its own
    certainty gate (ABSTAIN / required confidence) decides whether it commits.
    Wordplay clues are left for the Lateral Thinker even when short.
    """
    if is_wordplay(slot.clue):
        return False
    return is_short_slot(slot) or is_fill_in_blank(slot.clue)


def slot_pattern(board: AgentBoard, slot: Slot) -> str:
    """Current fill of a slot as a spatial pattern, e.g. 'I P _ _ _'."""
    return board.state_string(slot)


def slot_is_filled(board: AgentBoard, slot: Slot) -> bool:
    """True when every square of the slot already holds a letter."""
    return all(cell in board.fill for cell in slot.cells)


def slot_has_partial(board: AgentBoard, slot: Slot) -> bool:
    """True when the slot has at least one fixed letter and at least one gap."""
    filled = sum(1 for cell in slot.cells if cell in board.fill)
    return 0 < filled < slot.length


def route(board: AgentBoard, slot: Slot) -> str | None:
    """Pick the specialist for an *incomplete* slot during the constraint phase.

    Returns "lateral", "pattern", or None (nothing to do yet — wait for crossings
    to seed a letter). Sprinter routing is handled separately in phase one.
    """
    if slot_is_filled(board, slot):
        return None
    if is_wordplay(slot.clue):
        return "lateral"
    if slot_has_partial(board, slot):
        return "pattern"
    return None
