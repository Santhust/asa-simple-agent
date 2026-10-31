"""Tests for the plan-board — THREE hands over ONE shared world.

Each test names the lesson it demonstrates and why it matters. The suite's
center of gravity is test_add_move_and_list_are_three_faces_of_one_world:
separate tools, separate catalogue entries, one store they all close over.
"""

import pytest

from asa.registry import ToolRegistry
from asa.tools.calculator import build as build_calculator
from asa.tools.clock import build as build_clock
from asa.tools.notes import build as build_notes
from asa.tools.plan_board import Board, build


def _trio():
    """One fresh world per test — always through the factory."""
    return build()


def test_add_lands_in_todo_and_returns_a_stable_id():
    """Demonstrates the golden add: identity given, not position implied.

    Why it matters: 'item 1 added to todo' hands the model an ADDRESS that
    survives every later move. ids never repeat and never shift — that is
    the whole anti-index lesson in one Observation.
    """
    adder, _, lister = _trio()
    first = adder.run({"item": "draft the M6 trace schema"})
    second = adder.run({"item": "fix the parser"})

    assert first.is_error is False
    assert first.output == "item 1 added to todo: draft the M6 trace schema"
    assert second.output == "item 2 added to todo: fix the parser"

    board_text = lister.run({}).output
    assert "todo: 1 draft the M6 trace schema, 2 fix the parser" in board_text


def test_move_by_id_and_the_old_column_loses_the_item():
    """Demonstrates motion with identity intact.

    Why it matters: 'item 1 moved from todo to doing' says WHO moved, FROM
    where, TO where — a complete story a model can reason over and confirm.
    The todo column must lose the id the moment doing gains it: one item,
    one place, or the board is lying.
    """
    adder, mover, lister = _trio()
    adder.run({"item": "draft the M6 trace schema"})

    moved = mover.run({"item_id": 1, "status": "doing"})
    assert moved.is_error is False
    assert moved.output == (
        "item 1 moved from todo to doing: draft the M6 trace schema"
    )

    board_text = lister.run({}).output
    assert "doing: 1 draft the M6 trace schema" in board_text
    assert "todo: (empty)" in board_text


def test_ids_stay_the_same_after_moves_the_anti_index_guarantee():
    """Demonstrates identity surviving motion — the decision the map took.

    Why it matters: with list indices, moving one item would renumber
    everything behind it, and the model's second action would act on the
    WRONG item. Here the model can move item 2, then still say 'item 2'
    with absolute certainty. Position would be a trap; identity is not.
    """
    adder, mover, lister = _trio()
    for item in ("paint it red", "paint it blue", "paint it green"):
        adder.run({"item": item})

    mover.run({"item_id": 2, "status": "doing"})  # middle item leaves todo
    board_text = lister.run({}).output
    assert "todo: 1 paint it red, 3 paint it green" in board_text

    # the remaining item is STILL named by its original id, even though
    # its position in the todo list has shifted from [2nd] to [1st]:
    again = mover.run({"item_id": 3, "status": "done"})
    assert "item 3 moved from todo to done: paint it green" in again.output


def test_unknown_status_is_a_readable_refusal_that_names_the_vocabulary():
    """Demonstrates the enum the mini-schema cannot express, checked in tool.

    Why it matters: 'history' is plausible-sounding; the model needs the
    ALLOWED words to self-correct in one turn. The refusal is phrased with
    the exact vocabulary — the same pattern as the calculator's caps: a
    limit the schema can't say is pushed to the boundary that CAN.
    """
    _, mover, _ = _trio()
    result = mover.run({"item_id": 1, "status": "history"})
    assert result.is_error is True
    assert "unknown status 'history'" in result.output
    assert "todo, doing, done" in result.output


def test_unknown_id_is_a_readable_refusal_that_names_the_open_ids():
    """Demonstrates the helpful-miss refusal.

    Why it matters: movable ids change as the world grows; a stale id (or a
    hallucinated one) is the M4 era's everyday error. Naming the ids that
    exist turns the dead end into a hint — failure is data, embedded in a
    stateful refusal.
    """
    adder, mover, _ = _trio()
    adder.run({"item": "draft the M6 trace schema"})
    result = mover.run({"item_id": 99, "status": "doing"})
    assert result.is_error is True
    assert "no item 99 on the board" in result.output
    assert "open ids: 1" in result.output


