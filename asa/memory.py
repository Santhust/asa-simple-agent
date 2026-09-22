"""ContextWindow: the agent's memory.

A ReAct agent "remembers" nothing on its own — every call to the brain must carry the
whole conversation so far. The ContextWindow is that conversation: an ordered,
token-budgeted transcript of role-tagged Message objects.

It is deliberately a PURE data structure — no printing, no narration, no brain calls.
That keeps it trivially testable, and lets the Agent (agent.py) decide what to narrate.

The one rule that matters (use it to read this file):
  * the system prompt is sacred — trimming never touches it
  * on overflow we evict the OLDEST user/assistant turn, never the most recent one
"""

from .brain import Message
from .tokens import estimate_tokens


class ContextWindow:
    """An ordered transcript of messages, optionally bounded by a token budget.

    budget_tokens is a soft cap: the window does NOT trim automatically on add()
    — trimming is an explicit act (trim()), so nobody hides the moment memory
    gets thrown away. That choosing-to-forget moment is worth seeing.
    """

    def __init__(self, system: str | None = None, budget_tokens: int | None = None):
        self._messages: list[Message] = []
        if system is not None:
            self._messages.append(Message(role="system", content=system))
        self.budget_tokens = budget_tokens

    # ---- reading -----------------------------------------------------------
    @property
    def messages(self) -> list[Message]:
        """A copy of the transcript (callers cannot mutate memory behind our back)."""
        return list(self._messages)

    def token_count(self) -> int:
        """Estimated tokens of the whole transcript (uses tokens.estimate_tokens)."""
        return sum(estimate_tokens(m.content) for m in self._messages)

    def __len__(self) -> int:
        return len(self._messages)

    # ---- writing ------------------------------------------------------------
    def add(self, role: str, content: str) -> Message:
        """Append one turn. role: 'system' | 'user' | 'assistant'."""
        msg = Message(role=role, content=content)
        self._messages.append(msg)
        return msg

    def trim(self, budget: int | None = None) -> int:
        """Drop oldest non-system turns until within budget; return how many dropped.

        Guarantees:
          * the system message is never dropped (it is the standing instruction)
          * the most recent turn is never dropped (a context that forgets its
            newest message stops making sense to the model)
          * if a single turn alone busts the budget, we keep it anyway and accept
            the overrun — one fresh message beats an empty, "in-budget" context
        """
        budget = self.budget_tokens if budget is None else budget
        if budget is None:
            return 0

        dropped = 0
        while self.token_count() > budget:
            first_movable = next(
                (i for i, m in enumerate(self._messages) if m.role != "system"),
                None,
            )
            non_system_count = sum(1 for m in self._messages if m.role != "system")
            if first_movable is None or non_system_count <= 1:
                break  # nothing left to forget without breaking a guarantee
            del self._messages[first_movable]
            dropped += 1
        return dropped