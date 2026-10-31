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

from dataclasses import dataclass

from . import narrate as N
from .brain import Brain, Completion
from .memory import ContextWindow
from .registry import ToolRegistry
from .tools import default_tools


@dataclass
class AgentResult:
    """The agent's structured output: the ANSWER plus the OUTCOME of the run.

    Answer and outcome are deliberately separate. The answer is model-produced text;
    the outcome is our bookkeeping about how the run ended (which loop guard fired).
    If we folded the outcome into the answer string, we would pollute the model's
    text and make the status unreliably parseable.
    """

    text: str              # the answer (today: the last assistant turn; M5: the "Final Answer:" text)
    terminate_reason: str  # how the loop ended — always "max_steps" in M2; M5 adds "final_answer" / failure policy
    steps: int             # loop turns that actually ran
    tokens: int            # context token_count after the run (for narration / CLI / trace)


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
        registry: ToolRegistry | None = None,
    ):
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1")
        self.brain = brain
        self.max_steps = max_steps
        self.budget_tokens = budget_tokens
        self.narrate = narrate
        # M3.5 wiring: an agent comes WITH its hands. None -> default_tools()
        # (one fresh world, private to this agent); an explicitly passed empty
        # registry is honored too — the no-tools lesson is one line away.
        self.registry = registry if registry is not None else default_tools()
        self.memory = ContextWindow(
            system=self._compose_system_prompt(system_prompt),
            budget_tokens=budget_tokens,
        )
        self.step_count = 0
        self.result: AgentResult | None = None

    def _compose_system_prompt(self, system_prompt: str) -> str:
        """Paste the hands into the prompt: system text + the catalogue block.

        The catalogue is rendered FROM the registry (M3.2) — pasted, never
        retyped — so what the model reads here is byte-for-byte the same
        documentation the M4 loop will resolve against. M4 will extend THIS
        helper with the 'how to call' instructions; the loop itself stays
        untouched until then (the SEAM below still says M4 — honestly today,
        because no text the model produces is parsed or acted on yet).
        """
        return system_prompt.rstrip() + "\n\n" + self.registry.render_catalogue()

    def run(self, task: str) -> AgentResult:
        """Take one task through the skeleton loop; return the run's result.

        Memory persists on the agent: call run() again and the transcript keeps
        growing — a single Agent instance is a single session.
        """
        self.memory.add("user", task)
        if self.narrate:
            N.info(
                f"task entered memory · context now {len(self.memory)} messages · "
                f"{self.memory.token_count()} tokens (budget {self.budget_tokens})"
            )
            N.info(
                f"tools wired · {len(self.registry)} tools: "
                f"{', '.join(self.registry.names())}"
            )
            N.info(
                "the loop still cannot act on them — the protocol that turns model "
                "text into ToolCall is M4's; today every reply is just memorized"
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

        self.result = AgentResult(
            text=self.memory.messages[-1].content,
            terminate_reason="max_steps",
            steps=self.step_count,
            tokens=self.memory.token_count(),
        )
        return self.result

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