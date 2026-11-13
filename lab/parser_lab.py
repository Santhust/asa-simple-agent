#!/usr/bin/env python3
"""lab/parser_lab.py — poke the reader (M4.7)

One internal at a time: feed good and broken letters to the parser,
watch every intermediate. Also demo the flipped seam with MockBrain.
"""

import sys
from pathlib import Path

# labs are script-first, never installed
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from asa.protocol_react import parse
from asa.agent import Agent
from asa.brain import MockBrain
from asa import narrate as N


def demo_parser():
    N.h1("Reader demo: good letter")
    text = """Thought: I need to compute 2+2.
Action: calculator
Action Input: expression='2+2'
"""
    r = parse(text)
    print("kind:", r.kind)
    print("action:", r.action)
    print()

    N.h1("Reader demo: broken letter (missing Action Input)")
    text2 = """Thought: hmm
Action: calculator
"""
    r2 = parse(text2)
    print("kind:", r2.kind)
    print("note:", r2.error.message if r2.error else None)
    print()

    N.h1("Reader demo: Final Answer")
    text3 = """Thought: done
Final Answer: 4
"""
    r3 = parse(text3)
    print("kind:", r3.kind)
    print("answer:", r3.answer)
    print()


def demo_agent_flipped():
    N.h1("Agent demo: reads and acts (flipped seam)")
    # Model first calls calculator, then gives final answer
    brain = MockBrain(script=[
        "Thought: add them\nAction: calculator\nAction Input: expression='2+2'",
        "Thought: done\nFinal Answer: 4",
    ])
    agent = Agent(brain, narrate=True, max_steps=5)
    result = agent.run("what is 2+2?")
    N.h1("Result")
    print("terminate_reason:", result.terminate_reason)
    print("answer:", result.text)
    print("steps:", result.steps)


if __name__ == "__main__":
    demo_parser()
    demo_agent_flipped()
