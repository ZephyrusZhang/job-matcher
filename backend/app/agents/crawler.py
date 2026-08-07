"""Crawler agent, defined on the LangGraph framework.

Behaviourally this is the same agent as the previous hand-rolled ReAct loop in
``app/crawl/agent.py``: same system prompt, same eight tools with the same
names, descriptions and schemas, same 64-turn ceiling, same 12k-char tool-result
truncation, same history compaction, same ``output.json`` extraction, and the
same console + JSONL event stream.

What the framework adds: Postgres checkpointing (a crawl can be inspected or
resumed by session), Langfuse tracing, Prometheus metrics, model fallback with
retries, and cooperative cancellation.
"""

import json
import logging
import threading
from dataclasses import dataclass
from typing import (
    Any,
    Optional,
)

from langchain_core.messages import AIMessage

from app.core.langgraph import (
    AgentCancelled,
    BaseAgent,
)
from app.core.logging import get_logger
from app.crawl.callbacks import CrawlEventBridge
from app.crawl.handlers import (
    ConsoleHandler,
    FileHandler,
)
from app.crawl.lc_tools import CRAWL_TOOLS
from app.crawl.prompts import build_system_prompt
from app.crawl.sandbox import (
    LABEL_COMPANY,
    LABEL_MODE,
    LABEL_TASK,
    build_sandbox_name,
)
from app.crawl.tools import (
    browser_mgr,
    sandbox_mgr,
)
from app.schemas.agent import Message

logger = get_logger(__name__)

# Matches MAX_TURNS from the original loop.
MAX_TURNS = 64


@dataclass
class CrawlOutcome:
    """What one crawl produced, and enough context to say why when it produced nothing.

    A crawl that returns no jobs used to be indistinguishable from a successful
    one at the service layer, so an agent that burned through every turn without
    writing a result was recorded as ``completed`` with 0 jobs — no error, no
    retry, and the company's listing silently emptied.
    """

    jobs: list[dict]
    code: Optional[str]
    turns: int = 0
    #: The agent wrote ``output.json`` at all. False means it never got there.
    wrote_output: bool = False
    max_turns: int = MAX_TURNS
    error: Optional[str] = None
    cancelled: bool = False

    @property
    def max_turns_reached(self) -> bool:
        """Derived rather than stored, so it cannot disagree with ``turns``."""
        return self.turns >= self.max_turns

    def failure_reason(self) -> Optional[str]:
        """Why this crawl is a failure, or ``None`` when it is not one.

        An empty ``output.json`` is left as a success: a careers page with no
        current openings is a real, if rare, answer.
        """
        if self.cancelled or self.wrote_output:
            return None
        if self.max_turns_reached:
            return (
                f"Agent 用尽 {self.turns} 轮仍未产出 output.json，"
                "未能生成可用的爬虫脚本"
            )
        if self.error:
            return f"Agent 运行失败：{self.error}"
        return "Agent 结束时没有产出 output.json"

# The original compacted history once the serialized conversation passed 100k
# characters, keeping the most recent 16 messages intact.
MAX_HISTORY_CHARS = 100_000
KEEP_RECENT_MESSAGES = 16


