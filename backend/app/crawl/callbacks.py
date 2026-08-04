"""Bridge LangChain callbacks onto the existing crawl ``AgentEvent`` stream.

The crawl agent used to emit ``AgentEvent`` objects directly from its hand-rolled
ReAct loop, which ``ConsoleHandler`` renders to the terminal and ``FileHandler``
appends to ``logs/agent_<timestamp>.jsonl``. LangGraph drives the loop now, so
this handler translates LangChain's callback protocol back into the same events
— the console output and JSONL schema are unchanged.
"""

import json
import time
from typing import (
    Any,
    Optional,
)
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from app.crawl.events import (
    AgentEvent,
    EventHandler,
)


class CrawlEventBridge(AsyncCallbackHandler):
    """Emit legacy ``AgentEvent``s from LangChain callbacks.

    Attributes:
        turn: Incremented on every LLM start, matching the old loop's turn count.
    """

    def __init__(self, handlers: list[EventHandler]):
        """Wrap a list of legacy event handlers.

        Args:
            handlers: ``ConsoleHandler`` / ``FileHandler`` instances to feed.
        """
        self.handlers = handlers
        self.turn = 0
        self._agent_start = time.time()
        self._llm_start_time: float = 0.0
        self._tool_starts: dict[UUID, tuple[str, float]] = {}
        self._last_content = ""
        self._last_had_tool_calls = False

    def emit(self, event_type: str, data: Optional[dict] = None, duration_ms: Optional[float] = None) -> None:
        """Dispatch one event to every wrapped handler."""
        event = AgentEvent(turn=self.turn, event_type=event_type, data=data or {}, duration_ms=duration_ms)
        for handler in self.handlers:
            handler.handle(event)

    async def on_chat_model_start(
        self,
        serialized: dict[str, Any],
        messages: list[list[BaseMessage]],
        **kwargs: Any,
    ) -> None:
        """Emit ``llm_start`` before each model call."""
        self.turn += 1
        self._llm_start_time = time.time()

        flat = messages[0] if messages else []
        last = flat[-1] if flat else None
        last_message = {"role": getattr(last, "type", ""), "content": str(getattr(last, "content", ""))} if last else {}

        self.emit(
            "llm_start",
            {
                "message_count": len(flat),
                "total_chars": sum(len(str(getattr(m, "content", ""))) for m in flat),
                "last_message": last_message,
            },
        )

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Emit ``llm_end`` with content, tool calls and token usage."""
        duration_ms = (time.time() - self._llm_start_time) * 1000

        content = ""
        tool_calls = []
        generations = response.generations[0] if response.generations else []
        if generations:
            message = getattr(generations[0], "message", None)
            if message is not None:
                content = str(message.content or "")
                tool_calls = [
                    {"name": tc.get("name", ""), "arguments": json.dumps(tc.get("args", {}), ensure_ascii=False)}
                    for tc in (getattr(message, "tool_calls", None) or [])
                ]

        usage = {}
        raw_usage = (response.llm_output or {}).get("token_usage") if response.llm_output else None
        if raw_usage:
            usage = {
                "prompt": raw_usage.get("prompt_tokens"),
                "completion": raw_usage.get("completion_tokens"),
            }

        self._last_content = content
        self._last_had_tool_calls = bool(tool_calls)

        self.emit("llm_end", {"content": content, "tool_calls": tool_calls, "usage": usage}, duration_ms=duration_ms)

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Emit ``tool_start`` and remember the start time for this run."""
        name = (serialized or {}).get("name", "unknown")
        self._tool_starts[run_id] = (name, time.time())
        self.emit("tool_start", {"name": name, "args": inputs if inputs is not None else input_str})

    async def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """Emit ``tool_end`` with the truncated result."""
        name, started = self._tool_starts.pop(run_id, ("unknown", time.time()))
        content = getattr(output, "content", output)
        self.emit(
            "tool_end",
            {"name": name, "result": str(content)[:500], "success": True},
            duration_ms=(time.time() - started) * 1000,
        )

    async def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        """Emit ``error`` when a tool raises."""
        name, started = self._tool_starts.pop(run_id, ("unknown", time.time()))
        self.emit("error", {"error": str(error), "tool": name}, duration_ms=(time.time() - started) * 1000)

    def finish(self, cancelled: bool = False) -> None:
        """Emit ``agent_end`` and close any handlers that hold file descriptors.

        Args:
            cancelled: Whether the run stopped because of a cancellation request.
        """
        data = {
            "total_turns": self.turn,
            "total_time_ms": (time.time() - self._agent_start) * 1000,
            "final_message": "用户取消" if cancelled else self._last_content,
        }
        if cancelled:
            data["cancelled"] = True

        self.emit("agent_end", data)

        for handler in self.handlers:
            close = getattr(handler, "close", None)
            if callable(close):
                close()
