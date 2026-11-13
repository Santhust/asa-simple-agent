# asa — a simple agent

A ReAct agent written from scratch in Python, to learn how agentic AI actually works.

Not a product, not a framework, no magic. Every internal is observable on purpose, and every
milestone ships with tests, a narrated demo, and a lesson you can read. The whole agent runs on
the standard library — `pytest` is the only dependency.

The name is the joke: **a** **s**imple **a**gent.

## The idea

An agent is a loop. The model is a text box; the harness gives it a memory, a question, and a
set of hands, then keeps feeding it back its own results until it stops.

```
        ┌──────────────────────────────────────────────────────┐
        │                                                      │
Task ──► ContextWindow ──► Brain ──► protocol ──► ToolCall ──────┤
                                ▲                 (name, args)  │
                                │                                ▼
                                └──── observation ◄──── ToolRegistry
                                     (tool runs)
```

The loop terminates on `Final Answer:`, on a step budget, or by the failure policy.

The one design decision that matters: **the core only ever speaks `ToolCall(name, args)`.** How
that call arrives in text is somebody else's problem — which is exactly why there are two
protocol adapters underneath:

| Protocol | File | How the model is asked |
|---|---|---|
| Textual ReAct | `asa/protocol_react.py` | `Thought:` / `Action:` / `Action Input:` — universal, works with any model that can write |
| Native function-calling | `asa/protocol_native.py` | API tool payloads (e.g. Gemini `tools=[...]`) — the model returns structured calls |

Same agent, same tools, same tests. Swapping protocols is a config change, not a rewrite.

## The brain zoo

A model is a text-in / text-out box. Swapping brains **is** the lesson — the agent code never
changes.

| Brain | Default | Why it exists |
|---|---|---|
| `MockBrain` | `mock-1` | Deterministic and offline. Tests, golden traces, demos with zero dependencies. |
| `OllamaBrain` | `lfm3:latest` | Local, private, free. Runs on a Raspberry Pi 5 (8 GB) at ~7 tok/s. Stdlib HTTP, no SDK. |
| `GeminiBrain` | `gemini-3.5-flash-lite` | First cloud member. Big model, free tier, key read from `GEMINI_API_KEY`. |

The cloud brain takes its key from the `GEMINI_API_KEY` environment variable only, sends it in
the `x-goog-api-key` header, and never puts it in a URL, a log, or a trace.

## Quickstart

```bash
pip install -r requirements.txt

# offline rehearsal, no model needed: --script swaps in canned brain replies,
# so you can watch the real loop — tool call, observation, final answer
python run.py --task "what is 12 * 12?" --max-steps 4 \
  --script "Thought: I need the calculator
Action: calculator
Action Input: expression=12*12" "Thought: done
Final Answer: 144"

# local model (needs ollama serving localhost:11434 and the model pulled)
python run.py --task "what is 12 * 12?" --brain ollama --max-steps 6

# cloud model
export GEMINI_API_KEY="..."
python run.py --task "what is 12 * 12?" --brain gemini
```

The scripted run above really does execute the calculator: the trace shows
`Observation: 12*12 = 144`, then `terminate_reason: final_answer`, `steps: 2`.

Useful flags: `--explain` (deeper "why" annotations), `--script` (feed the brain a canned
script), `--no-tools`, `--native` (function-calling protocol), `--no-color`.

Same task across brains, side by side:

```bash
python bench.py --task "what is 12 * 12?" --brains mock,ollama
```

`ok` in the bench table means **procedural** success — the loop finished the way it should — never
a claim about truth.

Every run writes a JSONL trace to `asa/traces/trace.jsonl`: steps, prompts, tool calls,
observations, token counts. That file is the raw material for the playground.

Tests:

```bash
python -m pytest          # 197 tests: 196 passed, 1 skipped
```

## Poking one internal at a time

No install, no setup — each lab is a script that isolates a single piece of the machine:

```bash
python lab/parser_lab.py       # how "Action: calculator" becomes structured text
python lab/registry_lab.py     # the phonebook, and the manual page the model reads
python lab/tool_lab.py         # what a tool actually is
python lab/tools_lab.py        # the shipped tools: calculator, clock, notes, plan board
python lab/state_lab.py        # notes + plan board: state outside the hands
python lab/detective_lab.py    # read a trace and reconstruct what happened
```

## Reading material

| Path | What it is |
|---|---|
| `PLAN.md` | The full game plan: milestones, status, the reasoning behind each step |
| `AGENTS.md` | Project conventions, architecture notes, working rhythm |
| `docs/asa-docs.html` | Seven illustrated lessons, open directly in a browser |
| `playground/index.html` | Interactive playground: animated architecture, trace player, breakage lab, two-protocol comparison, model zoo, quiz |
| `docs/m1-diagram.svg` | The living architecture diagram — solid = built, dashed = planned |
| `docs/timeline.html` | Offline prev/next deck of the journey, one frame per stage |
| `docs/decisions-archive.md` | Detail from the early milestones, read on demand |

Both HTML files are fully self-contained and need no server. The playground plays pre-recorded
traces, so it works offline.

## License

asa — a simple agent
Copyright (C) 2026 Santhust

This program is free software: you can redistribute it and/or modify it under the terms of the
GNU General Public License as published by the Free Software Foundation, version 3.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See
the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If
not, see <https://www.gnu.org/licenses/>.

The full license text is in [`LICENSE`](LICENSE).
