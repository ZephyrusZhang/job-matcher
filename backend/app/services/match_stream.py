"""Streaming plumbing for the match agent.

Two pieces:

``FinalAnswerExtractor``
    The deliverable is the ``answer`` argument of the ``final_answer`` tool
    call, which arrives as a *partial JSON string* (``{"answer":"根``…). To
    stream it as text we decode that value incrementally, handling escapes and
    ``\\uXXXX`` sequences that straddle chunk boundaries.

``MatchStreamBridge``
    A LangChain callback handler that translates model/tool callbacks into the
    turn's semantic events, the same pattern ``app/crawl/callbacks.py`` uses.
    ``BaseAgent.get_stream_response`` only yields assistant text, which cannot
    express the tool timeline this page shows.

The bridge holds no aggregate state of its own: it hands each event to
``Run.emit``, which folds, persists and publishes it under one lock. Keeping the
fold there is what lets a reconnecting client be handed a snapshot whose ``seq``
cannot disagree with the frames that follow it.
"""

import time
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from app.agents.match_tools import FINAL_ANSWER_TOOL
from app.core.logging import logger
from app.services.match_runs import Run

_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    '"': '"',
    "\\": "\\",
    "/": "/",
}

# Tool name → what the user sees while it runs.
TOOL_LABELS = {
    "search_jobs": "检索岗位",
    "count_jobs": "统计岗位数量",
    "get_job_detail": "读取岗位详情",
    "get_resume_profile": "读取简历",
    "list_favorites": "读取收藏岗位",
}


class FinalAnswerExtractor:
    """Incrementally decode one string field out of a partial JSON object."""

    def __init__(self, key: str = "answer"):
        """Start an extractor for ``key``."""
        self._needle = f'"{key}"'
        self._buf = ""
        self._pos = 0
        self._state = "seek_key"
        self._escape = False
        self._unicode: Optional[str] = None
        self._pending_high: Optional[int] = None
        self.done = False

    def feed(self, delta: str) -> str:
        """Consume the next raw argument fragment.

        Args:
            delta: Newly arrived characters of the JSON arguments string.

        Returns:
            Newly decoded text of the target field, possibly empty.
        """
        if self.done or not delta:
            return ""

        self._buf += delta
        out: list[str] = []

        while self._pos < len(self._buf):
            if self._state == "seek_key":
                idx = self._buf.find(self._needle, self._pos)
                if idx < 0:
                    # Retain a tail long enough to hold a key split across chunks.
                    self._pos = max(self._pos, len(self._buf) - len(self._needle))
                    break
                self._pos = idx + len(self._needle)
                self._state = "seek_colon"
                continue

            char = self._buf[self._pos]

            if self._state == "seek_colon":
                self._pos += 1
                if char == ":":
                    self._state = "seek_quote"
                continue

            if self._state == "seek_quote":
                self._pos += 1
                if char == '"':
                    self._state = "in_value"
                continue

            # in_value
            if self._unicode is not None:
                needed = 4 - len(self._unicode)
                chunk = self._buf[self._pos : self._pos + needed]
                self._unicode += chunk
                self._pos += len(chunk)
                if len(self._unicode) < 4:
                    break  # wait for the rest of the escape
                out.append(self._decode_unicode(self._unicode))
                self._unicode = None
                continue

            if self._escape:
                self._escape = False
                self._pos += 1
                if char == "u":
                    self._unicode = ""
                else:
                    out.append(_ESCAPES.get(char, char))
                continue

            if char == "\\":
                self._escape = True
                self._pos += 1
                continue

            if char == '"':
                self._pos += 1
                self._state = "done"
                self.done = True
                break

            out.append(char)
            self._pos += 1

        return "".join(out)

    def _decode_unicode(self, hex4: str) -> str:
        """Decode one ``\\uXXXX`` escape, pairing surrogates."""
        try:
            code = int(hex4, 16)
        except ValueError:
            return ""

        if 0xD800 <= code <= 0xDBFF:
            self._pending_high = code
            return ""

        if 0xDC00 <= code <= 0xDFFF and self._pending_high is not None:
            combined = 0x10000 + ((self._pending_high - 0xD800) << 10) + (code - 0xDC00)
            self._pending_high = None
            return chr(combined)

        self._pending_high = None
        return chr(code)


