"""plan_board — the SHARED world: three tools over one mutable board.

The counterpoint to notes.py (one private ledger, two hands). Here THREE
distinct tools — board_add, board_move, board_list — all close over the SAME
Board object, so one hand's effect is immediately visible to the others.
That is what "shared mutable" means, made literal in five lines:

    board = Board()
    tools = build(board)   # three different hands, one world

1. **Stable ids, never indices.** board_move addresses items by a monotonic
   id (1, 2, 3… never reused). Why not list indices? Because indices are
   POSITIONS: the moment an item moves, every index after it shifts, and
   "move item 2" would hit a different item — the classic mutable-state
   identity bug. Two lines of counter buy identity that survives motion.
   (notes.py carries the sibling lesson for entries.)

2. **The status vocabulary is the TOOL's business.** The M3.1 mini-schema
   knows types but not enums, so "todo/doing/done" (and "all" for
   board_list) is checked by the tool functions — with readable refusals
   that list the words the model is allowed to use. Same shape as the
   calculator's length caps: a limit the schema cannot say is placed at
   the boundary the model can learn from.

3. **One shared store, built by ONE factory.** build() returns the three
   tools as one bundle precisely because they are meaningless apart: an
   adder nobody lists, a mover nobody added to, a lister of nobody's
   world. Splitting them into separate modules would let them drift apart
   and then pretend to be independent.

4. **`integer` finally gets a real job.** board_move's id is the first
   genuine INTEGER parameter of the agent (M3.1 defined the type; the
   schema boundary rejects bools and floats before the board ever sees
   them). The Observation says the id back every time — "item 2 moved" —
   so a model can chain its next turn without re-listing.

Failure remains data everywhere: unknown id → readable (and names the ids
that exist); unknown status → readable (and names the vocabulary); wrong
types → refused at the schema boundary.
"""

from __future__ import annotations

from asa.tool import Tool, ToolResult

#: The board's whole vocabulary — printed in every refusal that needs it.
_STATUSES = ("todo", "doing", "done")
#: board_list's fourth word: "status=all" renders the three columns in order.
_VIEW_WORD = "all"
_ALLOWED_STATUSES = _STATUSES + (_VIEW_WORD,)


class Board:
    """Three columns and a next-id counter; ids identify forever.

    The store is deliberately plain: a text per id, a place per id, an
    insertion order per column. Nothing clever — the LESSON must stay
    visible: identity, place, order. (Empty columns render as "(empty)" —
    readable by the same philosophy as notes' empty ledger.)
    """

    def __init__(self) -> None:
        self._next_id = 1
        self._text: dict[int, str] = {}          # id → what the item is
        self._place: dict[int, str] = {}         # id → which column it's in
        self._columns: dict[str, list[int]] = {s: [] for s in _STATUSES}

    def add(self, text: str) -> int:
        """Create the item in 'todo'; return its brand-new stable id."""
        item_id = self._next_id
        self._next_id += 1
        self._text[item_id] = text
        self._place[item_id] = "todo"
        self._columns["todo"].append(item_id)
        return item_id

    def move(self, item_id: int, status: str) -> tuple[str, str, str]:
        """Take item `item_id` to column `status`; say the whole story back.

        Returns (text, from_status, to_status) so the tool function can
        phrase "item 2 moved from todo to doing: buy milk" without
        re-deriving anything. Raises ValueError with a HUMAN message for
        unknown ids or unknown statuses — caught by the tool function and
        re-issued as ToolResult(is_error=True) data.
        """
        if status not in _STATUSES:
            raise ValueError(
                f"unknown status {status!r} — I only know todo, doing, done"
            )
        if item_id not in self._text:
            known = ", ".join(str(i) for i in self._text) or "none yet"
            raise ValueError(f"no item {item_id} on the board — open ids: {known}")
        old_place = self._place[item_id]
        self._columns[old_place].remove(item_id)  # identity survives motion
        self._columns[status].append(item_id)
        self._place[item_id] = status
        return self._text[item_id], old_place, status

    def render(self, view: str = _VIEW_WORD) -> str:
        """The board as text: three columns in vocabulary order, ids inline."""
        wanted = list(_STATUSES) if view == _VIEW_WORD else [view]
        lines = []
        for status in wanted:
            ids = self._columns[status]
            if ids:
                items = ", ".join(
                    f"{i} {self._text[i]}" for i in ids
                )
                lines.append(f"  {status}: {items}")
            else:
                lines.append(f"  {status}: (empty)")
        return "\n".join(lines)

    def ids(self) -> list[int]:
        """Every open id, ascending — what a refusal can legitimately offer."""
        return list(self._text)


def _build_tools(board: Board) -> list[Tool]:
    """Three tools, one world — the bundle that must not be split."""

    def add(item: str) -> ToolResult:
        item_id = board.add(item)
        return ToolResult(output=f"item {item_id} added to todo: {item}")

    def move(item_id: int, status: str) -> ToolResult:
        try:
            text, old_place, new_place = board.move(item_id, status)
        except ValueError as exc:
            # the store's WHY becomes the model's READABLE text, verbatim
            return ToolResult(output=f"board_move: {exc}", is_error=True)
        return ToolResult(
            output=(
                f"item {item_id} moved from {old_place} to {new_place}: {text}"
            )
        )

    def list_board(status: str = _VIEW_WORD) -> ToolResult:
        if status not in _ALLOWED_STATUSES:
            return ToolResult(
                output=(
                    "board_list: unknown view "
                    f"{status!r} — I know todo, doing, done, or 'all'"
                ),
                is_error=True,
            )
        return ToolResult(output="the board:\n" + board.render(status))

    return [
        Tool(
            name="board_add",
            description="Add one item to a shared plan board; it lands in 'todo'.",
            params={
                "item": {
                    "type": "string",
                    "required": True,
                    "help": "what to plan, e.g. 'draft the M6 trace schema'",
                }
            },
            func=add,
        ),
        Tool(
            name="board_move",
            description="Move a planned item between columns, by its stable id.",
            params={
                "item_id": {
                    "type": "integer",
                    "required": True,
                    "help": "the id printed when the item was added",
                },
                "status": {
                    "type": "string",
                    "required": True,
                    "help": "the destination column: todo, doing, or done",
                },
            },
            func=move,
        ),
        Tool(
            name="board_list",
            description="Read the shared plan board (all columns, or one).",
            params={
                "status": {
                    "type": "string",
                    "required": False,
                    "help": "restrict the view to todo, doing, done; default 'all'",
                }
            },
            func=list_board,
        ),
    ]


def build(board: Board | None = None) -> list[Tool]:
    """Three tools sharing one (here-fresh) board — the bundle is the unit.

    Two calls to build() are two boards: the second world cannot see the
    first one's items, which is exactly what keeps tests and future
    agent sessions isolated.
    """
    return _build_tools(board if board is not None else Board())
