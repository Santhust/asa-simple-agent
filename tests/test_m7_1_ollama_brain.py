"""M7.1 tests — the OllamaBrain skeleton: first real brain, same seam.

What each test demonstrates and why it matters (per the AGENTS.md habit):

  * payload shaping  : a native chat API needs the ROLE in its own JSON field —
                       NOT our textual `<role>` render() prefix. This is the
                       concrete difference between protocol adapters.
  * Completion mapping: Ollama's reply JSON becomes a Completion, using the
                       REAL token counts (prompt_eval_count / eval_count) and
                       falling back to OUR estimator when a server omits them.
  * failure policy   : a connection blip gets one gentle retry (local inference
                       is slow; fail-soft); an HTTP error or a dead server
                       after retries raises OllamaUnavailable with GUIDANCE —
                       failure is data, not a crash (the M4 lesson, now at the
                       network seam).
  * loud params      : unknown **params raise ValueError — never silently
                       ignored, mirrors the project's honesty rules.
  * live smoke       : one real call to localhost:11434, ONLY when Ollama is
                       reachable; otherwise SKIPPED (skipped, never silently
                       failed, keeps the offline suite instant and green).

All offline tests inject a FAKE transport — the network seam M7.1 introduced
precisely so the conversation logic is testable with zero Ollama.

The trace-relevant note: brain.request/brain.response trace events are not
asserted here — they are emitted by agent.py (M6.3). The brain stays pure.
"""

import socket

import pytest
import urllib.error

from asa.brain import Message, OllamaBrain, OllamaUnavailable
from asa.tokens import estimate_tokens


# -- the fake transport: a recording double of the ONE network call ----------

class FakeTransport:
    """Plays queued outcomes, records every call for assertions."""

    def __init__(self, outcomes):
        # each outcome: ("ok", body_dict) or ("err", exception_instance)
        self._outcomes = list(outcomes)

    def __call__(self, url, payload, timeout):
        self.calls = getattr(self, "calls", [])
        self.calls.append((url, payload, timeout))
        kind, value = self._outcomes.pop(0)
        if kind == "ok":
            return 200, value
        raise value


RESPONSE_BODY = {
    "model": "lfm3:latest",
    "message": {"role": "assistant", "content": "Thought: done\nFinal Answer: 4"},
    "prompt_eval_count": 411,
    "eval_count": 9,
}


def make_brain(outcomes, **kw):
    transport = FakeTransport(outcomes)
    defaults = dict(retry_wait=0.0)  # offline tests must not sleep
    defaults.update(kw)
    brain = OllamaBrain(transport=transport, **defaults)
    return brain, transport


# -- request shaping ----------------------------------------------------------

def test_payload_shapes_messages_for_native_chat():
    """Our Message list -> Ollama chat JSON: role in the FIELD, no <role> prefix."""
    brain, transport = make_brain([("ok", RESPONSE_BODY)])
    completion = brain.complete([
        Message(role="system", content="You are 'asa'."),
        Message(role="user", content="say 2+2"),
        Message(role="assistant", content="Thought: calculate"),
        Message(role="user", content="Observation: 2+2 = 4"),
    ])
    assert completion is not None  # success is M-response-mapping's job; here we inspect
    url, payload, timeout = transport.calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert [m["role"] for m in payload["messages"]] == ["system", "user", "assistant", "user"]
    assert payload["messages"][0]["content"] == "You are 'asa'."  # RAW content, no "<system>" prefix
    assert payload["model"] == "lfm3:latest"
    assert payload["stream"] is False            # one letter, not a token faucet
    assert payload["think"] is False             # M7.0 decision pinned in code
    assert payload["options"]["num_predict"] == 512  # runaway-generation cap
    assert "temperature" not in payload["options"]   # unset -> omitted, not None


# -- response mapping ---------------------------------------------------------

def test_real_token_counts_flow_into_completion():
    brain, _ = make_brain([("ok", RESPONSE_BODY)])
    completion = brain.complete([Message(role="user", content="hi")])
    assert completion.text == "Thought: done\nFinal Answer: 4"
    assert completion.model == "lfm3:latest"
    assert completion.prompt_tokens == 411      # REAL count, not an estimate
    assert completion.completion_tokens == 9


def test_token_estimate_fallback_when_server_omits_counts():
    body = {"model": "lfm3:latest", "message": {"role": "assistant",
                                                "content": "Final Answer:hello"}}
    brain, _ = make_brain([("ok", body)])
    completion = brain.complete([Message(role="user", content="hi there")])
    assert completion.prompt_tokens == estimate_tokens("hi there")
    assert completion.completion_tokens == estimate_tokens("Final Answer:hello")


# -- failure policy: fail-soft with guidance ----------------------------------

def test_connection_blip_gets_one_gentle_retry():
    blip = urllib.error.URLError("connection refused by server")
    brain, transport = make_brain(
        [("err", blip), ("ok", RESPONSE_BODY)], retries=1)
    completion = brain.complete([Message(role="user", content="hi")])
    assert completion.text == "Thought: done\nFinal Answer: 4"
    assert len(transport.calls) == 2  # first attempt failed, retry succeeded


def test_dead_server_raises_with_guidance_after_retries():
    blip = urllib.error.URLError("connection refused")
    brain, transport = make_brain([("err", blip)] * 2, retries=1)
    with pytest.raises(OllamaUnavailable, match="ollama list"):
        brain.complete([Message(role="user", content="hi")])
    assert len(transport.calls) == 2  # exactly retries+1 attempts, then stop


def test_http_error_is_surfaced_immediately_not_retried():
    """A 4xx will not heal; retrying it would hide a real misconfiguration."""
    http_err = urllib.error.HTTPError(
        "http://localhost:11434/api/chat", 404, "model not found", None, None)
    brain, transport = make_brain([("err", http_err)], retries=3)
    with pytest.raises(OllamaUnavailable, match="HTTP 404"):
        brain.complete([Message(role="user", content="hi")])
    assert len(transport.calls) == 1  # NO retry: the server spoke, we listened


# -- loud interfaces ----------------------------------------------------------

def test_unknown_param_is_rejected_not_silently_ignored():
    brain, _ = make_brain([("ok", RESPONSE_BODY)])
    with pytest.raises(ValueError, match="stop_sequence"):
        brain.complete([Message(role="user", content="hi")], stop_sequences=["END"])


def test_params_can_override_thinking_and_cap():
    """The one-flag thinking toggle from M7.0: overridable per call."""
    brain, transport = make_brain([("ok", RESPONSE_BODY)])
    brain.complete([Message(role="user", content="deep question")],
                   think=True, num_predict=64)
    _, payload, _ = transport.calls[-1]
    assert payload["think"] is True
    assert payload["options"]["num_predict"] == 64


# -- live smoke: real Ollama, real lfm3, tiny and skippable --------------------

def _ollama_alive(host="localhost", port=11434) -> bool:
    """Cheap TCP probe with a 0.5s budget — no HTTP needed to check 'is it up'."""
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _ollama_alive(),
                    reason="live Ollama not reachable on localhost:11434 — "
                           "skipped honestly (offline suite stays instant)")
def test_live_lfm3_first_words():
    brain = OllamaBrain(num_predict=16, timeout=90)  # tiny cap: the Pi5 is slow
    completion = brain.complete([Message(role="user", content="Reply with exactly: OK")])
    assert completion.text.strip(), "live model returned empty text"
    assert "lfm3" in completion.model
    real_counts = completion.prompt_tokens > 0 and completion.completion_tokens > 0
    assert real_counts, "Ollama should report real token counts"
