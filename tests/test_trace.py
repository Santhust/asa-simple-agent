"""Tests for asa.trace — the M6 trace layer.

Each test demonstrates one idea: event kinds, JSONL schema, CLI integration.
These tests ensure the agent becomes fully observable; nothing is hidden.
"""

from asa.trace import Event, write_event, read_events, clear_trace


def test_event_kind_constants():
    """Demonstrates: 14 event kinds defined for consistency.

    Why it matters: any tool or protocol can refer to these kinds. The
    playground's trace player expects a stable set.
    """
    from asa.trace import EVENT_KINDS
    # Ensure the count is exactly 14
    assert len(EVENT_KINDS) == 14
    # Quick sanity check of known kinds
    assert "session.start" in EVENT_KINDS
    assert "agent.answer" in EVENT_KINDS
    assert "tool.result" in EVENT_KINDS


def test_event_schema():
    """Demonstrates: each event has ts, iter, kind, payload, run_id.

    Why it matters: tooling (CLI, playground) depends on this shape.
    """
    ev = Event(ts=123.45, iter=7, kind="brain.request", payload={"prompt": "hi"})
    d = ev.to_dict()
    assert d["ts"] == 123.45
    assert d["iter"] == 7
    assert d["kind"] == "brain.request"
    assert d["payload"]["prompt"] == "hi"
    assert d["run_id"] == ""  # default when not specified


def test_event_jsonl_roundtrip():
    """Demonstrates: Event ↔ JSON line ↔ Event consistency.

    Why it matters: the file is parsed line by line; roundtrip must preserve
    all fields.
    """
    from asa.trace import reset_session
    reset_session()
    ev1 = Event(ts=0.0, iter=1, kind="tool.invoke", payload={"x": 1}, run_id="run-xyz789")
    line = ev1.to_json_line()
    ev2 = Event.from_json_line(line)
    assert ev1.ts == ev2.ts
    assert ev1.iter == ev2.iter
    assert ev1.kind == ev2.kind
    assert ev1.payload == ev2.payload
    assert ev1.run_id == ev2.run_id == "run-xyz789"


def test_write_and_read_events():
    """Demonstrates: events are persisted to trace.jsonl.

    Why it matters: the CLI and playground can replay the trace later.
    """
    from pathlib import Path
    from asa.trace import clear_trace
    # Start with completely clean slate (conftest also does this; kept explicit)
    clear_trace()

    # Write a few events
    write_event("session.start", {"task": "demo"})
    write_event("brain.request", {"prompt": "tools listed"})
    write_event("agent.answer", {"answer": "done"})
    # Read them back
    events = read_events()
    # Should have exactly 3 events
    assert len(events) == 3, f"Expected 3 events but got {len(events)}. Events: {[e.kind for e in events]}"
    assert events[0].kind == "session.start"
    assert events[0].payload["task"] == "demo"
    assert events[1].kind == "brain.request"
    assert events[2].kind == "agent.answer"
    assert events[2].payload["answer"] == "done"


def test_read_events_filters():
    """Demonstrates: reading supports since and kind filters.

    Why it matters: playground pagination and debugging filters.
    """
    from asa.trace import clear_trace
    # Start with completely clean slate (conftest also does this; kept explicit)
    clear_trace()

    write_event("tool.invoke", {"step": 1})
    write_event("tool.result", {"step": 1})
    write_event("tool.invoke", {"step": 2})
    # Filter by kind
    tool_invokes = read_events(kind_filter="tool.invoke")
    assert len(tool_invokes) == 2
    assert all(ev.kind == "tool.invoke" for ev in tool_invokes)
    # Filter by iter (read all events)
    events = read_events()
    # Should have exactly 3 events from this test
    assert len(events) == 3, f"Expected 3 events but got {len(events)}. Events: {[e.kind for e in events]}"
    assert any(ev.kind == "tool.invoke" for ev in events)
    assert any(ev.kind == "tool.result" for ev in events)


def test_clear_trace():
    """Demonstrates: clear_trace removes the file.

    Why it matters: golden-trace tests start with a clean slate.
    """
    from asa.trace import clear_trace
    clear_trace()
    write_event("test", {"x": 1})
    assert len(read_events()) == 1
    clear_trace()
    assert len(read_events()) == 0


def test_run_id_generated_on_reset():
    """Demonstrates: reset_session() mints a fresh run_id each time.

    Why it matters: the detective needs every run to have its own identity
    so it can separate one run's events from another's in the shared file.
    """
    from asa.trace import reset_session, get_run_id
    reset_session()
    first = get_run_id()
    assert first is not None
    assert first.startswith("run-")
    reset_session()
    second = get_run_id()
    assert second is not None
    assert second != first  # fresh identity every reset


