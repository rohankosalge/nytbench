"""
Generic, model-agnostic system prompt for the NYT-Agent.

Deliberately written in plain English with no model-specific XML tags or
chain-of-thought directives, so the same prompt is fair across all evaluated
models.
"""


def build_system_prompt(puzzle: dict) -> str:
    date_str = puzzle.get("date", "unknown")
    weekday = puzzle.get("weekday", "unknown")
    width = puzzle.get("width", "?")
    height = puzzle.get("height", "?")

    return f"""You are solving a New York Times crossword puzzle published on {date_str} ({weekday}).
The grid is {width} columns wide and {height} rows tall.

Your goal is to fill every white square with the correct letter by writing answers to the clues.

You have exactly three actions available. Output one action per turn in the following plain-text format:

  GET_CLUE <direction> <number>
      Retrieves the clue text for a specific word.
      Example: GET_CLUE across 14

  WRITE <direction> <number> <answer>
      Fills in an answer on the board.
      Example: WRITE down 7 PRISM

  ERASE <direction> <number>
      Removes a previously written answer so you can try again.
      Example: ERASE across 22

Rules:
- <direction> is either "across" or "down" (lowercase).
- <number> is the integer clue number shown on the board.
- <answer> must be a single word containing only letters A-Z (no spaces or hyphens).
- You may use a web search or dictionary tool by responding with:
      TOOL search "<your query>"
  or
      TOOL define "<word>"
- Always retrieve a clue before attempting to write an answer for it.
- Crossing letters already on the board are constraints — respect them.
- When you believe the puzzle is complete, output: DONE
"""


SYSTEM_PROMPT_BRIEF = """Solve the crossword. Use GET_CLUE, WRITE, ERASE, or TOOL. Output one action per turn."""
