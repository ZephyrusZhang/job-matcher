"""LangChain tools for the match agent.

Thin wrappers over ``app/services/job_search.py``, following the same shape as
``app/crawl/lc_tools.py``.

Scope is **not** a tool argument. It is pinned per turn in a context variable by
the service layer, so the agent physically cannot search outside the companies
or favourites the user picked — a hallucinated ``company_id`` has nowhere to go.
"""

import contextvars
import json
from dataclasses import dataclass, field
from typing import Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.database import get_db
from app.schemas.match import MatchScope
from app.services import job_search

MAX_TOP_K = 40


@dataclass
class TurnContext:
    """Per-turn state the tools read instead of trusting model arguments."""

    scope: MatchScope
    resume_id: Optional[str] = None
    resume_label: Optional[str] = None
    db_path: str = ""
    cited_job_ids: list[str] = field(default_factory=list)


_turn: contextvars.ContextVar[Optional[TurnContext]] = contextvars.ContextVar(
    "match_turn_context", default=None
)


def set_turn_context(ctx: TurnContext) -> contextvars.Token:
    """Pin the turn context for the tools. Returns a reset token."""
    return _turn.set(ctx)


def reset_turn_context(token: contextvars.Token) -> None:
    """Restore the previous turn context."""
    _turn.reset(token)


def current_turn() -> TurnContext:
    """Return the active turn context.

    Raises:
        RuntimeError: When a tool is invoked outside a turn.
    """
    ctx = _turn.get()
    if ctx is None:
        raise RuntimeError("match tools used outside of a turn context")
    return ctx


def _dumps(payload) -> str:
    """Serialize a tool result."""
    return json.dumps(payload, ensure_ascii=False)


# ── search_jobs ───────────────────────────────────────────────────────────


class SearchJobsArgs(BaseModel):
    """Arguments for ``search_jobs``."""

    query: str = Field(default="", description="检索关键词，如 '后端 Go 微服务'。可留空只用筛选条件")
    categories: list[str] = Field(
        default_factory=list,
        description="岗位方向，中文，如 ['后端','算法']。取值须来自系统提示中列出的方向",
    )
    locations: list[str] = Field(default_factory=list, description="城市，中文，如 ['上海','北京']")
    job_types: list[str] = Field(default_factory=list, description="类型，只能是 '实习' 或 '全职'")
    top_k: int = Field(default=20, description="返回条数，最多 40")


async def _search_jobs(
    query: str = "",
    categories: list[str] | None = None,
    locations: list[str] | None = None,
    job_types: list[str] | None = None,
    top_k: int = 20,
) -> str:
    ctx = current_turn()
    db = await get_db(ctx.db_path)
    try:
        jobs, total = await job_search.search_jobs(
            db,
            ctx.scope,
            query=query,
            categories=categories or None,
            locations=locations or None,
            job_types=job_types or None,
            top_k=min(max(top_k, 1), MAX_TOP_K),
        )
    finally:
        await db.close()

    for job in jobs:
        if job["id"] not in ctx.cited_job_ids:
            ctx.cited_job_ids.append(job["id"])

    return _dumps({"total_matched": total, "returned": len(jobs), "jobs": jobs})


search_jobs = StructuredTool.from_function(
    coroutine=_search_jobs,
    name="search_jobs",
    description=(
        "在用户选定的范围内检索岗位，返回精简信息（标题、公司、城市、方向、一句话摘要）。"
        "范围由用户在界面上选定，无需也无法在此指定公司。"
        "需要完整岗位描述时再对具体岗位调用 get_job_detail。"
    ),
    args_schema=SearchJobsArgs,
)


# ── count_jobs ────────────────────────────────────────────────────────────


class CountJobsArgs(BaseModel):
    """Arguments for ``count_jobs``."""

    categories: list[str] = Field(default_factory=list, description="岗位方向")
    locations: list[str] = Field(default_factory=list, description="城市")
    job_types: list[str] = Field(default_factory=list, description="'实习' 或 '全职'")


async def _count_jobs(
    categories: list[str] | None = None,
    locations: list[str] | None = None,
    job_types: list[str] | None = None,
) -> str:
    ctx = current_turn()
    db = await get_db(ctx.db_path)
    try:
        total = await job_search.count_jobs(
            db,
            ctx.scope,
            categories=categories or None,
            locations=locations or None,
            job_types=job_types or None,
        )
    finally:
        await db.close()
    return _dumps({"count": total})