def test_board_list_optional_status_view_and_its_manual_vocabulary():
    """Demonstrates the second real optional param AND the fourth word.

    Why it matters: board_list's status is optional ('all' default) — a
    model reading the catalogue knows a plain call is legal. And 'all' is
    a VIEW word, not a column: a model that moves an item to 'all' must
    meet the vocabulary refusal, not a quiet no-op. views vs statuses is
    exactly the distinction a lazy schema would blur.
    """
    adder, mover, lister = _trio()
    adder.run({"item": "draft the M6 trace schema"})
    mover.run({"item_id": 1, "status": "done"})

    done_view = lister.run({"status": "done"})
    assert done_view.is_error is False
    assert "done: 1 draft the M6 trace schema" in done_view.output
    assert "todo" not in done_view.output  # one column only, as asked

    bunk_view = lister.run({"status": "backlog"})
    assert bunk_view.is_error is True
    assert "todo, doing, done, or 'all'" in bunk_view.output


def test_wrong_types_are_refused_by_the_true_integer_param():
    """Demonstrates 'integer' earning its keep — the first real int param.

    Why it matters: M3.1 defined the integer type and its bool exception;
    here a model sending 2.5 or true for item_id meets a refusal BEFORE
    the board mutates. Types at the boundary are what make the store's
    casts unnecessary — the store can trust its ids.
    """
    adder, mover, _ = _trio()
    adder.run({"item": "draft the M6 trace schema"})

    assert mover.run({"item_id": 2.5, "status": "doing"}).is_error is True
    assert mover.run({"item_id": True, "status": "doing"}).is_error is True
    assert mover.run({"item_id": "1", "status": "doing"}).is_error is True
    # none of those reached the store:
    assert mover.run({"item_id": 1, "status": "doing"}).is_error is False


def test_add_move_and_list_are_three_faces_of_one_world():
    """Demonstrates the SUITE'S core: three tools, one shared mutable world.

    Why it matters: board_add/board_move/board_list are separate hands —
    separate catalogue sections the model reads as separate capabilities —
    yet one add is instantly visible to the other two, because all three
    close over the same Board. Actions are functions; the world is data
    OUTSIDE the hands. When M4's loop lets a model act three turns in a
    row, this is the machinery underneath every consecutive turn.
    """
    adder, mover, lister = _trio()
    assert adder.run({"item": "step one"}).is_error is False
    assert "step one" in lister.run({}).output  # the lister SAW the adder's write
    assert mover.run({"item_id": 1, "status": "done"}).is_error is False
    assert "done: 1 step one" in lister.run({}).output  # and the mover's
    assert "todo: (empty)" in lister.run({}).output


def test_store_is_plain_and_builds_two_independent_worlds():
    """Demonstrates the Board is plain data + factories make private worlds.

    Why it matters: the M3.4 decisions — state outside the hands,
    factory-injected, never global — are pinned: Board is a boring, named,
    hand-readable structure; two builds are two boards; and the SECOND
    world cannot see the first one's items, which is what will keep
    M3.5's agent sessions from bleeding into each other.
    """
    board = Board()
    assert board.ids() == []
    board.add("x")
    assert board.ids() == [1]

    trio_a = build()
    trio_b = build()
    trio_a[0].run({"item": "world a's item"})
    result_b = trio_b[2].run({})
    assert "world a's item" not in result_b.output
    assert "(empty)" in result_b.output


def test_factory_shape_and_all_five_hands_in_one_catalogue():
    """Demonstrates the flattened phonebook after M3.4: seven tool entries.

    Why it matters: calculator + clock + notes(2) + plan-board(3) is the
    whole toolbox M3.5's wiring will hand M4's loop. The catalogue must
    hold all seven, sorted by name (registry rule), with board_move's id
    documented as integer — the page and the hands cannot drift.
    """
    registry = ToolRegistry()
    registry.register(build_calculator())
    registry.register(build_clock())
    for tool in build_notes() + build():
        registry.register(tool)

    assert registry.names() == [
        "board_add",
        "board_list",
        "board_move",
        "calculator",
        "clock",
        "notes_read",
        "notes_write",
    ]
    catalogue = registry.render_catalogue()
    for name in ("calculator", "clock", "board_add", "notes_write"):
        assert f"### {name}" in catalogue
    assert "- item_id (integer, required): the id printed when the item was added" in catalogue
    assert "- text (string, required): the note to record" in catalogue