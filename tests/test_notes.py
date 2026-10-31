"""Tests for the notes tools — the first STATEFUL hand's lessons.

Each test names the lesson it demonstrates and why it matters. Everything
here builds fresh stores via build(), which is the determinism guarantee: no
test can leak state into another, because no state is shared by accident.
"""

from asa.registry import ToolRegistry
from asa.tools.notes import NotesStore, build


def _bundle():
    """One fresh world per test — via the factory, never a global."""
    return build()


def test_write_then_read_roundtrip_with_stable_numbering():
    """Demonstrates the golden path: write returns identity, read shows it.

    Why it matters: the Observation 'note 1 recorded: buy milk' gives the
    model an ADDRESS without re-listing. Numbers are stable forever — the
    identity-vs-position lesson the plan-board will press harder in M4.
    """
    writer, reader = _bundle()
    first = writer.run({"text": "buy milk"})
    second = writer.run({"text": "write agent"})

    assert first.is_error is False
    assert first.output == "note 1 recorded: buy milk"
    assert second.output == "note 2 recorded: buy milk".replace(
        "buy milk", "write agent"
    )  # number grew, never reused

    read_back = reader.run({})
    assert read_back.is_error is False
    assert "1. buy milk" in read_back.output
    assert "2. write agent" in read_back.output


def test_empty_ledger_reads_as_a_message_not_a_blank():
    """Demonstrates the never-blank rule, at the tool level this time.

    Why it matters: M3.2's catalogue had to render a sentence even with no
    tools; an empty ledger must speak too. A blank Observation would make
    the model guess whether its call failed, succeeded, or got truncated —
    the model is left nothing to reason over.
    """
    _, reader = _bundle()
    result = reader.run({})
    assert result.is_error is False  # an empty ledger is not a FAILURE
    assert "no notes yet" in result.output
    assert "notes_write" in result.output  # it names the hand that fixes it


def test_two_tools_share_one_store_by_closure():
    """Demonstrates 'the world is data outside both hands' — notes edition.

    Why it matters: writer and reader are separate tools (separate names,
    separate catalogue entries, separate sections of the model's page) —
    yet the write is INSTANTLY visible to the read because they close over
    the same NotesStore. This is the M3.4 lesson in its smallest form; the
    plan-board repeats it with three hands.
    """
    store = NotesStore()
    bundle_writer, bundle_reader = build(store)
    written = bundle_writer.run({"text": "idea x"})
    assert written.output == "note 1 recorded: idea x"  # the writer's own voice
    assert "1. idea x" in bundle_reader.run({}).output  # same world, other hand


def test_invented_parameter_is_refused_before_the_store_is_touched():
    """Demonstrates the M3.1 schema boundary guarding a STATEFUL tool.

    Why it matters: garbage input must never write to state. Validation
    happens before func is entered, so a typo'd param cannot half-mutate
    the ledger — stateful failure = no state change, plus a readable why.
    """
    writer, _ = _bundle()
    result = writer.run({"text": "x", "max": 5})
    assert result.is_error is True
    assert "unknown argument 'max'" in result.output


def test_wrong_type_is_refused_and_the_numbering_still_starts_at_1():
    """Demonstrates rejected mutation leaves no residue.

    Why it matters: a refused write must not advance the counter — if the
    failed call burned 'note 1', the model's next attempt would record as
    note 2 and Observations would lie about the world. The refus-leaves-
    no-trace rule is easy to forget with stateful tools.
    """
    writer, reader = _bundle()
    bad = writer.run({"text": 5})  # number where text is documented
    assert bad.is_error is True
    assert "expected text" in bad.output

    good = writer.run({"text": "first real note"})
    assert good.output == "note 1 recorded: first real note"  # no burned number


def test_two_built_worlds_are_independent():
    """Demonstrates factory-injected state: build() twice = two notebooks.

    Why it matters: state lifetime = the bundle built together. A second
    agent session (M3.5 wiring) must not read the first's secrets, and
    tests must not share a world by capital accident. No globals anywhere.
    """
    world_a = build()
    world_b = build()
    world_a[0].run({"text": "secret of world a"})
    seen_b = world_b[1].run({})
    assert "secret of world a" not in seen_b.output
    assert "no notes yet" in seen_b.output  # world B never heard of it


def test_factory_shape_and_the_pair_in_a_catalogue():
    """Demonstrates the bundle lands in the phonebook whole.

    Why it matters: M3.5 will flatten bundles into the registry. The two
    names must both exist, sort order must hold, and notes_read (zero
    params) must render with NO Params stub — the M3.2 zero-param rule
    meeting a real stateful tool.
    """
    bundle = build()
    assert [t.name for t in bundle] == ["notes_write", "notes_read"]
    assert bundle[1].params == {}

    registry = ToolRegistry()
    for tool in bundle:
        registry.register(tool)
    text = registry.render_catalogue()
    assert "### notes_write" in text
    assert "### notes_read" in text
    # alphabetically notes_read comes FIRST; everything after the split mark
    # belongs to notes_write (which documents params), everything before it
    # to notes_read (which must not carry a Params stub).
    reader_part, writer_part = text.split("### notes_write")
    assert "Params:" not in reader_part  # reader documents nothing it hasn't
    assert "- text (string, required): the note to record" in writer_part