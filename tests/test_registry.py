"""Tests for the ToolRegistry — proving the four M3.2 lessons.

Each test names the lesson it demonstrates and why it matters for the agent
loop that M3.5/M4 will build on top of this.
"""

import pytest

from asa.registry import ToolRegistry
from asa.tool import Tool, ToolResult


def _adder() -> Tool:
    """A tiny well-behaved tool: adds two numbers (same helper as test_tool)."""

    def add(a: float, b: float) -> ToolResult:
        return ToolResult(output=f"{a} + {b} = {a + b}")

    return Tool(
        name="add",
        description="Add two numbers.",
        params={
            "a": {"type": "number", "required": True, "help": "first addend"},
            "b": {"type": "number", "required": True, "help": "second addend"},
        },
        func=add,
    )


def _clock() -> Tool:
    """A second tool with NO params, for order/rendering edge cases."""

    def now() -> ToolResult:
        return ToolResult(output="12:00")

    return Tool(name="clock", description="Read the current time.", params={}, func=now)


def _notetaker() -> Tool:
    """A tool with one required + one optional param, for the catalogue test."""

    def write(note: str, author: str = "anonymous") -> ToolResult:
        return ToolResult(output=f"{author} wrote: {note}")

    return Tool(
        name="notes",
        description="Keep short notes and read them back.",
        params={
            "note": {"type": "string", "required": True, "help": "text to append"},
            "author": {"type": "string", "required": False, "help": "who wrote it"},
        },
        func=write,
    )


# ---- Group A · the phonebook: register / get / names / in / len ------------


def test_register_and_get_returns_the_same_object():
    """Demonstrates that the registry stores references, not copies.

    Why it matters: the M4 loop will resolve a name and then run THAT Tool.
    If get() handed back a copy, a re-registered or configured tool could
    silently diverge from the one the builder registered. Identity is the
    guarantee: resolve -> run uses exactly what was registered.
    """
    registry = ToolRegistry()
    tool = _adder()
    registry.register(tool)
    assert registry.get("add") is tool


def test_get_unknown_name_returns_none_not_an_exception():
    """Demonstrates: a missed lookup is DATA (model-time miss), not a crash.

    Why it matters: the model WILL typo tool names. Returning None lets M4
    compose a readable Observation ("no tool named 'claculator'") the model
    can self-correct from — the failure-is-data philosophy, deferred one
    layer up so the registry itself never has to phrase model-facing text.
    """
    registry = ToolRegistry()
    registry.register(_adder())
    assert registry.get("claculator") is None
    assert registry.get("") is None


def test_duplicate_registration_raises_valueerror():
    """Demonstrates: a duplicate registration is OUR build-time bug — loud.

    Why it matters: the mirror image of the previous test. Model-time misses
    are quiet data; our own bugs explode in tests. Silent shadowing would
    strand one of two same-named tools where nothing could ever call it —
    and everything would still look like it "works".
    """
    registry = ToolRegistry()
    registry.register(_adder())
    with pytest.raises(ValueError) as excinfo:
        registry.register(_adder())  # same name again, a build-time bug
    # the message must say BOTH what collided and what the squatter is
    assert "add" in str(excinfo.value)


def test_names_are_sorted_regardless_of_registration_order():
    """Demonstrates: the listing is sorted, cooking registration order away.

    Why it matters: registration order is an accident of the builder's code.
    If it leaked into the prompt or listings, identical tool sets would give
    differently-ordered output — and M5's golden-trace tests would get
    painful for no reason. Determinism is built here.
    """
    registry = ToolRegistry()
    registry.register(_clock())    # alphabetically LATER, registered FIRST
    registry.register(_adder())    # alphabetically first, registered second
    assert registry.names() == ["add", "clock"]


def test_len_and_contains_read_naturally():
    """Demonstrates the small ergonomics for narrations and tests.

    Why it matters: upcoming narrations want to say '3 tools · "add" in
    registry'. Pinned here so the promised Python-isms never surprise anyone.
    """
    registry = ToolRegistry()
    assert len(registry) == 0
    assert "add" not in registry
    registry.register(_adder())
    assert len(registry) == 1
    assert "add" in registry


# ---- Group B · the manual page: render_catalogue ---------------------------


def test_catalogue_documents_name_description_and_params():
    """Demonstrates documentation-first: the catalogue is rendered FROM the tool.

    Why it matters: this page is the ONLY knowledge the model will ever have
    of its capabilities (it lands in the system prompt in M3.5). It must
    carry the Tool's name, its description, and every param as declared —
    schema-data becomes prompt-text, so the two can never drift apart.
    """
    registry = ToolRegistry()
    registry.register(_adder())
    text = registry.render_catalogue()
    assert "### add" in text
    assert "Add two numbers." in text
    assert "- a (number, required): first addend" in text
    assert "- b (number, required): second addend" in text


def test_catalogue_distinguishes_required_from_optional_params():
    """Demonstrates the catalogue cannot lie about the schema it renders.

    Why it matters: a model reading this decides what a VALID call looks
    like. Optional params must be marked optional (not silently presented as
    required) so the model's first attempt is already schema-correct.
    """
    registry = ToolRegistry()
    registry.register(_notetaker())
    text = registry.render_catalogue()
    assert "- note (string, required): text to append" in text
    assert "- author (string, optional): who wrote it" in text


def test_catalogue_tool_without_params_has_no_params_section():
    """Demonstrates the empty-params rendering edge.

    Why it matters: a zero-param tool must not print a naked "Params:" stub —
    a dangling header would be page noise the model reads as a (false)
    promise of parameters to come.
    """
    registry = ToolRegistry()
    registry.register(_clock())
    text = registry.render_catalogue()
    assert "### clock" in text
    assert "Params:" not in text


def test_catalogue_empty_registry_is_a_paragraph_not_an_empty_string():
    """Demonstrates: an empty registry still renders a sentence.

    Why it matters: the catalogue lands in the system prompt. An empty
    string would put a blank section into the prompt for M3.5's agent and
    (a) puzzle the model, (b) break M5's golden expectations. The empty case
    is a designed message, not the absence of one.
    """
    registry = ToolRegistry()
    text = registry.render_catalogue()
    assert text.strip() != ""
    assert "no tools" in text
    assert "## Available tools" in text  # the section header survives, honestly


def test_catalogue_is_deterministic_across_two_registries():
    """Demonstrates golden-trace insurance: same tools => byte-identical page.

    Why it matters: M5 will snapshot whole agent runs as golden traces. Two
    registries carrying identical knowledge must render the identical
    prompt-section no matter HOW the tools were registered — or trace
    comparisons would diff on registration accident, not on real change.
    """
    a = ToolRegistry()
    a.register(_clock())
    a.register(_adder())
    b = ToolRegistry()
    b.register(_adder())
    b.register(_clock())  # same knowledge, opposite insertion order
    assert a.render_catalogue() == b.render_catalogue()


# ---- Group C · the M3.1 bridge: resolution composes with execution ---------


def test_golden_path_retrieve_then_run():
    """Demonstrates phonebook + Tool.run() compose with zero glue.

    Why it matters: this is the exact two-step the M4 loop will do —
    resolve the ToolCall's name, then execute. It proves Decision 4 (no
    registry.run() dispatcher needed): the registry stays a phonebook and
    execution lives in tool.run(), one line apart.
    """
    registry = ToolRegistry()
    registry.register(_adder())
    tool = registry.get("add")
    assert tool is not None
    result = tool.run({"a": 2, "b": 3})
    assert result.is_error is False
    assert result.output == "2.0 + 3.0 = 5.0"