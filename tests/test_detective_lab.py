"""Tests for lab/detective_lab.py — the replay probe for the M6 trace (M8.4.3).

Each test demonstrates one idea: grouping by run_id, detecting failures,
extracting failure contexts, converting render()→native format, replaying.

These tests stay OFFLINE — no Ollama, no Gemini, no network. The detective
lab's replay against real brains is exercised manually (or in M8.5's live
smoke), but the logic that drives it is fully testable here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from asa.trace import Event, read_events  # noqa: E402

# Import the lab module directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lab"))
import detective_lab  # noqa: E402


def make_event(iter_no: int, kind: str, run_id: str = "run-abc", **payload) -> Event:
    """Helper to build an Event with a given run_id."""
    return Event(ts=1.0, iter=iter_no, kind=kind, payload=payload, run_id=run_id)


def test_group_events_by_run_separates_runs():
    """Demonstrates: events are grouped by their run_id."""
    events = [
        make_event(1, "session.start", run_id="run-1", task="a"),
        make_event(2, "brain.request", run_id="run-1", prompt=["x"]),
        make_event(3, "session.start", run_id="run-2", task="b"),
        make_event(4, "brain.request", run_id="run-2", prompt=["y"]),
    ]
    groups = detective_lab.group_events_by_run(events)
    assert set(groups.keys()) == {"run-1", "run-2"}
    assert len(groups["run-1"]) == 2
    assert len(groups["run-2"]) == 2


def test_is_failing_run_detects_budget_exhaustion():
    """Demonstrates: loop.terminate with reason max_steps = failing run."""
    events = [
        make_event(1, "session.start", run_id="run-1"),
        make_event(2, "loop.terminate", run_id="run-1", reason="max_steps"),
    ]
    assert detective_lab.is_failing_run(events) is True


def test_is_failing_run_detects_final_answer():
    """Demonstrates: loop.terminate with reason final_answer = NOT failing."""
    events = [
        make_event(1, "session.start", run_id="run-1"),
        make_event(2, "loop.terminate", run_id="run-1", reason="final_answer"),
    ]
    assert detective_lab.is_failing_run(events) is False


def test_has_failure_events_detects_failure_kind():
    """Demonstrates: any event with a 'failure' payload key = failing run."""
    events = [
        make_event(1, "protocol.error", run_id="run-1", message="empty reply",
                   failure="empty_reply"),
    ]
    assert detective_lab.has_failure_events(events) is True


def test_has_failure_events_false_without_failures():
    """Demonstrates: events without failure keys = not failing."""
    events = [
        make_event(1, "brain.response", run_id="run-1", text="hello"),
        make_event(2, "agent.answer", run_id="run-1", answer="hello"),
    ]
    assert detective_lab.has_failure_events(events) is False


def test_extract_failure_contexts_finds_brain_request_before_failure():
    """Demonstrates: the brain.request before a protocol.error is extracted."""
    events = [
        make_event(1, "brain.request", run_id="run-1", prompt=["<system> hi", "<user> task"]),
        make_event(2, "brain.response", run_id="run-1", text="bad reply"),
        make_event(3, "protocol.raw", run_id="run-1", raw="bad reply"),
        make_event(4, "protocol.error", run_id="run-1", message="empty reply",
                   failure="empty_reply"),
    ]
    contexts = detective_lab.extract_failure_contexts(events)
    assert len(contexts) == 1
    assert contexts[0]["turn"] == 1
    assert contexts[0]["failure_kind"] == "empty_reply"
    assert contexts[0]["context"] == ["<system> hi", "<user> task"]


def test_extract_failure_contexts_ignores_non_failures():
    """Demonstrates: events without failure kinds don't produce contexts."""
    events = [
        make_event(1, "brain.request", run_id="run-1", prompt=["<user> task"]),
        make_event(2, "brain.response", run_id="run-1", text="good reply"),
        make_event(3, "agent.answer", run_id="run-1", answer="good"),
        make_event(4, "loop.terminate", run_id="run-1", reason="final_answer"),
    ]
    contexts = detective_lab.extract_failure_contexts(events)
    assert contexts == []


def test_render_to_native_ollama_splits_role_and_content():
    """Demonstrates: '<role> content' → {"role": ..., "content": ...}."""
    rendered = ["<system> You are asa.", "<user> What is 7*6?", "<assistant> Thought: compute"]
    native = detective_lab.render_to_native_ollama(rendered)
    assert native == [
        {"role": "system", "content": "You are asa."},
        {"role": "user", "content": "What is 7*6?"},
        {"role": "assistant", "content": "Thought: compute"},
    ]


def test_render_to_native_gemini_splits_system_and_contents():
    """Demonstrates: system → systemInstruction, others → contents with user/model roles."""
    rendered = ["<system> You are asa.", "<user> What is 7*6?", "<assistant> Thought: compute"]
    native = detective_lab.render_to_native_gemini(rendered)
    assert native["systemInstruction"]["parts"][0]["text"] == "You are asa."
    assert native["contents"] == [
        {"role": "user", "parts": [{"text": "What is 7*6?"}]},
        {"role": "model", "parts": [{"text": "Thought: compute"}]},
    ]


def test_replay_context_with_mockbrain_ignores_context():
    """Demonstrates: MockBrain replay returns its scripted text regardless of context."""
    from asa.brain import MockBrain
    brain = MockBrain(script=["Final Answer: replayed"])
    reply = detective_lab.replay_context(brain, [{"role": "user", "content": "ignored"}])
    assert reply == "Final Answer: replayed"


def test_main_reports_no_events(tmp_path, monkeypatch, capsys):
    """Demonstrates: main() with no trace events reports nothing to replay."""
    # Patch read_events to return empty
    monkeypatch.setattr(detective_lab, "read_events", lambda: [])
    rc = detective_lab.main(argv=[])
    assert rc == 1
    out = capsys.readouterr().out
    assert "No trace events found" in out
