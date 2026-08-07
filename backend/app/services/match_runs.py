"""In-flight match turns: aggregate state, persistence, and fan-out.

A turn used to live and die with its HTTP response: the agent task was owned by
the streaming generator, so closing the tab discarded the whole turn and left
the task running with nobody to persist its result. A ``Run`` decouples the two
— the registry owns the task, the response only owns a subscription to it.

Three properties the rest of the design leans on:

**Fold, persist, then publish.** ``emit`` writes the row before handing the
frame to any subscriber, so the stored ``seq`` is never behind what a client has
seen. A client reconnecting can therefore trust the row without reconciling.

**Snapshot and subscription are taken together.** ``attach`` holds ``lock``
while it reads the aggregate and registers the queue, so the snapshot's ``seq``
and the queue's first frame are necessarily adjacent — there are not two values
that could be paired wrongly.

**Cancellation is cooperative.** ``cancel`` feeds ``BaseAgent.run``'s
``cancel_check``, which is polled at graph node boundaries, rather than killing
the task mid-node.
"""

import asyncio
import threading
from typing import Any, Optional

from app.core.logging import get_logger
from app.models import match_conversation as conv_model

logger = get_logger(__name__)

# Frames that can change the reasoning trace. Every other frame — most of them,
# since one answer streams hundreds of `final_delta` — skips the large payload.
_STEP_EVENTS = frozenset({"narration", "tool_start", "tool_end"})

# Sent as an SSE comment so a silently dead connection still surfaces: without
# traffic, a reader can block forever instead of raising.
HEARTBEAT_SECONDS = 15


class Run:
    """One in-flight assistant turn."""

    def __init__(self, session_id: str, message_id: str, db: Any):
        """Create a run that persists into ``db`` for its whole lifetime."""
        self.session_id = session_id
        self.message_id = message_id
        self.db = db

        self.lock = asyncio.Lock()
        self.cancel = threading.Event()
        self.task: Optional[asyncio.Task] = None
        self.finished = asyncio.Event()

        self.seq = 0
        self.status = "running"
        self.steps: list[dict] = []
        self.final_answer = ""
        self.job_ids: list[str] = []

        self.subscribers: set[asyncio.Queue] = set()
        self._tool_steps: dict[str, int] = {}

    # ── Aggregate state ───────────────────────────────────────────────────

    def _apply(self, event: str, data: dict) -> None:
        """Fold one frame into the aggregate, stamping it with its step index.

        ``index`` is the frame's position in ``steps`` — which segment it
        belongs to — and is assigned here rather than by the bridge so that it
        cannot drift from the list it indexes into. It is a different axis from
        ``seq``: hundreds of ``narration`` frames share one ``index`` while each
        gets its own ``seq``.
        """
        if event == "narration":
            text = data.get("content", "")
            if not self.steps or self.steps[-1]["type"] != "narration":
                self.steps.append(
                    {"type": "narration", "index": len(self.steps), "content": ""}
                )
            self.steps[-1]["content"] += text
            data["index"] = self.steps[-1]["index"]

        elif event == "tool_start":
            entry = {
                "type": "tool",
                "index": len(self.steps),
                "call_id": data["call_id"],
                "name": data["name"],
                "label": data["label"],
                "args": data.get("args"),
                "ok": True,
                "summary": "",
                "observation": "",
                "count": None,
                "duration_ms": None,
            }
            self._tool_steps[data["call_id"]] = entry["index"]
            self.steps.append(entry)
            data["index"] = entry["index"]

        elif event == "tool_end":
            index = self._tool_steps.pop(data["call_id"], None)
            if index is None:
                return
            entry = self.steps[index]
            entry.update(
                ok=data.get("ok", True),
                summary=data.get("summary", ""),
                observation=data.get("observation", ""),
                count=data.get("count"),
                duration_ms=data.get("duration_ms"),
            )
            data["index"] = index

        elif event == "final_delta":
            self.final_answer += data.get("content", "")

    def snapshot(self) -> dict:
        """The turn's full state as of the current ``seq``.

        This is what a reconnecting client replaces its accumulator with; it is
        a complete value, not a delta, so no frame replay is needed to close a
        gap of any size.
        """
        return {
            "message_id": self.message_id,
            "seq": self.seq,
            "status": self.status,
            "steps": [dict(s) for s in self.steps],
            "final_answer": self.final_answer,
            "job_ids": list(self.job_ids),
        }

    async def emit(self, event: str, data: dict) -> None:
        """Persist one frame, then publish it.

        The ordering is the point: a subscriber can never hold a frame that the
        row does not already account for.
        """
        async with self.lock:
            self.seq += 1
            self._apply(event, data)
            await conv_model.update_progress(
                self.db,
                self.message_id,
                seq=self.seq,
                final_answer=self.final_answer,
                steps=self.steps if event in _STEP_EVENTS else None,
            )
            frame = {"seq": self.seq, "event": event, "data": data}
            for queue in list(self.subscribers):
                queue.put_nowait(frame)

    async def finish(self, status: str, job_ids: list[str] | None = None) -> None:
        """Close the turn: write the terminal row and release subscribers."""
        async with self.lock:
            self.status = status
            if job_ids is not None:
                self.job_ids = job_ids
            self.seq += 1
            await conv_model.update_progress(
                self.db,
                self.message_id,
                seq=self.seq,
                final_answer=self.final_answer,
                steps=self.steps,
                job_ids=self.job_ids,
                status=status,
            )
            end = {
                "seq": self.seq,
                "event": "message_end",
                "data": {"message_id": self.message_id, "status": status},
            }
            for queue in list(self.subscribers):
                queue.put_nowait(end)
                queue.put_nowait(None)
        self.finished.set()

    # ── Subscription ──────────────────────────────────────────────────────

    async def attach(self) -> tuple[dict, asyncio.Queue]:
        """Register a subscriber and return the snapshot it starts from.

        Both happen under ``lock``, so the first frame the queue receives is
        exactly ``snapshot["seq"] + 1``.
        """
        queue: asyncio.Queue = asyncio.Queue()
        async with self.lock:
            snapshot = self.snapshot()
            self.subscribers.add(queue)
        return snapshot, queue

    def detach(self, queue: asyncio.Queue) -> None:
        """Drop one subscriber. The run itself is unaffected."""
        self.subscribers.discard(queue)


class RunRegistry:
    """Process-local index of in-flight turns, keyed by conversation."""

    def __init__(self):
        """Create an empty registry."""
        self._runs: dict[str, Run] = {}

    def get(self, session_id: str) -> Optional[Run]:
        """Return the live run for a conversation, if any."""
        return self._runs.get(session_id)

    def add(self, run: Run) -> None:
        """Register a run.

        Raises:
            KeyError: When the conversation already has one.
        """
        if run.session_id in self._runs:
            raise KeyError(run.session_id)
        self._runs[run.session_id] = run

    def discard(self, session_id: str) -> None:
        """Forget a run once it has finished."""
        self._runs.pop(session_id, None)

    async def shutdown(self) -> None:
        """Cancel every live run. Called from the FastAPI lifespan."""
        for run in list(self._runs.values()):
            run.cancel.set()
            if run.task and not run.task.done():
                try:
                    await asyncio.wait_for(run.task, timeout=5)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception) as e:
                    logger.warning(
                        "match_run_shutdown_unclean", session_id=run.session_id, error=str(e)
                    )
        self._runs.clear()


registry = RunRegistry()
