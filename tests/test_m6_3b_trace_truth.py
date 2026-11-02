"""M6.3b regression — trace events must be temporally TRUE.

Provenance (why this exists): on 2026-11-02, replaying M8.2's Gemini run
against the API to diagnose a silent turn, the probe hit Google's
"Requests ending with a model turn are not supported" — because agent.py
emitted `brain.request` AFTER the reply was already stored in memory.
Every recorded snapshot contained the reply it claimed to have prompted:
the flight recorder was rewriting history, and the detective drew a false
hypothesis from corrupted evidence for one whole evening.

What these tests pin forever:

  1. the first brain.request of a run may NOT yet contain the first
     brain.response's text (the reply does not exist at request time);
  2. every brain.request payload equals the memory state BEFORE the call —
     provable because request payloads grow exactly ONE message per turn
     (the previous turn's REPLY was already in memory when THIS request
     was recorded — but the CURRENT turn's reply must still be absent);
  3. brain.response is emitted with the exact text that then enters memory.
"""

from asa.agent import Agent
from asa.brain import MockBrain
from asa.trace import read_events


def test_request_precedes_response_and_never_previews_its_own_reply():
    agent = Agent(MockBrain(script=["Thought: one\nFinal Answer: first reply"]),
                  narrate=False, max_steps=2)
    agent.run("hello there")

    events = read_events()
    request = next(e for e in events if e.kind == "brain.request")
    response = next(e for e in events if e.kind == "brain.response")
    assert events.index(request) < events.index(response)

    prompt = "\n".join(request.payload["prompt"])
    assert "first reply" not in prompt, (
        "brain.request recorded a reply that had not yet existed — "
        "the trace lied about time and the detective believed it")

    after = next(
        e for e in events
        if e.kind == "brain.response"
    )
    assert after.payload["text"] == "Thought: one\nFinal Answer: first reply"


def test_each_request_captures_the_prior_turn_not_its_own():
    """Turn 2's request must contain turn 1's letter (already in memory)
    and MUST NOT contain turn 2's own reply (still milk-fresh in the brain)."""
    first = 'Thought: compute\nAction: calculator\nAction Input: {"expression": "2+2"}'
    second = "Thought: got it\nFinal Answer: done2"
    agent = Agent(MockBrain(script=[first, second]), narrate=False, max_steps=3)
    agent.run("compute 2+2")

    events = read_events()
    requests = [e for e in events if e.kind == "brain.request"]
    assert len(requests) == 2
    second_prompt = "\n".join(requests[1].payload["prompt"])
    assert "2+2" in second_prompt       # turn 1's letter: IN (it's history now)
    assert "done2" not in second_prompt  # the current turn's reply: NOT YET
