"""Token estimation.

Real LLMs tokenize text into subword tokens; a model's context limit is measured in
those tokens. We don't ship a tokenizer in the agent core, so we estimate:
  ~4 characters ~ 1 token.
It is deliberately approximate — good enough to teach "context grows, watch the budget",
which is what memory.py will use later.
"""


def estimate_tokens(text: str) -> int:
    """Estimate how many tokens a string of text costs."""
    return max(1, len(text) // 4)