"""M7.3 tests — the REAL model's letters, frozen as deterministic regressions.

Provenance (WHY this matters): the strings below are captured VERBATIM from
live lfm3 runs on 2026-11-02 (see PLAN.md, M7.3). Live runs are slow, nondeterministic
and cost the Pi5 real seconds per step; freezing what a real 1.7B model
actually wrote turns the wild observation into an offline, instant lesson:

  1. a real model drifted: `Action Input: "7*6"` (bare value, no key=value)
     — the M4.3 gentle note caught it, and lfm3 READ the note and repaired
     itself into `{"expression": "7*6"}` on the very next turn (first
     self-repair ever executed by a real model in this project).
  2. with an amended M7.0 (think=True) the SAME model passed clean.
  3. lfm3 can even go SILENT — empty replies (run 1) met the gentle note,
     the loop stayed honest, and the run ended on the step budget instead
     of pretending to answer.

All three behaviors are replayed here through MockBrain — brain irony purely
deliberate: MockBrain replays the REAL model's letter word-for-word, so the
AGENT-side behavior (parse, repair, tool run, terminate) is pinned forever.
"""

from asa.agent import Agent
from asa.brain import MockBrain
from asa.trace import read_events

# -- captured verbatim from the live lfm3 run of 2026-11-02 -------------------

TASK = "What is 7*6? Use the calculator tool to compute it, then give the final answer."

LFM3_ACTION_DRIFT = (
    "Thought: I will use the calculator tool to evaluate the arithmetic expression 7*6.\n"
    'Action: calculator\nAction Input: "7*6"'
)

LFM3_REPAIRED = (
    "Thought: The previous call didn't properly format the arguments. I'll use the "
    "calculator tool with the correct parameter `expression`.\n"
    'Action: calculator\nAction Input: {"expression": "7*6"}'
)

LFM3_FINAL = "Final Answer: 42"


def test_real_drift_letter_gets_gentle_note_then_answer_still_lands():
    """Run 1 of the drift letter alone: tool NOT run, no crash, final still works."""
    agent = Agent(MockBrain(script=[LFM3_ACTION_DRIFT, LFM3_FINAL]),
                  narrate=False, max_steps=3)
    result = agent.run(TASK)
    assert result.terminate_reason == "final_answer"
    assert result.text == "42"
    assert result.steps == 2
    tool_runs = [e for e in read_events() if e.kind == "tool.invoke"]
    assert tool_runs == []  # the gentle note consumed the broken letter; nothing ran


def test_real_self_repair_executes_the_first_real_tool_call_shape():
    """Run 2, verbatim sequence: drift -> note -> repaired -> tool -> 42."""
    agent = Agent(MockBrain(script=[LFM3_ACTION_DRIFT, LFM3_REPAIRED, LFM3_FINAL]),
                  narrate=False, max_steps=4)
    result = agent.run(TASK)
    assert result.terminate_reason == "final_answer"
    assert result.steps == 3
    invoked = [e for e in read_events() if e.kind == "tool.invoke"]
    assert len(invoked) == 1
    assert invoked[0].payload["name"] == "calculator"
    assert invoked[0].payload["args"] == {"expression": "7*6"}
    results = [e for e in read_events() if e.kind == "tool.result"]
    assert "7*6 = 42" in str(results[-1].payload["output"])


def test_empty_letters_meet_the_gentle_note_too():
    """Run 0's surprise: silence is a letter lfm3 can write — the loop stays honest."""
    agent = Agent(MockBrain(script=["", "", ""]), narrate=False, max_steps=3)
    result = agent.run(TASK)
    assert result.terminate_reason == "max_steps"
    assert result.text == "Observation: empty reply"
    tool_runs = [e for e in read_events() if e.kind == "tool.invoke"]
    assert tool_runs == []  # silence never operated a tool — the guard held
