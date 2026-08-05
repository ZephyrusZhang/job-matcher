"""Guards on how the match agent shortens a long turn's history.

The failure these pin down: reading twenty full job descriptions in one turn
pushed the history past the budget, the framework trimmer returned an empty
list, and the model — seeing only the system prompt — greeted the user
mid-turn and started re-running tools it had already run.
"""

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.matcher import KEEP_RECENT_MESSAGES, matcher_agent
from app.utils.graph import count_tokens, prepare_messages

QUESTION = "请你根据我的简历找 TOP 10 最适合我的岗位"
SYSTEM = "你是一位资深技术招聘顾问"


def build_turn(job_details: int, jd_chars: int = 2000) -> list:
    """One question followed by N rounds of reading a full job description."""
    messages: list = [HumanMessage(content=QUESTION)]
    for i in range(job_details):
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "get_job_detail", "args": {"job_id": f"job-{i}"}, "id": f"c{i}"}
                ],
            )
        )
        messages.append(
            ToolMessage(content="岗" * jd_chars, name="get_job_detail", tool_call_id=f"c{i}")
        )
    return messages


def kept(result: list) -> list:
    """The history part of a compaction result, without the system prompt."""
    return [m for m in result if getattr(m, "role", None) != "system"]


def test_framework_trimmer_drops_everything_once_over_budget():
    """The behaviour being worked around, pinned so it cannot regress silently."""
    messages = build_turn(20)
    assert count_tokens(messages) > 32000

    trimmed = prepare_messages(messages, SYSTEM, 32000)
    assert kept(trimmed) == [], "framework trimming is expected to wipe history here"


def test_question_survives_a_long_turn():
    messages = build_turn(20)
    result = kept(matcher_agent.compact_history(messages, SYSTEM))

    assert any(
        isinstance(m, HumanMessage) and QUESTION in m.content for m in result
    ), "the user's question must never be dropped"


def test_no_message_is_dropped():
    """Removing an assistant message would orphan the tool replies to it."""
    messages = build_turn(20)
    result = kept(matcher_agent.compact_history(messages, SYSTEM))

    assert len(result) == len(messages)
    call_ids = {c["id"] for m in result if isinstance(m, AIMessage) for c in m.tool_calls}
    reply_ids = {m.tool_call_id for m in result if isinstance(m, ToolMessage)}
    assert call_ids == reply_ids


def test_short_turns_are_passed_through_untouched():
    messages = build_turn(3)
    assert count_tokens(messages) <= matcher_agent.max_history_tokens

    result = kept(matcher_agent.compact_history(messages, SYSTEM))
    assert result == messages


def test_recent_results_are_left_intact():
    """Only stale payloads are shortened; the model is still reasoning over the tail."""
    messages = build_turn(200)
    result = kept(matcher_agent.compact_history(messages, SYSTEM))

    assert count_tokens(result) < count_tokens(messages)
    for original, compacted in zip(
        messages[-KEEP_RECENT_MESSAGES:], result[-KEEP_RECENT_MESSAGES:]
    ):
        assert original.content == compacted.content


def test_compaction_keeps_a_readable_head_of_old_results():
    messages = build_turn(200)
    result = kept(matcher_agent.compact_history(messages, SYSTEM))

    first_tool = next(m for m in result if isinstance(m, ToolMessage))
    assert first_tool.content.startswith("岗" * 100)
    assert "已截断" in first_tool.content
