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
import threading
from typing import (
    Any,
    Optional,
)

from app.core.langgraph import (
    AgentCancelled,
    BaseAgent,
)
from app.core.logging import logger
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

# Matches MAX_TURNS from the original loop.
MAX_TURNS = 64

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

    def read_output(self) -> list[dict]:
        """Read ``/home/user/output.json`` from the sandbox.

        Returns:
            The crawled job dicts, or an empty list when the file is missing or
            malformed — matching the original ``_read_output`` behaviour.
        """
        try:
            data = json.loads(sandbox_mgr.read_file("/home/user/output.json"))
            if isinstance(data, dict) and "jobs" in data:
                return data["jobs"]
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []

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
        verbose: bool = True,
        log_dir: str = "logs",
    ) -> tuple[list[dict], Optional[str]]:
        """Run one crawl and return the jobs plus the generated crawler code.

        This is the drop-in replacement for ``app/crawl/pipeline.py::run_crawler``.

        Args:
            career_url: The careers page to crawl.
            session_id: LangGraph thread ID; reuse it to resume a crawl.
            company_id: Names/labels the sandbox container, e.g.
                ``jm-crawl-bytedance-0faec70f``.
            cancel_event: Checked between graph nodes for cooperative cancellation.
            verbose: Whether the console handler prints message previews.
            log_dir: Directory for the JSONL event log.

        Returns:
            A ``(jobs, crawler_code)`` tuple. ``crawler_code`` is ``None`` when
            the agent never produced a script.
        """
        bridge = CrawlEventBridge(handlers=[ConsoleHandler(verbose=verbose), FileHandler(log_dir=log_dir)])
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

        try:
            await self.run(
                [Message(role="user", content=f"爬取该招聘网站的所有岗位信息：{career_url}")],
                session_id,
                callbacks=[bridge],
                cancel_check=(cancel_event.is_set if cancel_event else None),
            )
        except AgentCancelled:
            cancelled = True
            logger.info("crawl_agent_cancelled", session_id=session_id, url=career_url)
        except Exception as e:
            # A failed run can still have produced a usable output.json, so fall
            # through to the extraction below rather than losing the work.
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
            return [], None

        jobs = self.read_output()
        code = self.read_crawler_code()

        # No jobs means the crawl failed; cleanup() then keeps the container so
        # the generated script and partial output stay inspectable.
        sandbox_mgr.cleanup(success=bool(jobs))
        logger.info("crawl_sandbox_released", session_id=session_id, jobs=len(jobs), kept=not bool(jobs))

        return jobs, code


crawler_agent = CrawlerAgent()
