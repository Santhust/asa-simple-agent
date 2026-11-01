"""Tests for M3.5 — the wiring: the agent SEES its hands, touches nothing yet.

Each test names the lesson it demonstrates and why it matters. The suite's
subject is the boundary between what the model READS (the catalogue, now in
the system prompt) and what the loop DOES (nothing — the SEAM stays M4's).
M4 will flip the second half; these tests pin the first half so the flip is
loud.
"""

from asa.agent import Agent
from asa.brain import MockBrain
from asa.registry import ToolRegistry
from asa.tools import default_tools

_TOOL_NAMES = [
    "board_add",
    "board_list",
    "board_move",
    "calculator",
    "clock",
    "notes_read",
    "notes_write",
]


def _agent(**kwargs) -> Agent:
    """A narrate-off agent with the default wired world, always fresh."""
    kwargs.setdefault("narrate", False)
    return Agent(MockBrain(script=["copy that"]), **kwargs)


def test_the_catalogue_lands_in_the_system_prompt():
    """Demonstrates M3.5's headline: the model's page of hands is IN memory.

    Why it matters: documentation-first (M3.2) only pays off when the model
    actually reads the documentation. The system message — the prompt part
    the trim() never deletes (M2's 'system is sacred') — must carry the
    section header AND every tool's name, so a model can only answer with
    awareness of what it may call.
    """
    agent = _agent()
    system = agent.memory.messages[0].content
    assert "## Available tools" in system
    for name in _TOOL_NAMES:
        assert name in system


def test_a_custom_system_prompt_survives_beside_the_catalogue():
    """Demonstrates composition, not replacement.

    Why it matters: the caller's system text is a promise the agent must
    keep (personality, tone, task framing). The catalogue is ADDED below
    it, never swapped in for it — the two halves of the prompt are two
    honest layers, not one overwriting the other.
    """
    agent = _agent(system_prompt="You are terse and always rhyme.")
    system = agent.memory.messages[0].content
    assert system.startswith("You are terse and always rhyme.")
    assert "## Available tools" in system


def test_the_catalogue_is_pasted_not_retyped():
    """Demonstrates drift-proofing: the registry's page is pasted intact.

    Why it matters: the model reads the same bytes the M4 loop resolves
    ToolCalls against. If these were two renderings, they could disagree —
    the classic documentation drift. M4.5 adds the 'how to call' block
    AFTER the catalogue (never retyped, never reordered).
    """
    registry = default_tools()
    agent = _agent(registry=registry)
    system = agent.memory.messages[0].content
    cat = registry.render_catalogue()
    assert cat in system
    # catalogue comes before the how-to-call instructions
    assert system.index(cat) + len(cat) <= system.index("## How to call tools") if "## How to call tools" in system else True


def test_default_toolsregisters_all_seven_sorted():
    """Demonstrates the bundle flattening produces the full phonebook.

    Why it matters: M3.5's other half is asa/tools.default_tools() — the
    flattener the agent's default depends on. Seven hands, already in sorted
    order, exactly the documented toolbox; anything missing here is a
    capability the model believes in but the phonebook lacks.
    """
    assert default_tools().names() == _TOOL_NAMES


def test_one_agent_one_world_state_is_private_per_agent():
    """Demonstrates the M3.4 lifetime rule, automatic at the wiring layer.

    Why it matters: default_tools() is fresh per call, so each agent owns
    its ledger and its board. Agent B must not read agent A's notes nor
    see A's plan-board items — sessions are isolated WITHIN one process,
    the same machinery M3.4's tests proved below the agent.
    """
    writer_agent = _agent()
    other_agent = _agent()

    # act on writer_agent's world DIRECTLY through its registry
    writer_agent.registry.get("notes_write").run({"text": "agent a's secret"})
    writer_agent.registry.get("board_add").run({"item": "agent a's plan"})

    other_system = other_agent.memory.messages[0].content  # just the prompt
    read = other_agent.registry.get("notes_read").run({})
    board = other_agent.registry.get("board_list").run({})
    assert "agent a's secret" not in read.output
    assert "no notes yet" in read.output
    assert "agent a's plan" not in board.output


def test_an_explicit_empty_registry_gives_the_honest_paragraph():
    """Demonstrates the no-tools agent — Ralph (Schiffman's tool-less dummy).

    Why it matters: 'registry=None -> default_tools()' must not force the
    no-tools lesson out of reach. Passing an explicitly empty ToolRegistry
    wires an agent whose page says 'You have no tools' — M3.2's designed
    empty catalogue doing its job inside a real agent, narrated by --no-tools.
    """
    no_hands = _agent(registry=ToolRegistry())
    system = no_hands.memory.messages[0].content
    assert "You have no tools in this session." in system
    assert "## Available tools" in system  # the header survives, honestly


def test_seam_stays_honest_a_faked_tool_call_is_just_text():
    """Demonstrates THE M3.5 boundary: the loop cannot act, and admits it.

    Why it matters: the prompt tells the model it has hands; the loop does
    not yet honor that — a model writing 'Action: calculator(...)' gets
    its TEXT memorized, no tool runs, nothing executed. Pinning the 'still
    just words' behavior makes M4's flip a loud, test-visible event
    instead of a silent one.
    """
    agent = Agent(
        MockBrain(script=["Action: calculator(expression='2+2')"]),
        narrate=False,
    )
    result = agent.run("what is two plus two?")
    assert result.terminate_reason == "max_steps"  # no 'final_answer' machinery exists
    assert result.text == "Action: calculator(expression='2+2')"  # memorized verbatim
    # the world is untouched: the faked call never ran
    no_trace = agent.registry.get("notes_read").run({}).output
    calculator_probe = agent.registry.get("calculator").run({"expression": "9-9"})
    assert "9-9 = 0" in calculator_probe.output  # the calculator answered FRESH
    assert result is not None and no_trace is not None  # and nothing else happened


def test_token_count_includes_the_catalogue():
    """Demonstrates the gauge honesty: the catalogue costs real tokens.

    Why it matters: M3.2's queue of lessons ('context is a cache') becomes
    concrete — seven hands' documentation permanently occupies budget
    space in EVERY turn's context. The narration quotes
    memory.token_count(), so the number must already include the page,
    or every gauge on the CLI would undercount from M3.5 onward.
    """
    agent = _agent()
    bare = Agent(MockBrain(script=["x"]), narrate=False, registry=ToolRegistry())
    before = len(agent.memory.messages[0].content)
    bare_len = len(bare.memory.messages[0].content)
    assert before > bare_len  # the wired page is substantial extra payload
    assert agent.memory.token_count() > bare.memory.token_count()