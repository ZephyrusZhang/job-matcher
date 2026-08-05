"""Conversational job-matching agent.

Drives the ``/match`` chat page. Unlike the crawler, this agent talks to a user
across many turns, so it leans on the framework's Postgres checkpointing: the
conversation id is the LangGraph thread id.

Every turn must end by calling ``final_answer``. That makes the deliverable
explicit and separable from the narration the model emits between tool calls —
the UI renders narration as muted progress text and the final answer as the body.
"""

from typing import Any

from app.agents.match_tools import FINAL_ANSWER_TOOL, MATCH_TOOLS, current_turn
from app.core.config import settings
from app.core.langgraph import BaseAgent
from app.core.logging import logger
from app.schemas.agent import Message
from app.schemas.match import MatchScope
from app.utils.graph import count_tokens

# The provider's context window, shared between the prompt and the reply.
CONTEXT_WINDOW_TOKENS = 1_000_000

# Slack for what the history count cannot see or size exactly: the tool schemas
# sent on every call, and the tokenizer gap — `utils/graph.py` falls back to
# cl100k_base because the provider's own tokenizer is not in tiktoken, and that
# estimate drifts on Chinese text.
CONTEXT_RESERVE_TOKENS = 100_000

# The most recent exchanges are what the model is actively reasoning over, so
# they are never touched.
KEEP_RECENT_MESSAGES = 12

# Older tool payloads keep a readable head rather than being replaced outright:
# a job's title and opening lines still carry most of what a later comparison
# needs, unlike the crawler's browser dumps which are worthless once past.
COMPACTED_HEAD_CHARS = 600

# The fixed taxonomies stored in the database, so the model filters with values
# that actually exist rather than inventing English equivalents.
CATEGORIES = [
    "前端", "后端", "算法", "客户端", "测试", "大数据", "安全", "硬件",
    "机器学习", "基础架构", "多媒体", "计算机视觉", "运维", "数据挖掘", "自然语言处理",
]
JOB_TYPES = ["实习", "全职"]

SYSTEM_PROMPT = """你是一位资深技术招聘顾问，通过对话帮助求职者从岗位库中找到合适的岗位。

# 当前会话上下文
- 检索范围：{scope}
- 简历：{resume_state}
- 当前日期：{today}

# 可用的固定取值
- 岗位方向（category）：{categories}
- 岗位类型（job_type）：{job_types}
筛选时必须使用上面列出的中文取值，不要自创或翻译成英文。

# 工作方式
1. 先用 get_resume_profile 了解用户背景（除非本轮明显不需要）
2. 条件不确定时先用 count_jobs 探数量，避免筛得过窄返回空结果
3. 用 search_jobs 检索，它只返回精简信息；对真正要推荐的岗位再用 get_job_detail 取全文
4. 信息足够后，调用 final_answer 输出最终回复

# 输出要求
- final_answer 的内容使用 Markdown，面向用户直接可读
- 推荐岗位时说明：为什么匹配（结合简历）、需要补足什么、岗位本身的亮点或风险
- 如果范围内确实没有合适岗位，如实说明并给出调整建议，不要编造岗位

# 岗位引用格式
在 final_answer 的正文中，用 :job[岗位id] 嵌入岗位卡片。

- id 必须从 search_jobs / get_job_detail / list_favorites 的返回中**原样复制**（36 位 UUID），
  一个字符都不能改，禁止编造
- 卡片会自动展示岗位名称、公司、城市、方向、类型，并可点击跳转原始链接；
  因此不要在标记旁边重复这些信息，也不要另外手写岗位链接
- 正式推荐某个岗位时：先写推荐理由，然后**另起一行、该行只放标记** → 渲染为完整卡片
- 行文中顺带提及某岗位时，把标记写在句子中间 → 渲染为紧凑芯片
- 同一岗位在一条回复中只引用一次（首次提及处）
- 不要把标记写进代码块或行内代码

示例：

## 最推荐

**后端开发工程师** 的分布式存储方向与你简历中的 etcd 经验高度吻合，
且只要求 1 年经验，你的 2 年经验有余量。

:job[3f2a9c10-7b4d-4e88-9a15-c0d3e5f61a27]

其次可以考虑 :job[8c1e04b2-33af-4d9e-b6c7-1e2f4a5b9d80]，方向接近但要求 3 年经验，
需要在项目深度上多准备。

# 硬性约束
- **必须调用 final_answer 结束本轮**，且单独调用，不要与其他工具同时调用
- 只能推荐检索结果中真实存在的岗位，禁止虚构岗位名称、公司或链接
- 检索范围由用户在界面上选定，你无法也不需要指定公司"""