count_jobs = StructuredTool.from_function(
    coroutine=_count_jobs,
    name="count_jobs",
    description=(
        "统计当前范围内满足筛选条件的岗位数量，不返回岗位内容。"
        "用于在检索前判断条件是否过窄（返回 0）或过宽。"
    ),
    args_schema=CountJobsArgs,
)


# ── get_job_detail ────────────────────────────────────────────────────────


class JobDetailArgs(BaseModel):
    """Arguments for ``get_job_detail``."""

    job_id: str = Field(description="岗位 id，来自 search_jobs 的返回")


async def _get_job_detail(job_id: str) -> str:
    ctx = current_turn()
    db = await get_db(ctx.db_path)
    try:
        job = await job_search.get_job_detail(db, job_id)
    finally:
        await db.close()

    if job is None:
        return _dumps({"error": f"岗位不存在: {job_id}"})

    if job_id not in ctx.cited_job_ids:
        ctx.cited_job_ids.append(job_id)
    return _dumps(job)


get_job_detail = StructuredTool.from_function(
    coroutine=_get_job_detail,
    name="get_job_detail",
    description="获取单个岗位的完整信息：职位描述、职位要求原文，以及城市、类型、发布日期、原始链接。",
    args_schema=JobDetailArgs,
)


# ── get_resume_profile ────────────────────────────────────────────────────


class ResumeProfileArgs(BaseModel):
    """``get_resume_profile`` takes no arguments."""


async def _get_resume_profile() -> str:
    from app.models import resume as resume_model

    ctx = current_turn()
    db = await get_db(ctx.db_path)
    try:
        data = await resume_model.get_resume(db, ctx.resume_id)
    finally:
        await db.close()

    if not data:
        return _dumps({"error": "用户尚未上传简历"})

    parsed = data["parsed_data"]
    return _dumps(
        {
            "label": data["label"],
            "skills": parsed.get("skills", []),
            "experience_years": parsed.get("experience_years"),
            "education": parsed.get("education"),
            "raw_text": (parsed.get("raw_text") or "")[:4000],
        }
    )


get_resume_profile = StructuredTool.from_function(
    coroutine=_get_resume_profile,
    name="get_resume_profile",
    description="读取用户当前选定的简历：技能、经验年限、学历，以及简历原文（截断）。",
    args_schema=ResumeProfileArgs,
)


# ── list_favorites ────────────────────────────────────────────────────────


class ListFavoritesArgs(BaseModel):
    """Arguments for ``list_favorites``."""

    company_id: Optional[str] = Field(default=None, description="只看某家公司的收藏，可省略")


async def _list_favorites(company_id: Optional[str] = None) -> str:
    ctx = current_turn()
    db = await get_db(ctx.db_path)
    try:
        jobs = await job_search.list_favorites(db, company_id)
    finally:
        await db.close()

    for job in jobs:
        if job["id"] not in ctx.cited_job_ids:
            ctx.cited_job_ids.append(job["id"])
    return _dumps({"count": len(jobs), "jobs": jobs})


list_favorites = StructuredTool.from_function(
    coroutine=_list_favorites,
    name="list_favorites",
    description="列出用户收藏的岗位（精简信息）。",
    args_schema=ListFavoritesArgs,
)


# ── final_answer ──────────────────────────────────────────────────────────


class FinalAnswerArgs(BaseModel):
    """Arguments for ``final_answer``."""

    answer: str = Field(
        description=(
            "给用户的完整最终回复，Markdown 格式。"
            "提到具体岗位时用 :job[岗位id] 嵌入岗位卡片，id 从检索工具返回中原样复制。"
        )
    )


async def _final_answer(answer: str) -> str:
    # The value is streamed to the client straight off the argument deltas; the
    # graph only needs this call to exist so the turn can terminate.
    return _dumps({"delivered": True, "chars": len(answer)})


final_answer = StructuredTool.from_function(
    coroutine=_final_answer,
    name="final_answer",
    description=(
        "每一轮对话的【唯一正式出口】，必须调用它来结束本轮。"
        "answer 写给用户看的完整最终回复，使用 Markdown。"
        "提到具体岗位时用 :job[岗位id] 嵌入岗位卡片，id 从检索工具返回中原样复制；"
        "推荐岗位时让标记独占一行（渲染成完整卡片），顺带提及时写在句中（渲染成芯片）。"
        "必须单独调用，不要和其他工具在同一轮里一起调用。"
    ),
    args_schema=FinalAnswerArgs,
)


FINAL_ANSWER_TOOL = "final_answer"

MATCH_TOOLS = [
    search_jobs,
    count_jobs,
    get_job_detail,
    get_resume_profile,
    list_favorites,
    final_answer,
]
