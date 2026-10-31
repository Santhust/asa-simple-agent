"""Tests for the clock tool — the read-only hand's three schema lessons.

Each test names the lesson it demonstrates and why it matters. Deliberately,
NOT ONE test pins an actual timestamp: the clock is the agent's first
non-deterministic tool, and this file is where the philosophy "tests assert
SHAPE, golden traces assert STRUCTURE — never wall-clock values" is written
down before M5 leans on it.
"""

import re

from asa.registry import ToolRegistry
from asa.tools.calculator import build as build_calculator
from asa.tools.clock import build as build_clock

#: The documented output shape: 'YYYY-MM-DD HH:MM:SS (local)' or '... (UTC)'.
_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \((local|UTC)\)$")


def test_golden_path_reads_the_local_wall():
    """Demonstrates the read-only happy path with NO parameters at all.

    Why it matters: a plain call must be legal — that is what 'optional'
    means, and the model reading the catalogue must be able to trust it.
    Also the first Observation sourced from the ENVIRONMENT, and it needs
    nothing but the tool itself.
    """
    result = build_clock().run({})
    assert result.is_error is False
    assert _STAMP.match(result.output), result.output
    assert result.output.endswith("(local)")


def test_utc_true_reads_the_same_instant_in_one_labelled_representation():
    """Demonstrates the optional parameter actually changing the answer.

    Why it matters: 'utc' was chosen as the agent's first real optional
    param; the test proves the default is local AND that explicit true
    yields the labeled UTC representation of the same moment (same clock,
    different label) — reading, never setting, never time-travel.
    """
    result = build_clock().run({"utc": True})
    assert result.is_error is False
    assert _STAMP.match(result.output), result.output
    assert result.output.endswith("(UTC)")


def test_non_boolean_utc_is_rejected_by_the_schema_before_the_function():
    """Demonstrates the mini-schema guarding a real tool's optional param.

    Why it matters: models send 'true' as a STRING exactly as often as they
    send it as a boolean. The type check is the boundary — the function is
    never entered with a string where a boolean is documented, so every
    caller (M4's loop) can trust the types it passes through.
    """
    result = build_clock().run({"utc": "true"})
    assert result.is_error is True
    assert "utc:" in result.output
    assert "expected true/false" in result.output


def test_invented_parameter_is_rejected_and_names_what_is_allowed():
    """Demonstrates the typo-guard interacting with the one optional param.

    Why it matters: 'timezone' is the plausible invention a model will make
    here. The refusal must say the only allowed name, or the model cannot
    self-correct on its next turn.
    """
    result = build_clock().run({"timezone": "UTC"})
    assert result.is_error is True
    assert "unknown argument 'timezone'" in result.output
    assert "utc" in result.output


def test_factory_shape_and_the_first_pair_in_one_catalogue():
    """Demonstrates build() shape + the two stateless tools rendering together.

    Why it matters: M3.5's system prompt will be built from exactly this —
    factories registered into a ToolRegistry, catalogue rendered FROM the
    result. Clock's optional param must show as 'optional' so the page
    matches reality, and byte-equality of the section is pinned here so a
    format accident in M3.5 fails loudly, not silently.
    """
    clock = build_clock()
    assert clock.name == "clock"
    assert "utc" in clock.params
    assert clock.params["utc"]["required"] is False

    registry = ToolRegistry()
    registry.register(build_calculator())
    registry.register(clock)
    assert registry.names() == ["calculator", "clock"]  # sorted, not registration order

    catalogue = registry.render_catalogue()
    assert "### calculator" in catalogue
    assert "### clock" in catalogue
    assert "- utc (boolean, optional): pass true for UTC; the default is your machine's local time" in catalogue
    # the calculator's required param is marked required, on the same page
    assert "- expression (string, required): the arithmetic to do, e.g. '2*(3+4)' or '7/2'" in catalogue