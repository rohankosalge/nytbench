"""
Tests for the multi-agent solver (src.agent.multi).

Covers the pure routing predicates, the reply parsers, each specialist in
isolation, the Eraser's conflict resolution at the placement level, and a full
deterministic solve driven by a clue-keyed fake model — exercising the Sprinter,
Pattern Matcher, and Lateral Thinker end to end with no network.
"""

import pytest

from src.agent.multi import classify
from src.agent.multi.agents import (
    PatternMatcher,
    Sprinter,
    SyntaxExtractor,
    SyntaxSpec,
    parse_proposal,
    parse_syntax_spec,
    parse_verdict,
    spec_allows,
)
from src.agent.multi.orchestrator import MultiAgentSolver, run_episode, solve_puzzle
from src.agent.observation import AgentBoard
from src.evaluation.grader import grade


# ── puzzle fixtures ──────────────────────────────────────────────────────

def _apple_puzzle() -> dict:
    """5x5 grid used for the full solve.

        A P P L E   1-Across: APPLE   3-Across: TESTS
        L . . . A   1-Down:   ALOFT   2-Down:   EARNS
        O . . . R
        F . . . N
        T E S T S
    """
    rows = ["APPLE", "L...A", "O...R", "F...N", "TESTS"]
    solution = list("".join(rows))
    grid = ["." if ch == "." else " " for ch in solution]
    return {
        "width": 5,
        "height": 5,
        "grid": grid,
        "solution": solution,
        "clues_across": {1: "Fruit in the '___ a day' adage", 3: "Standardized ___ in school"},
        "clues_down": {1: "Up in the air", 2: "Hauls in, as a salary?"},
    }


def _grid3() -> dict:
    """3x3 all-white grid for placement/conflict tests.

        C A T   1-Across: CAT   4-Across: ARE   5-Across: RED
        A R E   1-Down: CAR  2-Down: ARE  3-Down: TED
        R E D
    """
    rows = ["CAT", "ARE", "RED"]
    solution = list("".join(rows))
    grid = [" "] * 9
    return {
        "width": 3,
        "height": 3,
        "grid": grid,
        "solution": solution,
        "clues_across": {1: "Feline", 4: "They ___ here", 5: "Crimson"},
        "clues_down": {1: "Auto", 2: "Conjugation of 'to be'", 3: "Inspiring talks brand?"},
    }


# ── fake models ──────────────────────────────────────────────────────────

class ClueKeyedLLM:
    """Returns a canned reply chosen by a substring of the user message."""

    def __init__(self, routes: dict[str, str]) -> None:
        self._routes = routes
        self.calls = 0

    def __call__(self, system: str, messages: list[dict]) -> str:
        self.calls += 1
        # Match only the primary `Clue: "..."` line so neighboring clues listed
        # as crossing context never trigger the wrong route.
        clue_line = messages[-1]["content"].splitlines()[0]
        for needle, reply in self._routes.items():
            if needle in clue_line:
                return reply
        return "ABSTAIN"


def _fixed(reply: str):
    def _llm(system, messages):
        return reply
    return _llm


class RoleKeyedLLM:
    """Returns a canned reply chosen by which specialist's prompt is calling.

    Keys are matched against the system prompt (e.g. "Syntax Extractor",
    "Sprinter"), so a single fake can drive the extractor -> sprinter handoff.
    """

    def __init__(self, by_role: dict[str, str]) -> None:
        self._by_role = by_role

    def __call__(self, system: str, messages: list[dict]) -> str:
        for needle, reply in self._by_role.items():
            if needle in system:
                return reply
        return "ABSTAIN"


def _single_slot_puzzle(solution_word: str, clue: str) -> dict:
    """A 1xN all-white grid with a single Across slot."""
    n = len(solution_word)
    return {
        "width": n,
        "height": 1,
        "grid": [" "] * n,
        "solution": list(solution_word),
        "clues_across": {1: clue},
        "clues_down": {},
    }


# ── classification / routing ─────────────────────────────────────────────

def test_fill_in_blank_detection():
    assert classify.is_fill_in_blank("Apple of one's ___")
    assert classify.is_fill_in_blank("___ a day keeps the doctor away")
    assert not classify.is_fill_in_blank("Fruit on a tree")


def test_wordplay_detection():
    assert classify.is_wordplay("Org. with a famous deep field?")  # trailing ?
    assert classify.is_wordplay("Lab worker, for short")           # abbreviation marker
    assert classify.is_wordplay("Pres. between FDR and JFK: Abbr.")
    assert not classify.is_wordplay("Capital of France")