class CrawlerAgent(BaseAgent):
    """Agent that reverse-engineers a careers site and writes a crawler for it.

    The agent drives a real browser to capture API traffic, then writes and runs
    a crawler script inside a Docker sandbox until it produces structured job
    data.
    """

    name = "crawler"
    tools = CRAWL_TOOLS
    max_turns = MAX_TURNS
    # Crawling is a single-shot task against one careers site; there is no
    # cross-run user knowledge worth accumulating, and mem0 would add an LLM
    # call per turn.
    use_memory = False

    def build_system_prompt(self, **kwargs: Any) -> str:
        """Return the crawl system prompt, unchanged from the original agent."""
        return build_system_prompt()

    def compact_history(self, messages: list, system_prompt: str) -> list:
        """Compress old tool results instead of dropping messages.

        Reproduces ``app/crawl/agent.py::maybe_compress_history``. Token-based
        trimming is wrong here: dropping an assistant message would orphan its
        tool results and the provider would reject the request.

        Args:
            messages: The current conversation state.
            system_prompt: The system prompt to prepend.

        Returns:
            The messages to send, system prompt first.
        """
        system = [Message(role="system", content=system_prompt)]

        total = sum(len(str(getattr(m, "content", ""))) for m in messages)
        if total < MAX_HISTORY_CHARS:
            return system + messages

        compacted = []
        cutoff = len(messages) - KEEP_RECENT_MESSAGES
        for i, message in enumerate(messages):
            if i >= cutoff or message.__class__.__name__ != "ToolMessage":
                compacted.append(message)
                continue

            content = str(message.content or "")
            if len(content) > 300:
                message = message.model_copy(update={"content": f"[早期结果已压缩，原始 {len(content)} 字符]"})
            compacted.append(message)

        logger.info("crawl_history_compacted", original_chars=total, message_count=len(messages))
        return system + compacted

    def read_output(self) -> Optional[list[dict]]:
        """Read ``/home/user/output.json`` from the sandbox.

        Returns:
            The crawled job dicts, or ``None`` when the file is missing or
            malformed. That distinction matters: an empty list means the agent
            finished and reported no openings, while ``None`` means it never
            got as far as writing a result at all — the second is a failure,
            the first may simply be an empty careers page.
        """
        try:
            data = json.loads(sandbox_mgr.read_file("/home/user/output.json"))
            if isinstance(data, dict) and "jobs" in data:
                return data["jobs"]
            if isinstance(data, list):
                return data
            return None
        except Exception:
            return None

    def read_crawler_code(self) -> Optional[str]:
        """Read the generated crawler script so it can be cached for reuse."""
        try:
            return sandbox_mgr.read_file("/home/user/crawler.py")
        except Exception:
            return None

    async def crawl(
        self,
        career_url: str,
        session_id: str,
        *,
        company_id: Optional[str] = None,
        cancel_event: Optional[threading.Event] = None,
        verbose: Optional[bool] = None,
        log_dir: str = "logs",
    ) -> "CrawlOutcome":
        """Run one crawl and report what it produced.

        Args:
            career_url: The careers page to crawl.
            session_id: LangGraph thread ID; reuse it to resume a crawl.
            company_id: Names/labels the sandbox container, e.g.
                ``jm-crawl-bytedance-0faec70f``.
            cancel_event: Checked between graph nodes for cooperative cancellation.
            verbose: Log the model's narration and each tool result as well as
                the per-turn line. Defaults to following ``LOG_LEVEL`` — it used
                to be hardcoded on, which is how a crawl came to print ~580
                lines the structured log had no say over.
            log_dir: Directory for the JSONL event log.

        Returns:
            A ``CrawlOutcome``. Check ``failure_reason()`` rather than testing
            ``jobs`` for emptiness — the two are not the same question.
        """
        if verbose is None:
            verbose = logging.getLogger(__name__).isEnabledFor(logging.DEBUG)

        bridge = CrawlEventBridge(
            handlers=[
                ConsoleHandler(verbose=verbose, task_id=session_id, company=company_id),
                FileHandler(log_dir=log_dir),
            ]
        )
        cancelled = False

        # Stamp identity before the first tool call — the shared sandbox
        # manager creates its container lazily, so this is what names it.
        sandbox_mgr.configure(
            name=build_sandbox_name("crawl", company_id, session_id),
            labels={
                LABEL_MODE: "crawl",
                LABEL_COMPANY: company_id or "",
                LABEL_TASK: session_id,
            },
        )

        turns = 0
        agent_error: Optional[str] = None

        try:
            state = await self.run(
                [Message(role="user", content=f"爬取该招聘网站的所有岗位信息：{career_url}")],
                session_id,
                callbacks=[bridge],
                cancel_check=(cancel_event.is_set if cancel_event else None),
            )
            turns = len([m for m in (state or {}).get("messages", []) if isinstance(m, AIMessage)])
        except AgentCancelled:
            cancelled = True
            logger.info("crawl_agent_cancelled", session_id=session_id, url=career_url)
        except Exception as e:
            # A failed run can still have produced a usable output.json, so fall
            # through to the extraction below rather than losing the work.
            agent_error = str(e)
            logger.exception("crawl_agent_failed", session_id=session_id, url=career_url, error=str(e))
        finally:
            bridge.finish(cancelled=cancelled)
            try:
                browser_mgr.close()
            except Exception:
                logger.warning("browser_close_failed", session_id=session_id)

        # The sandbox must outlive the agent loop long enough to read its
        # output, so it is cleaned up here rather than in the finally above.
        if cancelled:
            sandbox_mgr.cleanup(success=True)
            return CrawlOutcome(jobs=[], code=None, turns=turns, cancelled=True)

        jobs = self.read_output()
        code = self.read_crawler_code()

        # No jobs means the crawl failed; cleanup() then keeps the container so
        # the generated script and partial output stay inspectable.
        produced = bool(jobs)
        sandbox_mgr.cleanup(success=produced)
        logger.info(
            "crawl_sandbox_released",
            session_id=session_id,
            jobs=len(jobs) if jobs is not None else None,
            turns=turns,
            kept=not produced,
        )

        return CrawlOutcome(
            jobs=jobs if jobs is not None else [],
            code=code,
            turns=turns,
            wrote_output=jobs is not None,
            # `_chat` stops the graph once the turn count passes max_turns, so
            # reaching it means the agent was cut off rather than finishing.
            max_turns=self.max_turns,
            error=agent_error,
        )


crawler_agent = CrawlerAgent()