class MatchStreamBridge(AsyncCallbackHandler):
    """Translate agent callbacks into the run's event stream."""

    def __init__(self, run: Run):
        """Bridge into ``run``."""
        self.run = run
        self._extractor = FinalAnswerExtractor()
        self._started: dict[UUID, float] = {}
        self._call_ids: dict[UUID, str] = {}
        # Tool-call arguments arrive as deltas keyed by index within one
        # assistant message, not by call id.
        self._arg_index_names: dict[int, str] = {}

    async def on_chat_model_start(
        self, serialized: dict[str, Any], messages: list[list[BaseMessage]], **kwargs: Any
    ) -> None:
        """Reset per-call argument tracking."""
        self._arg_index_names.clear()

    async def on_llm_new_token(self, token: str, *, chunk: Any = None, **kwargs: Any) -> None:
        """Stream narration text and tool-call argument deltas."""
        # The callback delivers a ChatGenerationChunk, which wraps the
        # AIMessageChunk that actually carries tool_call_chunks.
        message = getattr(chunk, "message", chunk) if chunk is not None else None
        tool_chunks = getattr(message, "tool_call_chunks", None) if message is not None else None

        if tool_chunks:
            for tc in tool_chunks:
                index = tc.get("index") or 0
                name = tc.get("name")
                if name:
                    self._arg_index_names[index] = name

                resolved = self._arg_index_names.get(index, name)
                args_delta = tc.get("args") or ""
                if not args_delta:
                    continue

                if resolved == FINAL_ANSWER_TOOL:
                    text = self._extractor.feed(args_delta)
                    if text:
                        await self.run.emit("final_delta", {"content": text})
                elif resolved:
                    await self.run.emit("tool_args", {"name": resolved, "delta": args_delta})
            return

        if token:
            await self.run.emit("narration", {"content": token})

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Fall back to the whole argument blob when nothing streamed.

        Some providers deliver tool-call arguments in one piece at the end
        rather than as deltas; without this the final answer would never reach
        the client.
        """
        if self.run.final_answer or not response.generations:
            return

        message = getattr(response.generations[0][0], "message", None)
        for call in getattr(message, "tool_calls", None) or []:
            if call.get("name") != FINAL_ANSWER_TOOL:
                continue
            answer = (call.get("args") or {}).get("answer") or ""
            if answer:
                await self.run.emit("final_delta", {"content": answer})

    async def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        inputs: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        """Open a timeline entry, skipping the terminal tool."""
        name = (serialized or {}).get("name", "unknown")
        if name == FINAL_ANSWER_TOOL:
            return  # not a step the user needs to see

        call_id = str(run_id)
        self._call_ids[run_id] = call_id
        self._started[run_id] = time.time()
        await self.run.emit(
            "tool_start",
            {
                "call_id": call_id,
                "name": name,
                "label": TOOL_LABELS.get(name, name),
                "args": inputs if inputs is not None else input_str,
            },
        )

    async def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        """Close a timeline entry with a short result summary."""
        call_id = self._call_ids.pop(run_id, None)
        if call_id is None:
            return

        content = str(getattr(output, "content", output))
        count = _extract_count(content)
        await self.run.emit(
            "tool_end",
            {
                "call_id": call_id,
                "ok": True,
                "summary": f"{count} 条" if count is not None else "完成",
                # The raw observation is what the model actually read, so the
                # trace shows it verbatim (truncated) rather than a bare count.
                "observation": _truncate(content),
                "count": count,
                "duration_ms": self._elapsed(run_id),
            },
        )

    async def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        """Mark a timeline entry as failed."""
        call_id = self._call_ids.pop(run_id, None)
        if call_id is None:
            return

        logger.warning("match_tool_failed", call_id=call_id, error=str(error))
        await self.run.emit(
            "tool_end",
            {
                "call_id": call_id,
                "ok": False,
                "summary": str(error)[:200],
                "observation": str(error)[:2000],
                "count": None,
                "duration_ms": self._elapsed(run_id),
            },
        )

    def _elapsed(self, run_id: UUID) -> float:
        """Milliseconds since the tool started."""
        return (time.time() - self._started.pop(run_id, time.time())) * 1000


# Observations can be large (a search returns dozens of jobs); keep enough to
# be useful in the trace without bloating stored messages.
MAX_OBSERVATION_CHARS = 4000


def _truncate(text: str, limit: int = MAX_OBSERVATION_CHARS) -> str:
    """Shorten an observation for display and storage."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n… 已截断，共 {len(text)} 字符"


def _extract_count(payload: str) -> Optional[int]:
    """Pull a result count out of a tool's JSON payload, if present."""
    import json

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    for key in ("returned", "count", "total_matched"):
        value = data.get(key)
        if isinstance(value, int):
            return value
    return None