def test_sprinter_targets_are_short_or_fill_in_blank_and_not_wordplay():
    board = AgentBoard(_grid3())
    by = {(s.number, s.direction): s for s in board.slots}
    assert classify.is_sprinter_target(by[(1, "across")])   # short
    assert classify.is_sprinter_target(by[(4, "across")])   # fill-in-blank
    assert not classify.is_sprinter_target(by[(3, "down")])  # wordplay "...?"


def test_route_waits_for_a_crossing_letter():
    board = AgentBoard(_apple_puzzle())
    one_down = board.slot(1, "down")
    # Empty board: a plain clue with no fixed letters has nothing to match yet.
    assert classify.route(board, one_down) is None
    # Seed a crossing letter; now it routes to the Pattern Matcher.
    board.write("APPLE", 1, 1, "across")
    assert classify.route(board, one_down) == "pattern"
    # A "?" clue always routes to the Lateral Thinker.
    assert classify.route(board, board.slot(2, "down")) == "lateral"


# ── reply parsing ────────────────────────────────────────────────────────

def test_parse_proposal_with_confidence():
    p = parse_proposal("ANSWER: APPLE\nCONFIDENCE: high")
    assert p.answer == "APPLE" and p.confidence == "high" and p.committed


def test_parse_proposal_abstain():
    p = parse_proposal("ABSTAIN")
    assert p.answer is None and not p.committed and p.confidence == "none"


def test_parse_proposal_defaults_to_low_confidence():
    p = parse_proposal("ANSWER: oreo")
    assert p.answer == "OREO" and p.confidence == "low"


def test_parse_verdict():
    v = parse_verdict("CLEAR: 1 down")
    assert v.key == (1, "down")
    assert parse_verdict("nope").key is None


# ── specialists in isolation ─────────────────────────────────────────────

def test_sprinter_commits_high_confidence():
    sprinter = Sprinter(_fixed("ANSWER: CAT\nCONFIDENCE: high"))
    p = sprinter.propose("Feline", 3)
    assert p.answer == "CAT" and p.confidence == "high"


def test_pattern_matcher_fits_pattern():
    pm = PatternMatcher(_fixed("ANSWER: ALOFT\nCONFIDENCE: high"))
    p = pm.propose("Up in the air", 5, "A _ _ _ T")
    assert p.answer == "ALOFT"


# ── eraser conflict resolution at the placement level ────────────────────

def test_eraser_clears_weaker_existing_word():
    """A strong crossing answer evicts the weaker word already on the board."""
    solver = MultiAgentSolver(_fixed("CLEAR: 1 down"))
    board = AgentBoard(_grid3())
    solver.board = board
    solver._build_cell_index()

    # Weak guess goes down first: 1-Down = COT (C O T).
    assert solver._place(board.slot(1, "down"), "COT", "medium", "sprinter")
    assert board.fill[(1, 2)] == "O"

    # Strong crossing answer 4-Across = ARE clashes at (1,2). Eraser clears COT.
    assert solver._place(board.slot(4, "across"), "ARE", "high", "sprinter")
    assert (1, "down") not in solver.placements      # weak word evicted
    assert (4, "across") in solver.placements
    assert board.fill[(1, 2)] == "A"                 # rebuilt with the winner
    assert (1, 1) not in board.fill                  # COT's other cells gone


def test_eraser_blocks_weaker_new_word():
    """When the new word is the weaker one, the board is left untouched."""
    solver = MultiAgentSolver(_fixed("CLEAR: 1 down"))
    board = AgentBoard(_grid3())
    solver.board = board
    solver._build_cell_index()

    # Strong answer first: 4-Across = ARE.
    assert solver._place(board.slot(4, "across"), "ARE", "high", "sprinter")
    # Weak crossing 1-Down = COT clashes; Eraser rules against the new word.
    assert not solver._place(board.slot(1, "down"), "COT", "medium", "sprinter")
    assert (1, "down") not in solver.placements
    assert board.fill[(1, 2)] == "A"                 # untouched winner


# ── full solve ───────────────────────────────────────────────────────────

