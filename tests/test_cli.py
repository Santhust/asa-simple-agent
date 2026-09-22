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

    Three scripted replies + --max-steps 3 -> three loop turns, the last reply is
    the answer, and termination honestly reports the step budget in M2.
    Colors are forced off here — this test asserts CONTENT, color gets its own case.
    """
    monkeypatch.setattr(narrate, "_NO_COLOR", True)
    rc = run.main([
        "--task", "count to three",
        "--script", "one", "two", "three",
        "--max-steps", "3",
    ])
    out = capsys.readouterr().out
    assert rc == 0
    assert "one" in out and "two" in out and "three" in out
    assert "memory before run:" in out
    assert "memory after run:" in out
    assert "answer: 'three'" in out
    assert "terminate_reason: max_steps" in out
    assert "steps: 3" in out


def test_max_steps_worded_as_the_guard(monkeypatch, capsys):
    """Demonstrates: without extra steps the CLI stops after ONE brain call."""
    monkeypatch.setattr(narrate, "_NO_COLOR", True)
    rc = run.main([
        "--task", "say hi",
        "--script", "first reply", "wasted reply",
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