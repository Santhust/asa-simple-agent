"""Tests for the calculator tool — proving the pure hand's five lessons.

Each test names the lesson it demonstrates and why it matters for the agent
loop that M4/M5 will build on top of this.
"""

from asa.registry import ToolRegistry
from asa.tools import calculator as calc_mod
from asa.tools.calculator import build, evaluate

_CALC = None  # one build() per test module, but ALWAYS via the factory


def _calc():
    global _CALC
    if _CALC is None:
        _CALC = build()
    return _CALC


def test_golden_path_ints_stay_ints():
    """Demonstrates honest numerics: int arithmetic renders int, not 5.0.

    Why it matters: the Observation is the model's only feedback. '2+3 = 5'
    reads like arithmetic; '2+3 = 5.0' would whisper that something secretly
    converted ints to floats. Python's real semantics, shown verbatim.
    """
    result = _calc().run({"expression": "2+3"})
    assert result.is_error is False
    assert result.output == "2+3 = 5"


def test_division_follows_python_and_floats_stay_honest():
    """Demonstrates '/' semantics and the no-cosmetic-rounding rule.

    Why it matters: '7/2 = 3.5' and '8/2 = 4.0' are Python truth — division
    ALWAYS produces a float, even when the value is whole. And '0.1+0.2 =
    0.30000000000000004' is not a bug we hide: floating point is IEEE 754
    truth, and a rounded story would teach the model to trust a lie.
    """
    assert _calc().run({"expression": "7/2"}).output == "7/2 = 3.5"
    assert _calc().run({"expression": "8/2"}).output == "8/2 = 4.0"
    assert (
        _calc().run({"expression": "0.1+0.2"}).output
        == "0.1+0.2 = 0.30000000000000004"
    )


def test_precedence_parens_and_unary_minus():
    """Demonstrates the parser handles the documented grammar in full.

    Why it matters: the catalogue promises '+ - * /, parentheses and
    decimals'. Precedence ('*' before '+'), parentheses, and unary minus
    are the expressions a model will actually send; each must be right
    because the Observation states the sum as if it were obvious.
    """
    assert _calc().run({"expression": "2*(3+4)"}).output == "2*(3+4) = 14"
    assert _calc().run({"expression": "1+2*3"}).output == "1+2*3 = 7"
    assert _calc().run({"expression": "-3+5"}).output == "-3+5 = 2"


def test_division_by_zero_is_readable_error_data():
    """Demonstrates failure-as-data: the crime scene says WHY in English.

    Why it matters: 'calculator: division by zero is undefined — pick a
    different expression' is something the model can act on in M4. A raw
    ZeroDivisionError would either crash the agent (before M3.1's guard) or
    arrive as a cryptic exception name — either way the model learns nothing.

    """
    result = _calc().run({"expression": "1/0"})
    assert result.is_error is True
    assert "division by zero" in result.output
    assert "pick a different expression" in result.output


def test_malformed_expression_is_a_readable_error_not_a_crash():
    """Demonstrates the parser refusing at the crime scene, in human words.

    Why it matters: models WILL send '2+' and '(2+3'. Readable positions and
    reasons ('the expression ends where a number or '(' was expected') are
    what turns a model failure into a self-correction instead of a dead loop.
    """
    missing = _calc().run({"expression": "2+"})
    assert missing.is_error is True
    assert "ends where a number or '(' was expected" in missing.output

    unbalanced = _calc().run({"expression": "(2+3"})
    assert unbalanced.is_error is True
    assert "unbalanced" in unbalanced.output


def test_eval_is_not_because_the_language_is_ground_math():
    """Demonstrates the tool is EXACTLY as narrow as documented — no eval().

    Why it matters: the catalogue promises arithmetic. eval() would deliver
    arbitrary Python (imports, file access, whatever a model typed), making
    the narrowness a fiction — a security hole wearing a calculator costume.
    Ground-math-only decides this before any guard: '__import__' is
    simply not part of the language, so it is refused as a character error.
    """
    result = _calc().run({"expression": "__import__('os')"})
    assert result.is_error is True
    assert "unexpected character '_'" in result.output
    assert "I read numbers, + - * / ( )" in result.output


def test_resource_guards_reject_adversarial_sized_input_as_text():
    """Demonstrates resource limits being TOOL business, phraseable as data.

    Why it matters: the mini-schema can't say 'at most 200 characters', and
    a recursive-descent parser could otherwise be crashed (Python stack) by
    a model wandering into absurd input. Crashing is not an option for the
    agent — so the tool measures its own input and says so, in text.
    """
    long_result = _calc().run({"expression": "1" * calc_mod._MAX_CHARS + " + 2"})
    assert long_result.is_error is True
    assert "characters" in long_result.output

    # 32 open parens stay UNDER 200 chars — deliberately past the depth cap
    # (32), not the length cap, so THIS assertion exercises THIS guard.
    deep_result = _calc().run({"expression": "(" * 40 + "1" + ")" * 40})
    assert deep_result.is_error is True
    assert "nest" in deep_result.output


def test_wrong_and_invented_arguments_are_rejected_before_the_function():
    """Demonstrates the M3.1 mini-schema guarding a REAL tool.

    Why it matters: validation happens in Tool.run() before the function is
    ever entered — a model sending the wrong param name or a number for a
    string meets an error Observation and can try again. Proven once with
    spy tools; here it is proven with the real thing.
    """
    invented = _calc().run({"expr": "2+2"})  # the classic model typo
    assert invented.is_error is True
    assert "unknown argument 'expr'" in invented.output

    typed = _calc().run({"expression": 5})  # number where text is documented
    assert typed.is_error is True
    assert "expected text" in typed.output


def test_factory_shape_and_phonebook_roundtrip():
    """Demonstrates build() + registry compose — the M3.5 wiring is one line.

    Why it matters: M3.5 will loop over factory functions like THIS one and
    register the results. The Tool must carry the exact name/schema the
    catalogue will render, and then run correctly when fetched from a real
    registry — the phonebook and the hand simply click together.
    """
    tool = build()
    assert tool.name == "calculator"
    assert tool.description
    assert "expression" in tool.params
    assert callable(tool.func)

    registry = ToolRegistry()
    registry.register(tool)
    fetched = registry.get("calculator")
    assert fetched is not None
    result = fetched.run({"expression": "2*3"})
    assert result.is_error is False
    assert result.output == "2*3 = 6"