def test_full_solve_uses_all_three_solver_roles():
    llm = ClueKeyedLLM({
        "a day": "ANSWER: APPLE\nCONFIDENCE: high",          # 1-Across, Sprinter
        "Standardized": "ANSWER: TESTS\nCONFIDENCE: high",   # 3-Across, Sprinter
        "Up in the air": "ANSWER: ALOFT\nCONFIDENCE: high",  # 1-Down, Pattern
        "salary": (                                          # 2-Down, Lateral
            "The clue puns on earning a paycheck.\n"
            "ANSWER: EARNS\nCONFIDENCE: high"
        ),
    })
    result = solve_puzzle(llm, _apple_puzzle())

    assert result["complete"] is True
    board = result["board"]
    expected = _apple_puzzle()["solution"]
    for y in range(1, 6):
        for x in range(1, 6):
            if not board.is_black(x, y):
                idx = (y - 1) * 5 + (x - 1)
                assert board.fill[(x, y)] == expected[idx]

    agents_used = {entry["agent"] for entry in result["log"] if entry["action"] == "place"}
    assert agents_used == {"sprinter", "pattern", "lateral"}
    assert result["llm_calls"] > 0


# ── syntax extraction ────────────────────────────────────────────────────

def test_parse_syntax_spec():
    spec = parse_syntax_spec(
        "PART_OF_SPEECH: verb\nTENSE: present\nPLURAL: false\nREQUIRED_SUFFIX: -s"
    )
    assert spec.part_of_speech == "verb"
    assert spec.tense == "present"
    assert spec.plural is False
    assert spec.required_suffix == "S"


def test_parse_syntax_spec_defaults_on_garbage():
    spec = parse_syntax_spec("I cannot help with that")
    assert spec.part_of_speech == "other"
    assert spec.required_suffix == ""  # no constraint imposed


def test_spec_allows_required_suffix():
    spec = SyntaxSpec(required_suffix="S")
    ok, _ = spec_allows("BOLT", spec)
    assert ok is False           # fails the -s filter
    assert spec_allows("DARTS", spec)[0] is True
    # An empty suffix constraint accepts anything.
    assert spec_allows("BOLT", SyntaxSpec())[0] is True


def test_syntax_extractor_returns_spec():
    extractor = SyntaxExtractor(
        _fixed("PART_OF_SPEECH: verb\nTENSE: present\nPLURAL: false\nREQUIRED_SUFFIX: -s")
    )
    spec = extractor.extract("Leaves in a hurry", 5)
    assert spec.required_suffix == "S" and spec.part_of_speech == "verb"


def test_sprinter_rejects_suffix_violation():
    """The grammatical backstop blocks a structurally wrong scaffold letter."""
    llm = RoleKeyedLLM({
        "Syntax Extractor": "PART_OF_SPEECH: verb\nTENSE: present\nPLURAL: false\nREQUIRED_SUFFIX: -s",
        # The Sprinter ignores the suffix and proposes a non-S word (the BOLT case).
        "Sprinter": "ANSWER: BOLT\nCONFIDENCE: high",
    })
    result = solve_puzzle(llm, _single_slot_puzzle("ZIPS", "Hurries off, slangily"))
    assert (1, "across") not in result["placements"]   # rejected, nothing placed
    assert not result["board"].fill
    assert any(e["action"] == "reject" and "suffix" in e["detail"] for e in result["log"])


def test_sprinter_accepts_suffix_compliant_word():
    llm = RoleKeyedLLM({
        "Syntax Extractor": "PART_OF_SPEECH: verb\nTENSE: present\nPLURAL: false\nREQUIRED_SUFFIX: -s",
        "Sprinter": "ANSWER: ZIPS\nCONFIDENCE: high",
    })
    result = solve_puzzle(llm, _single_slot_puzzle("ZIPS", "Hurries off, slangily"))
    assert result["placements"][(1, "across")]["word"] == "ZIPS"
    assert result["complete"] is True


# ── benchmark episode runner ─────────────────────────────────────────────

def test_run_episode_grades_as_solved():
    llm = ClueKeyedLLM({
        "a day": "ANSWER: APPLE\nCONFIDENCE: high",
        "Standardized": "ANSWER: TESTS\nCONFIDENCE: high",
        "Up in the air": "ANSWER: ALOFT\nCONFIDENCE: high",
        "salary": "Pun on a paycheck.\nANSWER: EARNS\nCONFIDENCE: high",
    })
    puzzle = _apple_puzzle()
    episode = run_episode(llm, puzzle)

    assert episode["complete"] is True
    assert episode["tool_calls"] == 0
    assert episode["turns"] > 0
    result = grade(episode["grid"], puzzle["solution"])
    assert result["solved"] is True
    assert result["fill_rate"] == 1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
