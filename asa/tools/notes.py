"""notes — the agent's first STATEFUL hand: a private, numbered ledger.

Pure tools (M3.3) answer without remembering. A stateful tool must keep its
data somewhere between calls, and WHERE it lives is the whole lesson:

1. **The world is data; actions are functions; the world is OUTSIDE both.**
   `NotesStore` is a plain object holding the entries. The two tools below
   are two small functions that know about it by CLOSURE. Nothing global,
   nothing hidden: the store is constructed, visible, and passed in.

2. **Factory-injected store — build() makes a fresh world every time.**
   `build(store=None)` creates a new NotesStore when none is given. So the
   LIFETIME of the notes is the lifetime of the bundle of tools built
   together — which becomes "as long as the agent session lasts".
   Two calls to build() = two independent notebooks; no module globals ever,
   so tests just build anew and stay deterministic.

3. **Stateful tools come as BUNDLES.** M3.3's build() returned one Tool;
   this build() returns a LIST of two — notes_write and notes_read —
   because a store with only a writer can never be verified and one with
   only a reader can never grow. The agent's wiring flattens the bundles.

4. **Identity is the entry NUMBER — stable forever.** Entries are numbered
   monotonically (1, 2, 3…never reused), like the plan-board's ids
   (M3.4's partner lesson). Position in a list is a moving target in a
   mutable world; a number is an identity. No timestamps: notes record WHAT
   was written, and the clock hand already tells the model WHEN.

Failure remains data: wrong types and invented params are refused at the
M3.1 schema boundary before the store is ever touched.
"""

from __future__ import annotations

from asa.tool import Tool, ToolResult


class NotesStore:
    """The ledger: a grow-only list of text entries, numbered 1..n.

    Deliberately tiny. Its only clever trick is returning the entry's
    number on write() — the caller (the tool function) can put identity
    into the Observation without parsing anything back out of the list.
    """

    def __init__(self) -> None:
        self.entries: list[str] = []

    def write(self, text: str) -> int:
        """Append one entry; return its number (1-based, stable forever)."""
        self.entries.append(text)
        return len(self.entries)

    def read(self) -> list[str]:
        """A copy of the ledger — readers cannot mutate the world by aliasing."""
        return list(self.entries)


def _build_tools(store: NotesStore) -> list[Tool]:
    """The two functions that share the store, plus their Tool descriptions."""

    def write(text: str) -> ToolResult:
        number = store.write(text)
        return ToolResult(output=f"note {number} recorded: {text}")

    def read() -> ToolResult:
        entries = store.read()
        if not entries:
            # an empty ledger is a MESSAGE, not an absence — the M3.2 catalogue
            # lesson (never blank) repeated at the tool level:
            return ToolResult(
                output="no notes yet — the ledger is empty; write one with notes_write"
            )
        lines = [f"{i}. {text}" for i, text in enumerate(entries, start=1)]
        return ToolResult(output="notes:\n    " + "\n    ".join(lines))

    return [
        Tool(
            name="notes_write",
            description="Append one note to a private numbered ledger.",
            params={
                "text": {
                    "type": "string",
                    "required": True,
                    "help": "the note to record, e.g. 'idea: cache summaries'",
                }
            },
            func=write,
        ),
        Tool(
            name="notes_read",
            description="Read every note in the ledger, numbered.",
            params={},
            func=read,
        ),
    ]


def build(store: NotesStore | None = None) -> list[Tool]:
    """Two tools sharing one (here-fresh) ledger — the bundle is the unit."""
    return _build_tools(store if store is not None else NotesStore())