class MatchAgent(BaseAgent):
    """Multi-turn agent that recommends jobs from a user-selected scope."""

    name = "matcher"
    tools = MATCH_TOOLS
    terminal_tools = frozenset({FINAL_ANSWER_TOOL})
    max_turns = 12
    # History budget only — *not* the reply length cap, which is
    # `settings.MAX_TOKENS` over in `services/llm/registry.py`.
    #
    # This is the ceiling at which `compact_history` starts shortening, so it
    # should sit as close to the window as is safe: anything lower discards
    # context the model could otherwise still see. Derived from the window
    # rather than picked, so it tracks a change to either term.
    max_history_tokens = CONTEXT_WINDOW_TOKENS - settings.MAX_TOKENS - CONTEXT_RESERVE_TOKENS
    # mem0 needs an embeddings endpoint the configured provider does not expose.
    use_memory = False
    # The UI renders tokens as they arrive, including the final_answer payload.
    streaming = True

    def build_system_prompt(self, **kwargs: Any) -> str:
        """Render the prompt with the turn's scope and resume state.

        Scope comes from the same context variable the tools read, not from
        ``kwargs``: the framework only passes generic conversation context, and
        keeping one source avoids the prompt and the tools disagreeing.
        """
        from datetime import date

        try:
            ctx = current_turn()
            scope: MatchScope | None = ctx.scope
            resume_label = ctx.resume_label
        except RuntimeError:
            scope, resume_label = None, None

        return SYSTEM_PROMPT.format(
            scope=scope.describe() if scope else "未指定范围",
            resume_state=f"已选择《{resume_label}》" if resume_label else "用户未选择简历",
            today=date.today().isoformat(),
            categories="、".join(CATEGORIES),
            job_types="、".join(JOB_TYPES),
        )

    def compact_history(self, messages: list, system_prompt: str) -> list:
        """Shorten old tool results instead of dropping messages.

        The framework default trims with ``strategy="last"`` and
        ``start_on="human"``. A turn has exactly one human message — the
        question — at the very front, so once the accumulated tool results
        alone exceed the budget there is no human message left for the window
        to start on and the trimmer returns *nothing*. The model then sees only
        the system prompt, greets the user as if the conversation were new, and
        re-runs the tools it already ran, until ``max_turns`` cuts it off with
        no answer.

        Dropping messages is not an option either: an assistant message carries
        the ``tool_calls`` its ``ToolMessage`` replies answer, and separating
        them makes the provider reject the request. So every message is kept
        and only the payload of older tool results is shortened.

        Args:
            messages: The current conversation state.
            system_prompt: The system prompt to prepend.

        Returns:
            The messages to send, system prompt first.
        """
        system = [Message(role="system", content=system_prompt)]

        total = count_tokens(messages)
        if total <= self.max_history_tokens:
            return system + messages

        compacted = []
        cutoff = len(messages) - KEEP_RECENT_MESSAGES
        shortened = 0

        for index, message in enumerate(messages):
            if index >= cutoff or message.__class__.__name__ != "ToolMessage":
                compacted.append(message)
                continue

            content = str(message.content or "")
            if len(content) <= COMPACTED_HEAD_CHARS:
                compacted.append(message)
                continue

            head = content[:COMPACTED_HEAD_CHARS]
            compacted.append(
                message.model_copy(
                    update={"content": f"{head}\n\n[早期结果已截断，原始 {len(content)} 字符]"}
                )
            )
            shortened += 1

        logger.info(
            "match_history_compacted",
            original_tokens=total,
            compacted_tokens=count_tokens(compacted),
            budget=self.max_history_tokens,
            messages=len(messages),
            shortened=shortened,
        )
        return system + compacted


matcher_agent = MatchAgent()