def test_agent_run_writes_session_start_with_run_id():
    """Demonstrates: agent.run() writes session.start carrying run_id.

    Why it matters: this is the detective's anchor — every run begins with
    a named identity card stamped on its first event.
    """
    from asa.trace import read_events, get_run_id
    from asa.agent import Agent
    from asa.brain import MockBrain

    agent = Agent(MockBrain(script=["Thought: done\nFinal Answer: hello"]),
                  narrate=False, max_steps=2)
    agent.run("test task")

    events = read_events()
    starts = [e for e in events if e.kind == "session.start"]
    assert len(starts) == 1
    assert starts[0].payload["task"] == "test task"
    run_id = starts[0].payload["run_id"]
    assert run_id == get_run_id()
    # Every event in this run carries the same run_id
    for ev in events:
        assert ev.run_id == run_id


def test_run_ids_unique_across_runs():
    """Demonstrates: two agent.run() calls get different run_ids.

    Why it matters: the detective must distinguish consecutive runs.
    """
    from asa.trace import read_events, get_run_id
    from asa.agent import Agent
    from asa.brain import MockBrain

    agent = Agent(MockBrain(script=["Thought: done\nFinal Answer: first"]),
                  narrate=False, max_steps=2)
    agent.run("task one")
    run_id_1 = get_run_id()  # capture before second run overwrites _run_id

    agent.run("task two")  # calls reset_session() internally → new run_id
    run_id_2 = get_run_id()

    assert run_id_1 != run_id_2
    # The file now holds events from both runs, each tagged with its own id
    events = read_events()
    run_ids = {ev.run_id for ev in events if ev.run_id}
    assert run_id_1 in run_ids
    assert run_id_2 in run_ids


def test_protocol_error_empty_reply_carries_failure_kind():
    """Demonstrates: empty reply → protocol.error with failure: "empty_reply".

    Why it matters: the detective needs to distinguish silence from format
    drift — both are "protocol.error" but different failure kinds.
    """
    from asa.trace import read_events
    from asa.agent import Agent
    from asa.brain import MockBrain

    agent = Agent(MockBrain(script=[""]), narrate=False, max_steps=1)
    agent.run("test")

    events = read_events()
    errors = [e for e in events if e.kind == "protocol.error"]
    assert len(errors) == 1
    assert errors[0].payload["failure"] == "empty_reply"
    assert errors[0].payload["message"] == "empty reply"


def test_protocol_error_drift_carries_failure_kind():
    """Demonstrates: unparseable reply → protocol.error with failure: "protocol_drift".

    Why it matters: format drift is a different failure than silence — the
    detective's bisect needs to know which.
    """
    from asa.trace import read_events
    from asa.agent import Agent
    from asa.brain import MockBrain

    agent = Agent(MockBrain(script=["hello world"]), narrate=False, max_steps=1)
    agent.run("test")

    events = read_events()
    errors = [e for e in events if e.kind == "protocol.error"]
    assert len(errors) == 1
    assert errors[0].payload["failure"] == "protocol_drift"


def test_tool_error_carries_failure_kind():
    """Demonstrates: tool result with error → tool.result with failure: "tool_error".

    Why it matters: a crashing or misbehaving tool is a distinct failure kind
    from protocol drift or budget exhaustion.
    """
    from asa.trace import read_events
    from asa.agent import Agent
    from asa.brain import MockBrain

    agent = Agent(MockBrain(script=[
        'Thought: compute\nAction: calculator\nAction Input: {"expression": "notanumber"}',
        "Thought: done\nFinal Answer: ok",
    ]), narrate=False, max_steps=3)
    agent.run("compute")

    events = read_events()
    errors = [e for e in events if e.kind == "tool.result" and e.payload.get("failure")]
    assert len(errors) >= 1
    assert all(e.payload["failure"] == "tool_error" for e in errors)


def test_budget_exhausted_carries_failure_kind():
    """Demonstrates: max_steps termination → loop.terminate with failure: "budget_exhausted".

    Why it matters: running out of steps is a distinct failure from a bad
    letter — the detective needs to know the run died of starvation, not
    confusion.
    """
    from asa.trace import read_events
    from asa.agent import Agent
    from asa.brain import MockBrain

    agent = Agent(MockBrain(script=["hello world"]), narrate=False, max_steps=1)
    agent.run("test")

    events = read_events()
    terminates = [e for e in events if e.kind == "loop.terminate"]
    assert len(terminates) == 1
    assert terminates[0].payload["reason"] == "max_steps"
    assert terminates[0].payload["failure"] == "budget_exhausted"