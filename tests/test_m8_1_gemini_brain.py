"""M8.1 tests — the GeminiBrain skeleton: the zoo's first CLOUD brain, same seam.

What each test demonstrates and why it matters:

  * third JSON dialect : our Message list becomes Gemini's contents[]/parts[],
    and the "system" message moves to its SEPARATE systemInstruction field.
    Roles: Gemini speaks "user"/"model" — our "assistant" maps to "model".
    Every native-API brain teaches the same lesson a level deeper: the ROLE
    lives in its own field, never in our <role> render() prefix.
  * thinking: the M8.0 "off" pin was amended in M8.2's LIVE bisection — this
    model rejects thinkingBudget=0 (400 INVALID_ARGUMENT), so no
    thinkingConfig is ever sent; thought parts get filtered at mapping time
    (same separate-channel contract as Ollama's message.thinking).
  * real token counts: usageMetadata -> Completion, estimator as fallback.
  * credential rules as CODE (M8.0): the key rides in a HEADER, never a URL —
    so no log, trace, or error can capture it; error messages never
    interpolate it; the missing-key failure names the missing THING.
  * failure policy    : transient URLError -> 1 gentle retry; HTTP error ->
    surfaced immediately (4xx won't heal); dead server -> guidance. Same shape
    as M7.1 because the SAME philosophy now speaks to a different backend.

All offline via the fake transport (instant, deterministic, keyless) —
only the live smoke touches Google, and it SKIPS without GEMINI_API_KEY.
"""

import json as json_lib
import socket
import time
from email.message import Message as EmailMessage

import pytest
import urllib.error

from asa.brain import GeminiBrain, GeminiUnavailable, Message
from asa.tokens import estimate_tokens


SECRET = "AIzaThisIsATestKeyForRedactionChecks"  # fake — exercises redaction only


class FakeTransport:
    """Plays queued outcomes, records every call (url, payload, timeout)."""

    def __init__(self, outcomes):
        self._outcomes = list(outcomes)

    def __call__(self, url, payload, timeout):
        self.calls = getattr(self, "calls", [])
        self.calls.append((url, payload, timeout))
        kind, value = self._outcomes.pop(0)
        if kind == "ok":
            return 200, value
        raise value


RESPONSE_BODY = {
    "candidates": [{
        "content": {"role": "model",
                    "parts": [{"text": "Thought: done\nFinal Answer: three"}]},
        "finishReason": "STOP",
    }],
    "usageMetadata": {"promptTokenCount": 411, "candidatesTokenCount": 9},
}

MESSAGES = [
    Message(role="system", content="You are 'asa'."),
    Message(role="user", content="count to three"),
    Message(role="assistant", content="Thought: counting"),
    Message(role="user", content="Observation: 1 2 3"),
]


def make_brain(outcomes, **kw):
    transport = FakeTransport(outcomes)
    defaults = dict(api_key=SECRET, retry_wait=0.0)
    defaults.update(kw)
    brain = GeminiBrain(transport=transport, **defaults)
    return brain, transport


# -- request shaping ----------------------------------------------------------

def test_payload_splits_system_and_maps_roles_to_the_third_dialect():
    brain, transport = make_brain([("ok", RESPONSE_BODY)])
    brain.complete(MESSAGES)
    url, payload, _ = transport.calls[0]
    assert url.startswith("https://generativelanguage.googleapis.com/")
    assert "/models/gemini-3.5-flash-lite:generateContent" in url
    assert "key" not in url                    # credential rule: key NEVER in URL
    assert payload["systemInstruction"]["parts"][0]["text"] == "You are 'asa'."
    roles = [c["role"] for c in payload["contents"]]
    assert roles == ["user", "model", "user"]  # of "assistant" -> "model"
    assert payload["contents"][0]["parts"][0]["text"] == "count to three"  # raw, no prefix
    assert payload["generationConfig"]["maxOutputTokens"] == 512
    # M8.2 amendment: Google rejects thinkingBudget=0 (400 INVALID_ARGUMENT) —
    # thinkingConfig is never sent; thought parts get filtered at mapping time.
    assert "thinkingConfig" not in payload["generationConfig"]


def test_thinking_switch_is_intent_only_untill_the_api_speaks():
    """ON or OFF, the payload is the same today — the pin was amended in live
    bisect (M8.2); the flag stays for the day the API allows it."""
    brain_on, transport_on = make_brain([("ok", RESPONSE_BODY)])
    brain_on.complete(MESSAGES, thinking=True)
    brain_off, transport_off = make_brain([("ok", RESPONSE_BODY)])
    brain_off.complete(MESSAGES)
    _, payload_on, _ = transport_on.calls[0]
    _, payload_off, _ = transport_off.calls[0]
    assert payload_on["generationConfig"] == payload_off["generationConfig"]


# -- response mapping ---------------------------------------------------------

def test_reply_maps_to_completion_with_real_token_counts():
    brain, _ = make_brain([("ok", RESPONSE_BODY)])
    completion = brain.complete(MESSAGES)
    assert completion.text == "Thought: done\nFinal Answer: three"
    assert completion.prompt_tokens == 411
    assert completion.completion_tokens == 9
    assert brain.total_output_tokens == 9  # bench aggregation, Ollama parity


