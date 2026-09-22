"""Agent: the orchestration around a brain.

The Brain is a text-in / text-out box — deliberately stupid. The Agent is where the
intelligence of PROCEDURE lives: build the conversation, feed the brain, record the
reply back into memory, and narrate every important moment.

This milestone takes exactly ONE step (task in → brain out → memorized), but the
loop skeleton is already real: memory is created, the user task enters it, the brain
is called, and the reply is stored back. The `for step in range(max_steps)` harness
and the SEAM comment below mark exactly where M4 (ReAct parsing) and M5
(Final-Answer detection, tool hooks) plug in — without reshaping anything.
"""

from __future__ import annotations

from . import narrate as N
from .brain import Brain, Completion
from .memory import ContextWindow


class Agent:
    """One agent = one conversation session (one ContextWindow), with ANY brain.

    Swap the brain and nothing in here changes — that is the whole point of the
    Brain abstraction: to the agent, a model is text-in/text-out, full stop.
    """

    def __init__(
        self,
        brain: Brain,
        system_prompt: str = "You are 'asa', a teaching agent built from scratch.",
        max_steps: int = 1,
        budget_tokens: int | None = None,
        narrate: bool = True,
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        self.brain = brain
        self.max_steps = max_steps
        self.budget_tokens = budget_tokens
        self.narrate = narrate
        self.memory = ContextWindow(system=system_prompt, budget_tokens=budget_tokens)
        self.step_count = 0
        self.answer: str | None = None

    def run(self, task: str) -> str:
        """Take one task through the skeleton loop; return the final answer.

        Memory persists on the agent: call run() again and the transcript keeps
        growing — a single Agent instance is a single session.
        """
        self.memory.add("user", task)
        if self.narrate:
            N.info(
                f"task entered memory · context now {len(self.memory)} messages · "
                f"{self.memory.token_count()} tokens (budget {self.budget_tokens})"
            )

        for step in range(self.max_steps):
            self.step_count += 1
            if self.narrate:
                self._narrate_context()

            # ---- THE SEAM (M4 / M5) ----------------------------------------
            #   after each brain response the real loop will:
            #     1. let protocol_react parse Thought:/Action:/Action Input:
            #     2. if Action: resolve + run the tool via the registry, store
            #        the Observation back into memory, and keep looping
            #     3. break as soon as 'Final Answer:' is seen or steps run out
            #   None of that exists yet — today we just ask and memorize.
            completion = self.brain.complete(self.memory.messages)
            self.memory.add("assistant", completion.text)
            if self.narrate:
                self._narrate_completion(completion)

        self.answer = self.memory.messages[-1].content
        return self.answer

    # ---- narration (front-of-house; memory.py stays pure) ------------------
    def _narrate_context(self) -> None:
        N.info(
            f"context #{self.step_count}: {len(self.memory)} messages · "
            f"{self.memory.token_count()} tokens"
        )
        for m in self.memory.messages:
            N.code(m.render())

    def _narrate_completion(self, c: Completion) -> None:
        N.kv(f"brain said · model {c.model!r}", repr(c.text))