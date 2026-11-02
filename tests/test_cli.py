"""Tests for run.py's CLI — the agent's mouthpiece.

The front door must run the Agent end to end, narrate the memory layer, and print a
structured result — all deterministically (scripted MockBrain, controlled color).
These drive main(argv) in-process so they are fast and need no subprocesses.
"""

import pytest

import asa.narrate as narrate
import run


def test_run_answers_with_scripted_brain(monkeypatch, capsys):
    """Demonstrates: the CLI turns a scripted brain into a full narrated run.

    Colors are forced off here — this test asserts CONTENT, color gets its own case.
    """
    monkeypatch.setattr(narrate, "_NO_COLOR", True)
    rc = run.main([
        "--task", "count to three",
        "--script", "Thought: done\nFinal Answer: three",
        "--max-steps", "3",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "three" in out
    assert "memory before run:" in out
    assert "memory after run:" in out
    assert "answer: 'three'" in out
    assert "terminate_reason: final_answer" in out
    assert "steps: 1" in out


def test_max_steps_worded_as_the_guard(monkeypatch, capsys):
    """Demonstrates: without extra steps the CLI stops after ONE brain call."""
    monkeypatch.setattr(narrate, "_NO_COLOR", True)
    rc = run.main([
        "--task", "say hi",
        "--script", "Thought: done\nFinal Answer: first reply", "wasted reply",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "answer: 'first reply'" in out
    assert "steps: 1" in out
    assert "wasted reply" not in out


def test_explain_adds_why_and_trim_sections(capsys):
    """Demonstrates: --explain turns on the deeper pedagogic layers.

    The 'why' asides and the live trim() demonstration only appear when asked for.
    """
    run.main(["--task", "hi", "--script", "hello", "--explain"])
    out = capsys.readouterr().out
    assert "trim(budget=" in out          # the narrated forgetting demo
    assert "forgot " in out               # ... reports the eviction count
    assert "?" in out                     # the 'why' narration markers


def test_script_flag_reports_the_mock_override(monkeypatch, capsys):
    """Demonstrates: --script announces that the selected brain is being replaced.

    A quiet swap would be a foot-gun once real brains (ollama/gemini) exist —
    picking one and then passing --script must never be silent.
    """
    monkeypatch.setattr(narrate, "_NO_COLOR", True)
    run.main(["--task", "hi", "--script", "hello"])
    out = capsys.readouterr().out
    assert "--script is active" in out
    assert "'mock' is replaced by a scripted MockBrain" in out
    assert "zero real model calls" in out


def test_help_declares_script_intent(capsys):
    """Demonstrates: the CLI's own --help documents --script's purpose.

    Correct now (the teaching override), and it keeps the clue in front of users
    once real brains arrive.
    """
    with pytest.raises(SystemExit):
        run.parse_args(["--help"])
    out = capsys.readouterr().out
    assert "--script" in out
    assert "OVERRIDES" in out
    assert "teaching/demo mode" in out


def test_no_color_strips_ansi(monkeypatch, capsys):
    """Demonstrates: plain output has no escape sequences.

    Color is a module-level switch (narrate._NO_COLOR, also set by $NO_COLOR or
    --no-color); flipping it in-process proves the narrator honors it.
    """
    monkeypatch.setattr(narrate, "_NO_COLOR", True)
    run.main(["--task", "hi", "--script", "hello"])
    assert "\x1b[" not in capsys.readouterr().out

    monkeypatch.setattr(narrate, "_NO_COLOR", False)
    run.main(["--task", "hi", "--script", "hello"])
    assert "\x1b[" in capsys.readouterr().out


def test_ollama_flag_wired_to_the_first_real_brain():
    """Demonstrates: --brain ollama selects the real local brain (M7).

    The test stays OFFLINE: it checks the registry mapping and that argparse
    accepts the choice — a *construction* test, not a live call (network gets
    its own smoke test in test_m7_1_ollama_brain.py).
    """
    from asa.brain import OllamaBrain
    assert run.BRAINS["ollama"] is OllamaBrain
    args = run.parse_args(["--brain", "ollama"])
    assert args.brain == "ollama"
    brain = run.BRAINS["ollama"]()  # the exact construction path main() uses
    assert brain.model == "lfm3:latest"  # M7.0 decision: tag is a config string


def test_gemini_flag_wired_to_the_first_cloud_brain():
    """Demonstrates: --brain gemini selects the cloud brain (M8.2).

    Construction path only — no network, no key usage. M8.1's suite (with the
    fake transport and the live smoke) is where GeminiBrain's behavior lives.
    """
    from asa.brain import GeminiBrain
    assert run.BRAINS["gemini"] is GeminiBrain
    args = run.parse_args(["--brain", "gemini"])
    assert args.brain == "gemini"
    brain = run.BRAINS["gemini"]()
    assert brain.model == "gemini-3.5-flash-lite"   # M8.0 decision: a config string
    assert brain.thinking is False                  # M8.0 pin (amended note: no thinkingConfig sent)