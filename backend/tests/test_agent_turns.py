"""``max_turns`` bounds one question, not a whole conversation.

The failure being pinned down: a `/match` chat answered five questions using 12
assistant turns between them, hit ``MatchAgent.max_turns`` mid-answer, and from
then on every further question ended in ~40 ms without a single LLM call —
``agent_max_turns_reached`` immediately, no answer, ``status='completed'``. The
conversation was permanently unusable.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.core.langgraph.base import BaseAgent


class _Agent(BaseAgent):
    """Minimal concrete agent — only ``_current_turn`` is under test."""

    name = "test"
    tools = []
    max_turns = 3

    def build_system_prompt(self, **kwargs):
        return "system"


agent = _Agent()


def _tool_round(text: str) -> list:
    """One assistant turn that called a tool, plus the tool's reply."""
    return [
        AIMessage(content="", tool_calls=[{"name": "search", "args": {}, "id": text}]),
        ToolMessage(content="{}", tool_call_id=text),
    ]


def test_first_call_of_a_question_is_turn_one():
    assert agent._current_turn([HumanMessage(content="第一问")]) == 1


def test_turns_accumulate_within_one_question():
    messages = [HumanMessage(content="第一问"), *_tool_round("a"), *_tool_round("b")]
    assert agent._current_turn(messages) == 3


def test_budget_resets_on_the_next_question():
    """The heart of the bug: a new question starts from turn 1 again."""
    messages = [
        HumanMessage(content="第一问"),
        *_tool_round("a"),
        *_tool_round("b"),
        AIMessage(content="答案一"),
        HumanMessage(content="第二问"),
    ]
    assert agent._current_turn(messages) == 1


def test_a_long_conversation_never_starves_a_new_question():
    """Six questions, 12 assistant messages — the shape that bricked the session."""
    messages = []
    for i in range(6):
        messages.append(HumanMessage(content=f"问题 {i}"))
        messages.extend(_tool_round(f"t{i}"))
        messages.append(AIMessage(content=f"答案 {i}"))
    messages.append(HumanMessage(content="第七问"))

    assert len([m for m in messages if isinstance(m, AIMessage)]) == 12
    # Counting the whole thread gave 13 > max_turns and killed the turn outright.
    assert agent._current_turn(messages) == 1


def test_limit_still_stops_a_runaway_question():
    """The guard must keep working — a single question cannot loop forever."""
    messages = [HumanMessage(content="问")]
    for i in range(5):
        messages.extend(_tool_round(f"loop{i}"))

    turn = agent._current_turn(messages)
    assert turn == 6
    assert turn > agent.max_turns
