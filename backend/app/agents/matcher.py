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
from app.core.langgraph import BaseAgent
from app.schemas.match import MatchScope

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
- 引用岗位时写明岗位名称和公司，便于用户对照
- 如果范围内确实没有合适岗位，如实说明并给出调整建议，不要编造岗位

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
    # Tool payloads are compact but a long conversation still adds up; well
    # above the framework default of 8000.
    max_history_tokens = 32000
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


matcher_agent = MatchAgent()
