"""Trace layer: record every internal step as JSONL events.

The core teaching artifact. Every action the agent does — from the brain
receiving a task to the final answer — is one JSON line in the trace.
This makes the agent glass-box; nothing is hidden.

Event kinds (14 total):
  session.start    – agent run begins
  context.add      – a message enters memory
  context.trim     – memory evicts oldest non-system turn
  brain.request    – brain sees a transcript (tools in system prompt)
  brain.response   – brain produces a reply (model text)
  protocol.raw     – model text before parsing (for debugging)
  protocol.parsed  – model text parsed into a verdict
  protocol.error   – parsing produced a gentle note (failure is data)
  tool.lookup      – registry lookup for a tool name
  tool.invoke      – tool.run() begins (with args)
  tool.result      – tool.run() returns (output, is_error)
  loop.turn        – one brain call / tool run counts as a turn
  loop.terminate   – loop ended (by Final Answer or budget)
  agent.answer     – final answer computed (Action Result)

Each event: {ts, iter, kind, payload}
  ts   – UNIX timestamp (seconds) when event occurred
  iter – iteration number (incremented per brain response)
  kind – one of the 13 strings above
  payload – kind-specific data (see docstrings)

All events are pure functions; no side effects outside the file.
"""

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Timestamp utility
def _now() -> float:
    return time.time()

# Event kinds constants (used in tests and by callers)
EVENT_KINDS = {
    "session.start",
    "context.add",
    "context.trim",
    "brain.request",
    "brain.response",
    "protocol.raw",
    "protocol.parsed",
    "protocol.error",
    "tool.lookup",
    "tool.invoke",
    "tool.result",
    "loop.turn",
    "loop.terminate",
    "agent.answer",
}

# File management
_TRACE_DIR = Path(__file__).parent / "traces"
_TRACE_DIR.mkdir(exist_ok=True)
_TRACE_FILE = _TRACE_DIR / "trace.jsonl"

# Global counters (simple persistence for the session)
_session_iter = 0
_run_id: str | None = None

# Reset function for tests
def _reset_session():
    global _session_iter, _run_id
    _session_iter = 0
    _run_id = f"run-{uuid.uuid4().hex[:8]}"


def get_run_id() -> str | None:
    """Return the current session's run identity (None before first reset)."""
    return _run_id

@dataclass
class Event:
    ts: float
    iter: int
    kind: str
    payload: dict[str, Any]
    run_id: str = ""

    def to_dict(self) -> dict:
        return {"ts": self.ts, "iter": self.iter, "kind": self.kind, "payload": self.payload, "run_id": self.run_id}

    @classmethod
    def from_dict(cls, d: dict) -> "Event":
        return cls(**d)

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json_line(cls, line: str) -> "Event":
        return cls.from_dict(json.loads(line))

# Public API

def write_event(kind: str, payload: dict[str, Any]) -> None:
    """Record an event to the trace file.

    Example:
        write_event("brain.response", {
            "prompt_tokens": 124,
            "completion_tokens": 27,
            "text": "Thought: ...\nAction: calculator...",
        })
    """
    global _session_iter
    _session_iter += 1
    # Convert any Message objects in payload to their string representation
    import json
    from dataclasses import is_dataclass
    def sanitize(obj):
        if isinstance(obj, dict):
            return {k: sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [sanitize(v) for v in obj]
        elif is_dataclass(obj):
            # Handle dataclasses by calling their render() method if available
            if hasattr(obj, 'render'):
                return obj.render()
            # Otherwise, try to convert to dict
            return {k: sanitize(v) for k, v in obj.__dict__.items()}
        else:
            return obj
    sanitized_payload = sanitize(payload)
    event = Event(ts=_now(), iter=_session_iter, kind=kind, payload=sanitized_payload, run_id=_run_id or "")
    # Ensure the file exists and append atomically (write to temp then rename)
    tmp = _TRACE_FILE.with_suffix(".tmp")
    # Read existing lines to preserve order (small files only)
    lines = []
    if _TRACE_FILE.exists():
        with open(_TRACE_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
    with open(tmp, "w", encoding="utf-8") as f:
        f.writelines(lines)
        f.write(event.to_json_line() + "\n")
    tmp.replace(_TRACE_FILE)

def read_events(since: int | None = None, kind_filter: str | None = None) -> list[Event]:
    """Read events from the trace file.

    Args:
        since: only events with iter >= since (for pagination)
        kind_filter: only events with this kind (for debugging)

    Returns:
        list of Event objects in file order.
    """
    if not _TRACE_FILE.exists():
        return []
    with open(_TRACE_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = Event.from_json_line(line)
            if since is not None and ev.iter < since:
                continue
            if kind_filter is not None and ev.kind != kind_filter:
                continue
            events.append(ev)
        except Exception:
            # Malformed line: skip for robustness (but log in real system)
            continue
    return events


def clear_trace() -> None:
    """Delete the trace file (for golden-trace fresh runs)."""
    if _TRACE_FILE.exists():
        _TRACE_FILE.unlink()
    _reset_session()

# Expose reset for tests
reset_session = _reset_session


# Demo: show how the trace works
if __name__ == "__main__":
    clear_trace()
    # Simulate a simple agent run
    write_event("session.start", {"task": "calculate 2+2"})
    write_event("brain.request", {"prompt": "You have calculator tool"})
    write_event("brain.response", {"text": "Thought: add\\nAction: calculator\\nAction Input: expression=\"2+2\""})
    write_event("protocol.raw", {"raw": "Thought: add\\nAction: calculator\\nAction Input: expression=\"2+2\""})
    write_event("protocol.parsed", {"kind": "thought_action", "tool": "calculator"})
    write_event("tool.lookup", {"name": "calculator"})
    write_event("tool.invoke", {"name": "calculator", "args": {"expression": "2+2"}})
    write_event("tool.result", {"name": "calculator", "output": "2+2 = 4", "error": False})
    write_event("loop.turn", {"iteration": 1})
    write_event("context.add", {"role": "user", "content": "Observation: 2+2 = 4"})
    write_event("brain.request", {"prompt": "..."})
    write_event("brain.response", {"text": "Thought: done\\nFinal Answer: 4"})
    write_event("protocol.parsed", {"kind": "final_answer", "answer": "4"})
    write_event("agent.answer", {"answer": "4", "steps": 2})
    write_event("loop.terminate", {"reason": "final_answer"})

    print("Trace demo written. Events:", len(read_events()))
    for ev in read_events():
        print(f"{ev.iter:3} {ev.kind:20} {ev.payload}")