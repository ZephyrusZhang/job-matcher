"""Sinks for the crawl agent's event stream.

Two of them, with deliberately different jobs — the third consumer of the same
stream is Langfuse, which ``BaseAgent._build_config`` attaches to every run.

``ConsoleHandler`` answers one question: *is this crawl still moving, and where
is it?* One line per turn, nothing else. It used to print the LLM preview, the
tool arguments and the tool result too — around 580 lines for a 64-turn crawl,
all of it truncated too hard to actually debug with, and all of it already in
the other two sinks.

``FileHandler`` is the forensic record: every event, untruncated, on local disk.
That is the one worth keeping, because it can be grepped and scripted over
offline — Langfuse needs a browser and a login, and ``LANGFUSE_TRACING_ENABLED``
is off by default, so on a fresh checkout this file is all there is.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from app.core.logging import get_logger

from .events import AgentEvent

logger = get_logger(__name__)

#: How many past crawl traces to keep. They are the only local record of a
#: crawl, but a 64-turn run writes ~320 KB and nothing pruned them before.
MAX_TRACE_FILES = 30

#: Console preview length for a tool's arguments — enough to tell `goto` from
#: `click` and see which URL, not enough to wrap the line.
_ARG_PREVIEW = 112

#: Above this, an individual argument is reported by size instead of by value.
#: Tuned so `sandbox_write_file`'s `content` (a whole crawler script, 800–5000
#: chars) collapses to a size while commands and URLs — the parts that say what
#: the turn was actually doing — still print in full.
_VALUE_MAX = 100


def _preview(args: dict) -> str:
    """Render tool arguments as a short single-line hint."""
    parts = []
    for key, value in args.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
        text = re.sub(r"\s+", " ", str(text)).strip()
        parts.append(f"{key}=<{len(text)} chars>" if len(text) > _VALUE_MAX else f"{key}={text}")
    joined = " ".join(parts)
    return joined[:_ARG_PREVIEW] + ("…" if len(joined) > _ARG_PREVIEW else "")


class ConsoleHandler:
    """One structured line per turn, so a running crawl is visible but not loud.

    Routed through the application logger rather than ``print`` so it carries a
    timestamp and module like every other line, lands in the structured log, and
    obeys ``LOG_LEVEL``.
    """

    def __init__(self, verbose: bool = False, task_id: str | None = None, company: str | None = None):
        """Args:
        verbose: Also log the LLM's narration and each tool's result.
        task_id: Crawl task, stamped onto every line so concurrent crawls
            (the semaphore allows two) stay tellable apart.
        company: Company being crawled.
        """
        self.verbose = verbose
        self._log = logger.bind(**{k: v for k, v in (("task", task_id), ("company", company)) if v})
        self._pending: dict[str, object] = {}

    def handle(self, event: AgentEvent):
        match event.event_type:
            case "llm_end":
                # Carried to the tool_end line rather than logged on its own.
                self._pending = {
                    "llm_ms": round(event.duration_ms or 0),
                    "tokens": (event.data.get("usage") or {}).get("prompt"),
                }
                if self.verbose and event.data.get("content"):
                    self._log.debug("crawl_narration", turn=event.turn, text=event.data["content"][:300])

            case "tool_start":
                self._pending["tool"] = event.data.get("name")
                self._pending["args"] = _preview(event.data.get("args") or {})

            case "tool_end":
                # The one line that matters: which turn, what it did, did it work.
                ok = bool(event.data.get("success", True))
                self._log.info(
                    "crawl_turn",
                    turn=event.turn,
                    tool=event.data.get("name") or self._pending.get("tool"),
                    args=self._pending.get("args", ""),
                    ok=ok,
                    tool_ms=round(event.duration_ms or 0),
                    llm_ms=self._pending.get("llm_ms"),
                    prompt_tokens=self._pending.get("tokens"),
                )
                if self.verbose:
                    self._log.debug(
                        "crawl_tool_result",
                        turn=event.turn,
                        result=str(event.data.get("result", ""))[:1000],
                    )
                self._pending = {}

            case "error":
                self._log.warning("crawl_turn_error", turn=event.turn, error=str(event.data.get("error", ""))[:300])

            case "agent_end":
                self._log.info(
                    "crawl_agent_finished",
                    turns=event.data.get("total_turns", 0),
                    duration_ms=round(event.data.get("total_time_ms", 0)),
                )


class FileHandler:
    """JSONL trace, one line per event — the untruncated local record."""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = self.log_dir / f"agent_{ts}.jsonl"
        self.f = open(self.filepath, "a", encoding="utf-8")
        self._prune()

    def _prune(self) -> None:
        """Keep the newest ``MAX_TRACE_FILES`` traces, drop the rest."""
        try:
            traces = sorted(
                self.log_dir.glob("agent_*.jsonl"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            for stale in traces[MAX_TRACE_FILES:]:
                stale.unlink(missing_ok=True)
        except OSError as e:
            # Never let housekeeping take a crawl down with it.
            logger.debug("crawl_trace_prune_failed", error=str(e))

    def handle(self, event: AgentEvent):
        line = json.dumps({
            "turn": event.turn,
            "type": event.event_type,
            "timestamp": event.timestamp,
            "duration_ms": event.duration_ms,
            "data": event.data,
        }, ensure_ascii=False, default=str)
        self.f.write(line + "\n")
        self.f.flush()

    def close(self):
        self.f.close()
