"""
Pre-built tool implementations available to the agent.

Tools are intentionally kept narrow and stateless so they are fair
across all evaluated models:
  - web_search: DuckDuckGo Instant Answer API (no API key required)
  - define:     Free Dictionary API
"""

import requests

_DDG_URL = "https://api.duckduckgo.com/"
_DICT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"

_TIMEOUT = 8


def web_search(query: str) -> str:
    """Return a short text snippet from DuckDuckGo Instant Answers."""
    try:
        resp = requests.get(
            _DDG_URL,
            params={"q": query, "format": "json", "no_redirect": 1, "no_html": 1},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        abstract = data.get("AbstractText") or data.get("Answer") or ""
        if abstract:
            return abstract[:500]
        related = data.get("RelatedTopics", [])
        if related and isinstance(related[0], dict):
            return related[0].get("Text", "No result found.")[:500]
        return "No result found."
    except Exception as exc:
        return f"Search error: {exc}"


def define(word: str) -> str:
    """Return the first dictionary definition for word."""
    try:
        resp = requests.get(
            _DICT_URL.format(word=word.lower()), timeout=_TIMEOUT
        )
        if resp.status_code == 404:
            return f"No definition found for '{word}'."
        resp.raise_for_status()
        entries = resp.json()
        meanings = entries[0].get("meanings", [])
        if not meanings:
            return "Definition unavailable."
        first = meanings[0]["definitions"][0]
        pos = meanings[0].get("partOfSpeech", "")
        defn = first.get("definition", "")
        example = first.get("example", "")
        result = f"({pos}) {defn}"
        if example:
            result += f' — e.g. "{example}"'
        return result[:400]
    except Exception as exc:
        return f"Dictionary error: {exc}"


def dispatch_tool(tool_name: str, query: str) -> str:
    """Route a TOOL action to the correct implementation."""
    if tool_name == "search":
        return web_search(query)
    if tool_name == "define":
        return define(query)
    return f"Unknown tool: {tool_name!r}"
