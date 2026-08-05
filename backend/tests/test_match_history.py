"""Guards on how the match agent shortens a long turn's history.

The failure these pin down: reading twenty full job descriptions in one turn
pushed the history past the budget, the framework trimmer returned an empty
list, and the model — seeing only the system prompt — greeted the user
mid-turn and started re-running tools it had already run.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agents.matcher import (
    CONTEXT_RESERVE_TOKENS,
    CONTEXT_WINDOW_TOKENS,
    KEEP_RECENT_MESSAGES,
    matcher_agent,
)
from app.core.config import settings
from app.utils.graph import count_tokens, prepare_messages

QUESTION = "请你根据我的简历找 TOP 10 最适合我的岗位"
SYSTEM = "你是一位资深技术招聘顾问"

# Compaction is exercised against a small budget so the fixtures stay cheap;
# the logic under test does not depend on the real ceiling, and
# `test_budget_uses_the_context_window` covers the ceiling itself.
TEST_BUDGET = 32_000


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


@pytest.fixture
def small_budget(monkeypatch):
    """Run compaction against a budget a test-sized history can exceed."""
    monkeypatch.setattr(type(matcher_agent), "max_history_tokens", TEST_BUDGET)
    return TEST_BUDGET


def test_budget_uses_the_context_window():
    """A budget well under the window would discard context for no reason."""
    budget = matcher_agent.max_history_tokens
    assert budget == CONTEXT_WINDOW_TOKENS - settings.MAX_TOKENS - CONTEXT_RESERVE_TOKENS
    # Room for the reply and the schemas, but not a token more than necessary.
    assert budget > CONTEXT_WINDOW_TOKENS * 0.85
    assert budget + settings.MAX_TOKENS < CONTEXT_WINDOW_TOKENS


def test_framework_trimmer_drops_everything_once_over_budget():
    """The behaviour being worked around, pinned so it cannot regress silently."""
    messages = build_turn(20)
    assert count_tokens(messages) > TEST_BUDGET

    trimmed = prepare_messages(messages, SYSTEM, TEST_BUDGET)
    assert kept(trimmed) == [], "framework trimming is expected to wipe history here"


def test_question_survives_a_long_turn(small_budget):
    messages = build_turn(20)
    assert count_tokens(messages) > small_budget

    result = kept(matcher_agent.compact_history(messages, SYSTEM))
    assert any(
        isinstance(m, HumanMessage) and QUESTION in m.content for m in result
    ), "the user's question must never be dropped"


def test_no_message_is_dropped(small_budget):
    """Removing an assistant message would orphan the tool replies to it."""
    messages = build_turn(20)
    result = kept(matcher_agent.compact_history(messages, SYSTEM))

    assert len(result) == len(messages)
    call_ids = {c["id"] for m in result if isinstance(m, AIMessage) for c in m.tool_calls}
    reply_ids = {m.tool_call_id for m in result if isinstance(m, ToolMessage)}
    assert call_ids == reply_ids


def test_a_realistic_turn_is_passed_through_untouched():
    """Twenty full job descriptions used to blow the old 32k budget outright."""
    messages = build_turn(20)
    assert count_tokens(messages) <= matcher_agent.max_history_tokens

    result = kept(matcher_agent.compact_history(messages, SYSTEM))
    assert result == messages


def test_recent_results_are_left_intact(small_budget):
    """Only stale payloads are shortened; the model still needs the tail."""
    messages = build_turn(40)
    result = kept(matcher_agent.compact_history(messages, SYSTEM))

    assert count_tokens(result) < count_tokens(messages)
    for original, compacted in zip(
        messages[-KEEP_RECENT_MESSAGES:], result[-KEEP_RECENT_MESSAGES:]
    ):
        assert original.content == compacted.content


def test_compaction_keeps_a_readable_head_of_old_results(small_budget):
    messages = build_turn(40)
    result = kept(matcher_agent.compact_history(messages, SYSTEM))

    first_tool = next(m for m in result if isinstance(m, ToolMessage))
    assert first_tool.content.startswith("岗" * 100)
    assert "已截断" in first_tool.content