def test_thought_parts_never_pollute_the_letter():
    body = {"candidates": [{"content": {"role": "model", "parts": [
        {"thought": True, "text": "internal reasoning scribbles"},
        {"text": "Final Answer: 4"},
    ]}}]}
    brain, _ = make_brain([("ok", body)])
    assert brain.complete(MESSAGES).text == "Final Answer: 4"


def test_missing_usage_falls_back_to_our_estimator():
    body = {"candidates": [{"content": {"parts": [{"text": "Final Answer: hi"}]}}]}
    brain, _ = make_brain([("ok", body)])
    completion = brain.complete([Message(role="user", content="hello")])
    assert completion.prompt_tokens == estimate_tokens("hello")
    assert completion.completion_tokens == estimate_tokens("Final Answer: hi")


# -- credential rules ----------------------------------------------------------

def test_missing_key_fails_with_guidance_naming_the_thing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    brain = GeminiBrain()  # default transport, no key anywhere
    with pytest.raises(GeminiUnavailable, match="GEMINI_API_KEY"):
        brain.complete([Message(role="user", content="hi")])


def test_http_error_never_contains_the_key():
    http_err = urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/", 403, "Forbidden", None, None)
    brain, _ = make_brain([("err", http_err)], retries=3)
    with pytest.raises(GeminiUnavailable) as info:
        brain.complete(MESSAGES)
    assert "HTTP 403" in str(info.value)
    assert SECRET not in str(info.value)     # redaction by construction
    assert "AIza" not in str(info.value)


# -- failure policy ------------------------------------------------------------

def test_transient_blip_gets_one_gentle_retry():
    blip = urllib.error.URLError("temporary network hiccup")
    brain, transport = make_brain([("err", blip), ("ok", RESPONSE_BODY)])
    completion = brain.complete(MESSAGES)
    assert "Final Answer: three" in completion.text
    assert len(transport.calls) == 2


def test_dead_server_gives_up_with_guidance_after_retries():
    blip = urllib.error.URLError("connection refused anyway")
    brain, transport = make_brain([("err", blip)] * 2, retries=1)
    with pytest.raises(GeminiUnavailable, match="attempt\\(s\\)"):
        brain.complete(MESSAGES)
    assert len(transport.calls) == 2


def test_unknown_param_is_rejected_not_silently_ignored():
    brain, _ = make_brain([("ok", RESPONSE_BODY)])
    with pytest.raises(ValueError, match="temperature"):
        brain.complete(MESSAGES, temperature=0.2)


# -- rate-limit fail-soft ------------------------------------------------------

def test_rate_limit_retries_once_then_raises_rate_limit_guidance():
    """429 may heal; after retries are spent we raise — naming the problem,
    never the key."""
    rate_limited = urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/x", 429,
        "Too Many Requests", EmailMessage(), None)
    brain, transport = make_brain(
        [("err", rate_limited)] * 2, retries=1, retry_wait=1.0)
    with pytest.raises(GeminiUnavailable, match="rate limit"):
        brain.complete(MESSAGES)
    assert len(transport.calls) == 2  # exactly retries + 1 attempts
    for call in transport.calls:
        assert SECRET not in str(call)  # key never rides in the URL/recorded payload


def test_rate_limit_honors_retry_after_header(monkeypatch):
    """Retry-After seconds are used as the gentle backoff."""
    headers = EmailMessage()
    headers["Retry-After"] = "2"
    rate_limited = urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/x", 429,
        "Too Many Requests", headers, None)
    brain, transport = make_brain(
        [("err", rate_limited), ("ok", RESPONSE_BODY)], retries=1,
        retry_wait=1.0)
    sleeps = []
    monkeypatch.setattr(time, "sleep", lambda d: sleeps.append(d))
    completion = brain.complete(MESSAGES)
    assert completion.text == "Thought: done\nFinal Answer: three"
    assert sleeps == [2.0]                 # obeyed Retry-After: 2 seconds
    assert len(transport.calls) == 2       # one retry, then success


def test_other_http_errors_still_raise_immediately():
    """A 403 is not rate-limited; retrying it cannot heal a bad key."""
    forbidden = urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/x", 403, "Forbidden",
        EmailMessage(), None)
    brain, transport = make_brain([("err", forbidden)], retries=3)
    with pytest.raises(GeminiUnavailable, match="HTTP 403"):
        brain.complete(MESSAGES)
    assert len(transport.calls) == 1       # NO retry: the server spoke



# -- live smoke (real key, real Google, tiny; SKIPS when the key is absent) ----

def _key_present() -> bool:
    import os
    return bool(os.environ.get("GEMINI_API_KEY"))


@pytest.mark.skipif(not _key_present(),
                    reason="no GEMINI_API_KEY in env — live smoke skipped "
                           "honestly (offline suite stays instant and keyless)")
def test_live_gemini_first_words():
    brain = GeminiBrain(max_output_tokens=64, timeout=60)
    completion = brain.complete(
        [Message(role="user", content='Reply with exactly: OK')])
    assert completion.text.strip(), "live model returned empty text"
    assert "gemini" in completion.model.lower()
    assert completion.prompt_tokens > 0   # Google reports REAL counts
