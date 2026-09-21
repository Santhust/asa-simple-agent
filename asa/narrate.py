"""Tiny terminal narrator.

Every run of asa explains itself: color-coded headings, what/how/why annotations,
timings. Honoring the user's mandate — 'verbose outputs, explaining what is happening
at the moment, how it is happening, all the details.'
"""

import os
import sys

_COLORS = {
    "reset": "\033[0m",
    "bold": "\033[1m",
    "dim": "\033[2m",
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
    "cyan": "\033[36m",
}

_NO_COLOR = bool(os.environ.get("NO_COLOR")) or "--no-color" in sys.argv


def _c(code: str, text: str) -> str:
    if _NO_COLOR:
        return text
    return f"{_COLORS[code]}{text}{_COLORS['reset']}"


def h1(text: str) -> None:
    print(_c("cyan", _c("bold", "\n━━━ " + text + " ━━━")))


def h2(text: str) -> None:
    print(_c("blue", _c("bold", "\n▸ " + text)))


def kv(key: str, value: object) -> None:
    print(f"  {_c('dim', key + ':')} {value}")


def info(text: str) -> None:
    print("  " + text)


def why(text: str) -> None:
    """An explanatory aside — the 'why is this happening / next' layer."""
    print(_c("magenta", "  ? " + text))


def ok(text: str) -> None:
    print("  " + _c("green", "✔ " + text))


def warn(text: str) -> None:
    print("  " + _c("yellow", "⚠ " + text))


def err(text: str) -> None:
    print("  " + _c("red", "✘ " + text))


def code(text: str) -> None:
    print(_c("dim", "    " + text))