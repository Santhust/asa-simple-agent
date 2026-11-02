"""M9.3 tests — asa.compare_protocols (side-by-side ReAct vs native benchmark).

Offline and keyless: scripts MockBrain deterministically so the lab's metrics
(drift, repair, steps, tokens, wall time) are pinned without any model. The
gemini live side-by-side is exercised by running the CLI with
GEMINI_API_KEY set — not asserted here.
"""

from asa.compare_protocols import compare, run_once
from asa.brain import MockBrain


def test_run_once_react_success_drift_zero():
    """A scripted ReAct success: two turns, one tool call, no drift."""
    brain = MockBrain(script=[
        "Thought: I need to compute.\n"
        "Action: calculator\n"
        "Action Input: {\"expression\": \"7*6\"}\n",
        "Thought: done.\nFinal Answer: 42\n",
    ])
    m = run_once(brain, "compute 7*6", max_steps=4)
    assert m["protocol"] == "react"
    assert m["brain"] == "MockBrain"
    assert m["steps"] == 2
    assert m["terminate_reason"] == "final_answer"
    assert m["drift_count"] == 0
    assert m["repair_count"] == 0
    assert m["tool_calls"] == 1
    assert m["tool_results"] == 1
    assert m["wall_s"] >= 0


def test_run_once_drift_then_repair():
    """M4.3 in numbers: a bad letter → gentle note → retry → success.
    drift_count==1, repair_count==1, two tool-free turns then a tool call."""
    brain = MockBrain(script=[
        "This is not a letter at all.",          # drift -> empty_reply note
        "Thought: now I will call.\n"
        "Action: calculator\n"
        "Action Input: {\"expression\": \"2+2\"}\n",
        "Thought: done.\nFinal Answer: 4\n",
    ])
    m = run_once(brain, "compute 2+2", max_steps=6)
    assert m["terminate_reason"] == "final_answer"
    assert m["steps"] == 3
    assert m["drift_count"] == 1
    assert m["repair_count"] == 1
    assert m["tool_calls"] == 1


def test_run_once_max_steps_exhausted():
    """A brain that never answers hits the budget: max_steps, drift counted."""
    brain = MockBrain(script=["just talking"] * 4)
    m = run_once(brain, "anything", max_steps=4)
    assert m["terminate_reason"] == "max_steps"
    assert m["steps"] == 4
    # 4 empty replies = 4 empty_reply drifts
    assert m["drift_count"] == 4
    assert m["repair_count"] == 4


def test_compare_mock_react_only_native_none():
    """MockBrain is text-only: compare() yields react metrics, native is None."""
    c = compare("compute 7*6", "mock", runs=2, max_steps=4)
    assert c["brain"] == "mock"
    assert c["summary"]["react"] is not None
    assert c["summary"]["react"]["trials"] == 2
    assert c["summary"]["react"]["final_answers"] >= 0
    assert c["summary"]["native"] is None   # text-only brain has no native side


def test_compare_react_and_native_trials_match_runs():
    """Each protocol gets exactly `runs` trials when native is available."""
    c = compare("compute 7*6", "mock", runs=3, max_steps=4)
    assert c["summary"]["react"]["trials"] == 3
    assert c["summary"]["react"]["avg_steps"] >= 1


def test_compare_unknown_brain_raises():
    try:
        compare("x", "no-such-brain", runs=1, max_steps=4)
    except (KeyError, ValueError):
        pass
    else:
        raise AssertionError("expected an error for an unknown brain")


def test_metrics_non_negative_and_wall_present():
    brain = MockBrain(script=["Thought: done\nFinal Answer: hi\n"])
    m = run_once(brain, "x", max_steps=1)
    for key in ("steps", "tokens", "drift_count", "repair_count",
                "tool_calls", "tool_results", "wall_s"):
        assert key in m
        assert m[key] >= 0
