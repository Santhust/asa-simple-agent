#!/usr/bin/env python3
"""lab/state_lab.py — poke ONE internal: where does state live, who touches it?

Run it:  python lab/state_lab.py

M3.3's tools were pure — nothing to remember. This lab holds the stateful
pair, and every beat circles ONE question: the state lives OUTSIDE the
hands, in injected stores that build() constructs fresh each call.

  1. the ledger   -> notes_write/notes_read: two hands, one NotesStore
  2. the empty    -> an empty ledger still ANSWERS, with an instruction
  3. the board    -> board_add/board_move/board_list: three hands, one Board
                     (ids are stable — 'move item 2' never hits item 4)
  4. the refusals -> unknown status, unknown id: readable words, not a crash
  5. two worlds   -> build() twice = two boards; neither sees the other

Beat 3 is the heart of M3.4: actions are functions, the world is DATA, and
when item 1 moves via board_move, board_list sees it instantly — because
both hands closed over the same store, not because anything was global.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from asa import narrate as N  # noqa: E402
from asa.registry import ToolRegistry  # noqa: E402
from asa.tools.calculator import build as build_calculator  # noqa: E402
from asa.tools.clock import build as build_clock  # noqa: E402
from asa.tools.notes import build as build_notes  # noqa: E402
from asa.tools.plan_board import build as build_board  # noqa: E402


def beat(title: str) -> None:
    N.h2(title)


def show(result, call: str) -> None:
    N.kv("the call", call)
    if result.is_error:
        N.err(f"refused → {result.output}")
    else:
        N.ok(f"answer → {result.output}")


def main() -> None:
    N.h1("asa lab · state — where the stateful hands keep their world")
    N.why(
        "One question only: state lives OUTSIDE the hands, in stores that "
        "build() injects fresh every time. Watch the same data from "
        "different hands, then watch two worlds stay strangers."
    )

    # ---- beat 1 · the ledger: two hands, one store -------------------------
    beat("1 · the ledger — notes_write and notes_read share one NotesStore")
    writer, reader = build_notes()
    show(writer.run({"text": "buy milk"}), "notes_write(text='buy milk')")
    show(writer.run({"text": "sketch the ReAct grammar"}), "notes_write(...)")
    show(reader.run({}), "notes_read()")
    N.why(
        "The reader saw every write INSTANTLY — not by being global, but by "
        "closing over the same store. Identity is the entry number: 1, 2, "
        "never reused, never shifted."
    )
    print()

    # ---- beat 2 · empty is a message, not a blank --------------------------
    beat("2 · the empty ledger — a refusal to stay blank")
    fresh_writer, fresh_reader = build_notes()
    show(fresh_reader.run({}), "notes_read()          # brand-new world")
    N.why(
        "An empty Observation would leave the model guessing. A sentence "
        "that names the fixing hand is something it can act on — M3.2's "
        "'never blank' rule, now at the tool level."
    )
    print()

    # ---- beat 3 · the board: three hands, one world ------------------------
    beat("3 · the board — three faces of one shared mutable world")
    adder, mover, lister = build_board()
    show(adder.run({"item": "draft the M6 trace schema"}), "board_add(item=...)")
    show(adder.run({"item": "fix the parser"}), "board_add(item=...)")
    show(
        mover.run({"item_id": 1, "status": "doing"}),
        "board_move(item_id=1, status='doing')",
    )
    show(lister.run({}), "board_list()")
    N.why(
        "board_list SAW the move board_move made — three separate hands over "
        "one Board. And the item moved BY ID: its position in the todo list "
        "shifted when item 1 left, yet 'item 2' still means the same thing. "
        "Indices would have lied here; ids cannot."
    )
    print()

    # ---- beat 4 · refusals that name their vocabulary ----------------------
    beat("4 · the refusals — a limit the schema cannot say, said anyway")
    show(
        mover.run({"item_id": 1, "status": "history"}),
        "board_move(item_id=1, status='history')",
    )
    show(mover.run({"item_id": 99, "status": "doing"}), "board_move(item_id=99)")
    N.why(
        "The mini-schema knows types but not enums, so the tool checks the "
        "words itself — and names the allowed ones. In M4 this text IS the "
        "self-correction instruction."
    )
    print()

    # ---- beat 5 · two worlds are strangers ---------------------------------
    beat("5 · two worlds — build() twice, no global state anywhere")
    world_a = build_board()
    world_b = build_board()
    world_a[0].run({"item": "world a's plan"})
    show(world_b[2].run({}), "world_b board_list()   # never saw world a")
    N.why(
        "State lifetime = the bundle built together. In M3.5 the wiring "
        "gives each agent ITS OWN world; two agents cannot see each other's "
        "plans, and no test can leak into another."
    )
    print()

    # ---- beat 6 · the whole phonebook --------------------------------------
    beat("6 · the phonebook after M3.4 — seven hands, one manual page")
    registry = ToolRegistry()
    registry.register(build_calculator())
    registry.register(build_clock())
    for tool in build_notes() + build_board():
        registry.register(tool)
    N.kv("tool names", registry.names())
    N.why(
        "Calculator (pure) · clock (read-only) · notes x2 + plan-board x3 "
        "(stateful). The catalogue below is rendered from this data, so it "
        "cannot drift from what runs."
    )
    N.code(registry.render_catalogue().rstrip())
    print()
    N.ok("the world is data, the hands are functions — and nothing is global.")


if __name__ == "__main__":
    main()
