"""M7.4 tests — bench: the same task across brains, side by side.

What each test demonstrates and why it matters:

  * record shape      : one honest row per brain — ok (PROCEDURAL), steps,
                        tokens, wall_s, terminate_reason, answer. Bench counts
                        obedience to the loop, never fakes semantic truth.
  * real throughput   : tok/s comes from OLLAMA's OWN counters (eval_count /
                        eval_duration, aggregated) — not a stopwatch around
                        agent.run(). Offline proven with the fake transport.
  * unknown brains    : --brains with a typo fails LOUD with the available
                        list (never a silent row of nothing).
  * json + table      : --json for tooling; table for humans (no rich deps —
                        script-first rule).
  * swappability proof: a two-brain bench works with ONE of them using a fake
                        transport O(nline) — bench never needs the network to
                        be correct offline.

Determinism note: all of this is MockBrain + fake transport — Ollama itself
gets exactly ONE live pin per close-out (the task rate is the Pi5's cost).
"""

import json as json_lib

import pytest

from asa.brain import Message, MockBrain, OllamaBrain
import bench


RESPONSE_BODY = {
    "model": "lfm3:latest",
    "message": {"role": "assistant", "content": "Final Answer: 42"},
    # Ollama reports eval_count (tokens) and eval_duration (ns). 9 tokens in
    # 3e9 ns => 3.0 tok/s, so bench throughput math is testable exactly.
    "prompt_eval_count": 420,
    "eval_count": 9,
    "eval_duration": 3_000_000_000,
}


class FakeTransport:
    def __init__(self, body):
        self._body = body

    def __call__(self, url, payload, timeout):
        return 200, self._body


def fast_mock():
    return MockBrain(script=["Final Answer: 42"])


def offline_ollama():
    return OllamaBrain(transport=FakeTransport(RESPONSE_BODY), num_predict=32)


# -- records ------------------------------------------------------------------

def test_records_have_honest_shape_for_two_brains():
    records = bench.run_bench("What is 7*6? Use the calculator tool.",
                              {"mock": fast_mock, "ollama": offline_ollama})
    assert [r["brain"] for r in records] == ["mock", "ollama"]
    for r in records:
        assert r["ok"] is True                     # PROCEDURAL success only
        assert r["terminate_reason"] == "final_answer"
        assert r["answer"] == "42"
        assert r["steps"] >= 1
        assert r["tokens"] >= 0
        assert r["wall_s"] >= 0.0
    # the mock has no Ollama counters -> no tok/s key (absent, not 0-faked)
    assert "tok_per_s" not in records[0]
    assert records[1]["tok_per_s"] == 3.0          # 9 tokens / 3 s, server-reported


def test_conversation_token_realism_into_bench_record():
    """ Tokens: OllamaBrain reports REAL prompt/completion tokens (M7.1);
    bench surfaces them so comparison vs MockBrain's estimates is visible. """
    records = bench.run_bench("hi", {"ollama": offline_ollama})
    assert records[0]["tokens"] > 0  # Completion.output_tokens mapped va estimates


# -- CLI ----------------------------------------------------------------------

def test_cli_table_and_json_surfaces(monkeypatch, capsys):
    # bench is a REAL-brain tool (no --script flag); tests inject their own
    # deterministic mock factory through the same dict the CLI consumes.
    monkeypatch.setitem(bench.BRAIN_FACTORIES, "mock", fast_mock)
    rc = bench.main(["--task", "What is 7*6? Use the calculator tool.",
                     "--brains", "mock", "--max-steps", "3"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PROCEDURAL success" in out
    assert "mock" in out and "mock-1" in out


def test_cli_json_is_machine_readable(monkeypatch, capsys):
    monkeypatch.setitem(bench.BRAIN_FACTORIES, "mock", fast_mock)
    rc = bench.main(["--task", "What is 7*6? Use the calculator tool.",
                     "--brains", "mock", "--json"])
    out = capsys.readouterr().out
    assert rc == 0
    records = json_lib.loads(out)
    assert records[0]["brain"] == "mock"
    assert records[0]["terminate_reason"] == "final_answer"


def test_unknown_brain_fails_loud_with_available_list(capsys):
    rc = bench.main(["--task", "hi", "--brains", "mock,copilot"])
    out = capsys.readouterr().out
    assert rc == 2
    assert "copilot" in out and "'mock', 'ollama'" in out


# -- throughput accumulates over turns (not last-call only) -------------------

def test_throughput_aggregates_across_calls():
    brain = OllamaBrain(transport=FakeTransport(RESPONSE_BODY))
    brain.complete([Message(role="user", content="a")])
    brain.complete([Message(role="user", content="b")])
    assert brain.total_eval_count == 18
    assert brain.total_eval_duration == pytest.approx(6.0)
