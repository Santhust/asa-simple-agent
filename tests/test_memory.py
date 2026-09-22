"""Tests for asa.memory.ContextWindow — how the agent "remembers".

Each test pins down one small claim about the transcript: order, token cost,
and the two forget-guarantees (system sacred · newest kept). Read these before
using trim() — they spell out the exact behavior the Agent (agent.py, M2.3)
will rely on when its memory grows past the budget.
"""

import pytest

from asa.memory import ContextWindow
from asa.tokens import estimate_tokens


def make_window(*turns, system="You are asa."):
    w = ContextWindow(system=system)
    for role, text in turns:
        w.add(role, text)
    return w


def texts_of(w) -> str:
    return " ".join(m.content for m in w.messages)


def test_add_preserves_role_order():
    """Demonstrates: turns are stored in the exact order they happened.

    Why it matters: the brain reads the transcript top to bottom. If order
    drifted, the model would hear the answer before the question.
    """
    w = make_window(("user", "hi"), ("assistant", "hello"), ("user", "again"))
    assert [m.role for m in w.messages] == ["system", "user", "assistant", "user"]
    assert texts_of(w) == "You are asa. hi hello again"


def test_token_count_is_the_estimated_sum():
    """Demonstrates: token accounting is exactly estimate_tokens summed over turns.

    Why it matters: trim() decides what to forget using this number. If this
    arithmetic drifted from tokens.py, budget decisions would be wrong.
    """
    w = make_window(("user", "a" * 100), ("assistant", "b" * 40))
    expected = (
        estimate_tokens("You are asa.")
        + estimate_tokens("a" * 100)
        + estimate_tokens("b" * 40)
    )
    assert w.token_count() == expected


def test_len_reflects_transcript_size():
    """Demonstrates: __len__ counts Message objects (system included)."""
    w = make_window(("user", "hi"), ("assistant", "hello"))
    assert len(w) == 3


def test_messages_returns_a_copy():
    """Demonstrates: callers cannot mutate memory through the accessor.

    Why it matters: the forget-guarantees are only real if nobody outside the
    window can reorder or delete turns behind its back.
    """
    w = make_window(("user", "hi"))
    w.messages.clear()
    assert len(w) == 2


def test_trim_without_budget_is_a_noop():
    """Demonstrates: no budget means nothing is ever forgotten.

    Why it matters: many agents run with effectively unbounded context; trim()
    must be a pure opt-in, never a surprise.
    """
    w = make_window(("user", "hi"), ("assistant", "hello"))
    assert w.trim(budget=None) == 0
    assert len(w) == 3


def test_trim_keeps_system_and_newest_turn():
    """Demonstrates the two guarantees under maximum pressure (tiny budget).

    The system prompt survives because it is the standing instruction; the
    newest turn survives because a context that forgets its last message stops
    making sense. Only the past is forgettable.
    """
    w = make_window(
        ("user", "first question one two three"),
        ("assistant", "first answer one two three"),
        ("user", "the actual question"),
    )
    dropped = w.trim(budget=6)
    assert dropped == 2
    assert w.messages[0].role == "system"                 # guarantee 1
    assert w.messages[0].content == "You are asa."
    assert w.messages[-1].content == "the actual question"  # guarantee 2
    assert "first question" not in texts_of(w)


def test_trim_prefers_oldest_over_biggest():
    """Demonstrates: eviction is age-based, not size-based.

    Why it matters: the oldest, most stale turn usually costs the least to lose
    — a huge but recent turn is kept even when a tiny oldest one is dropped.
    """
    w = make_window(("user", "u" * 200), ("assistant", "short"))
    dropped = w.trim(budget=40)
    assert dropped == 1
    assert w.messages[-1].content == "short"
    assert len(w) == 2  # system + newest


def test_single_oversized_turn_accepted_despite_budget():
    """Demonstrates: a turn bigger than the whole budget is kept anyway.

    Why it matters: one fresh message beats an empty, "in-budget" context —
    a documented, deliberate overrun rather than a silent deletion.
    """
    w = make_window(("user", "z" * 500))  # ~125 tokens against a budget of 30
    dropped = w.trim(budget=30)
    assert dropped == 0
    assert w.token_count() > 30


def test_trim_meets_budget_or_stops_at_the_guarantees():
    """Demonstrates: trim stops at the guarantees, even if the budget is unmet.

    With a budget of one token the transcript can never fit — but system and
    the newest turn still survive.
    """
    w = make_window(("user", "question"), ("assistant", "answer"))
    w.trim(budget=1)
    assert [m.role for m in w.messages] == ["system", "assistant"]


def test_trim_reports_how_many_were_dropped():
    """Demonstrates: trim returns the eviction count.

    Why it matters: the return value becomes the narration hook — "forgot 3
    turns" is exactly the moment the CLI and later the trace should teach.
    """
    w = make_window(
        ("user", "question one"),
        ("assistant", "answer one"),
        ("user", "question two"),
        ("assistant", "answer two"),
    )
    dropped = w.trim(budget=5)
    assert dropped == 3
    assert [m.role for m in w.messages] == ["system", "assistant"]
    assert w.messages[-1].content == "answer two"
    assert w.token_count() == 5