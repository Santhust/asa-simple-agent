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
from .brain import Brain, Completion, GeminiUnavailable, OllamaUnavailable
from .memory import ContextWindow
from .protocol_native import build_tools_payload, parse_function_call
from .protocol_react import parse
from .registry import ToolRegistry
from .tool import ToolCall
from .tools import default_tools
from .trace import get_run_id, reset_session, write_event


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
        """Paste the hands into the prompt: system text + catalogue + how-to-call.

        The catalogue is rendered FROM the registry (M3.2) — pasted, never
        retyped — so what the model reads here is byte-for-byte the same
        documentation the M4 loop will resolve against. We now add the
        ReAct "how to write the letter" instructions after the catalogue.
        """
        base = system_prompt.rstrip() + "\n\n" + self.registry.render_catalogue()
        howto = """

## How to call tools (ReAct)
When you need to use a tool, write EXACTLY this form:
Thought: <why you are doing this>
Action: <tool name from the list above>
Action Input: <key=value pairs, or a JSON object>. Use the parameter names shown.

To answer directly (no tool), write:
Thought: <brief reasoning>
Final Answer: <your answer>

If a message comes back starting with "Observation:", read it and continue.
If you see a gentle note about fixing your letter, correct the format and try again.
"""
        return base + howto

    def run(self, task: str) -> AgentResult:
        """Take one task through the skeleton loop; return the run's result.

        Memory persists on the agent: call run() again and the transcript keeps
        growing — a single Agent instance is a single session.
        """
        # M8.4.1: every run gets its own identity (run_id) so the detective can
        # separate one run's events from another's in the shared trace file.
        reset_session()
        run_id = get_run_id()
        write_event("session.start", {"task": task, "run_id": run_id})

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
                "the M4 reader turns each reply into action / observation / answer "
                "— this run's every internal step lands in asa/traces/trace.jsonl (M6)"
            )

        for step in range(self.max_steps):
            self.step_count += 1
            if self.narrate:
                self._narrate_context()

            # ---- THE SEAM (M4.6 + M9: two protocols, one core) ----
            # Which protocol does this brain speak? The brain decides (supports_native);
            # the loop only asks. Textual ReAct (M4) parses a prose letter; native (M9)
            # reads the structured functionCall the API produced — no regex, no repair.
            # native is only real when the brain offers tool schemas, so an empty
            # registry falls back to text mode automatically.
            native = self.brain.supports_native() and len(self.registry) > 0
            tools = build_tools_payload(self.registry) if native else None

            # M6.3b ordering: brain.request emits BEFORE the call — the snapshot
            # must not contain the reply it claims to prompt.
            write_event("brain.request", {
                "prompt": [m.render() for m in self.memory.messages],
                "protocol": "native" if native else "react",
            })

            try:
                completion = (self.brain.complete(self.memory.messages, tools=tools)
                              if native else self.brain.complete(self.memory.messages))
            except (OllamaUnavailable, GeminiUnavailable) as e:
                # M8.4.4: brain failures are recorded as trace events, not
                # propagated as crashes. The detective needs them in evidence.
                msg = str(e).lower()
                failure_kind = "rate_limited" if ("429" in msg or "too many requests" in msg) else "network"
                write_event("brain.response", {"text": "", "error": str(e), "failure": failure_kind})
                write_event("loop.terminate", {"reason": failure_kind, "failure": failure_kind})
                self.result = AgentResult(
                    text="",
                    terminate_reason=failure_kind,
                    steps=self.step_count,
                    tokens=self.memory.token_count(),
                )
                return self.result

            reply = completion.text
            write_event("brain.response", {"text": reply, "model": completion.model})
            self.memory.add("assistant", reply)
            if self.narrate:
                self._narrate_completion(completion)

            # ---- THE SEAM (M4.6 + M9) ---------------------------------------
            if native:
                # Native function-calling path: the API hands us structured calls
                # — no regex, no kwargs parser, no repair, args already typed.
                write_event("protocol.raw", {"raw": reply,
                                             "tool_calls": completion.tool_calls})
                verdict = parse_function_call(completion)
            else:
                # Textual ReAct path: parse the letter.
                write_event("protocol.raw", {"raw": reply})
                verdict = parse(reply)

            if verdict.kind == "thought_action" and verdict.action is not None:
                # Run the tool, put Observation back into memory
                call: ToolCall = verdict.action
                write_event("protocol.parsed", {"kind": verdict.kind, "tool": verdict.action.name, "args": verdict.action.args})
                write_event("tool.lookup", {"name": call.name})
                tool = self.registry.get(call.name)
                if tool is None:
                    obs = f"Observation: no tool named '{call.name}'. Available: {', '.join(self.registry.names())}"
                    self.memory.add("user", obs)
                    if self.narrate:
                        N.info(f"tool lookup failed · {obs}")
                    continue  # keep looping so the model can try again
                write_event("tool.invoke", {"name": call.name, "args": call.args})
                try:
                    result = tool.run(call.args)
                    obs = f"Observation: {result.output}"
                    if result.is_error:
                        obs = f"Observation (error): {result.output}"
                except Exception as e:
                    obs = f"Observation (error): tool '{call.name}' crashed: {e}"
                is_error = getattr(result, 'is_error', False) if 'result' in locals() else False
                failure_kind = "tool_error" if is_error else None
                result_payload = {"name": call.name, "output": result.output if 'result' in locals() else str(obs), "error": is_error}
                if failure_kind:
                    result_payload["failure"] = failure_kind
                write_event("tool.result", result_payload)
                self.memory.add("user", obs)
                if self.narrate:
                    N.info(f"tool ran · {call.name} -> {obs[:80]}...")
                continue  # loop again with observation in memory
            elif verdict.kind == "error" and verdict.error is not None:
                error_msg = verdict.error.message
                failure_kind = "empty_reply" if error_msg == "empty reply" else "protocol_drift"
                write_event("protocol.error", {"message": error_msg, "failure": failure_kind})
                obs = f"Observation: {verdict.error.message}"
                self.memory.add("user", obs)
                if self.narrate:
                    N.info(f"parse error -> observation back to model")
                continue
            elif verdict.kind == "final_answer":
                write_event("agent.answer", {"answer": verdict.answer or reply, "steps": self.step_count})
                self.result = AgentResult(
                    text=verdict.answer or reply,
                    terminate_reason="final_answer",
                    steps=self.step_count,
                    tokens=self.memory.token_count(),
                )
                write_event("loop.terminate", {"reason": "final_answer"})
                return self.result

            write_event("loop.turn", {"iteration": self.step_count})

        self.result = AgentResult(
            text=self.memory.messages[-1].content,
            terminate_reason="max_steps",
            steps=self.step_count,
            tokens=self.memory.token_count(),
        )
        write_event("loop.terminate", {"reason": "max_steps", "failure": "budget_exhausted"})
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