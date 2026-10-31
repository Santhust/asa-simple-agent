"""clock — the agent's read-only window onto the world outside the loop.

The smallest real tool there is, and exactly for that reason it answers three
schema questions the M3.1 mini-schema has not met face-to-face until now:

1. **Read-only, like M3.1 said a tool CAN be.** The clock only LOOKS at the
   environment (wall time); it mutates nothing. Its ToolResult is the first
   Observation that comes from the world rather than from computation — and
   a model reasoning "how long has this been running?" is the fastest way
   to feel why agents want tools at all.

2. **The first REAL optional parameter.** `utc` (boolean, not required) has
   a default the function itself can hold, and the catalogue (M3.2's
   render) will print ``utc (boolean, optional): ...`` — a model reading
   the page now knows a plain call is legal. Required-vs-optional was
   taught with dummy tools in tests; this is the first time it exists in
   the agent's actual hands.

3. **A non-deterministic tool whose tests are still deterministic.** The
   output will never be pinned to a timestamp in tests — we assert the
   SHAPE (ISO-parseable, correct label: ``(local)`` / ``(UTC)``). Golden
   traces in M5 will pin trace STRUCTURE, not wall-clock values; this test
   file is where that philosophy is first written down.

`utc=False` (the default) shows your machine's LOCAL time — on the Pi5
that is whatever `/etc/timezone` says. `utc=True` shows Coordinated
Universal Time: the same instant, one labelled representation. Note what
the tool does NOT offer: it cannot set the time, time-travel, or schedule
anything — read-only means only reads.
"""

from __future__ import annotations

from datetime import datetime, timezone

from asa.tool import Tool, ToolResult

#: The one output format, documented in the description so the catalogue and
#: the function cannot drift apart — the page is rendered from this data.
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _now(utc: bool = False) -> ToolResult:
    """Look at the wall, return the honest stamp — nothing is mutated."""
    if utc:
        stamp = datetime.now(timezone.utc).strftime(_TIME_FORMAT)
        return ToolResult(output=f"{stamp} (UTC)")
    stamp = datetime.now().strftime(_TIME_FORMAT)
    return ToolResult(output=f"{stamp} (local)")


def build() -> Tool:
    """Fresh Tool; the factory pattern shared by every module in asa/tools/."""
    return Tool(
        name="clock",
        description=(
            "Read the current time, formatted"
            f" 'YYYY-MM-DD HH:MM:SS (local)' or '... (UTC)'."
        ),
        params={
            "utc": {
                "type": "boolean",
                "required": False,
                "help": "pass true for UTC; the default is your machine's local time",
            }
        },
        func=_now,
    )
