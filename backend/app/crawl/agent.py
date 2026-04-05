import json
import threading
import time

from .events import AgentEvent, EventHandler
from .handlers import ConsoleHandler, FileHandler
from .llm import MODEL, client
from .prompts import build_system_prompt
from .tools import TOOLS, browser_mgr, execute_tool, sandbox_mgr

MAX_TURNS = 64


class AgentRunner:
    def __init__(
        self,
        handlers: list[EventHandler] | None = None,
        cancel_event: threading.Event | None = None,
    ):
        self.handlers = handlers or [ConsoleHandler()]
        self.cancel_event = cancel_event
        self.turn = 0

    def emit(self, event_type: str, data: dict = None, duration_ms: float = None):
        event = AgentEvent(
            turn=self.turn,
            event_type=event_type,
            data=data or {},
            duration_ms=duration_ms,
        )
        for h in self.handlers:
            h.handle(event)

    def run(self, user_message: str) -> list[dict]:
        """运行 Agent，返回爬取到的岗位数据列表。"""
        system_prompt = build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        agent_start = time.time()

        for self.turn in range(1, MAX_TURNS + 1):

            # ── 检查取消信号 ──
            if self.cancel_event and self.cancel_event.is_set():
                self.emit("agent_end", {
                    "total_turns": self.turn - 1,
                    "total_time_ms": (time.time() - agent_start) * 1000,
                    "final_message": "用户取消",
                    "cancelled": True,
                })
                break

            # ── 事件：LLM 调用前 ──
            self.emit("llm_start", {
                "message_count": len(messages),
                "total_chars": sum(len(json.dumps(m, ensure_ascii=False, default=str)) for m in messages),
                "last_message": messages[-1],
            })

            # ── 调用 LLM ──
            t0 = time.time()
            response = client.chat.completions.create(
                model=MODEL, messages=messages, tools=TOOLS,
            )
            msg = response.choices[0].message
            llm_ms = (time.time() - t0) * 1000

            # ── 事件：LLM 返回后 ──
            usage = {}
            if response.usage:
                usage = {
                    "prompt": response.usage.prompt_tokens,
                    "completion": response.usage.completion_tokens,
                }
            self.emit("llm_end", {
                "content": msg.content or "",
                "tool_calls": [
                    {"name": tc.function.name, "arguments": tc.function.arguments}
                    for tc in (msg.tool_calls or [])
                ],
                "usage": usage,
            }, duration_ms=llm_ms)

            # 追加 assistant 消息到历史
            assistant_msg = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                assistant_msg["tool_calls"] = [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ]
            messages.append(assistant_msg)

            # 无工具调用 → 结束
            if not msg.tool_calls:
                self.emit("agent_end", {
                    "total_turns": self.turn,
                    "total_time_ms": (time.time() - agent_start) * 1000,
                    "final_message": msg.content or "",
                })
                break

            # ── 执行工具调用 ──
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments)

                # 事件：工具执行前
                self.emit("tool_start", {"name": name, "args": args})

                t1 = time.time()
                try:
                    raw_result = execute_tool(name, args)
                    tool_ms = (time.time() - t1) * 1000

                    # 事件：工具执行后
                    self.emit("tool_end", {
                        "name": name,
                        "result": raw_result[:500],
                        "success": True,
                    }, duration_ms=tool_ms)
                except Exception as e:
                    tool_ms = (time.time() - t1) * 1000
                    raw_result = json.dumps({"error": str(e)})
                    # 事件：工具执行出错
                    self.emit("error", {
                        "error": str(e),
                        "tool": name,
                    }, duration_ms=tool_ms)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": truncate_tool_result(raw_result),
                })

            # 上下文压缩
            messages = maybe_compress_history(messages)

        # 从沙箱读取爬取结果
        jobs = self._read_output()

        # 清理资源（保留沙箱容器便于 debug）
        browser_mgr.close()
        for h in self.handlers:
            if hasattr(h, "close"):
                h.close()

        return jobs

    def _read_output(self) -> list[dict]:
        """从沙箱读取 /home/user/output.json。"""
        try:
            content = sandbox_mgr.read_file("/home/user/output.json")
            data = json.loads(content)
            if isinstance(data, dict) and "jobs" in data:
                return data["jobs"]
            if isinstance(data, list):
                return data
            return []
        except Exception:
            return []


def truncate_tool_result(result: str, max_chars: int = 12000) -> str:
    if len(result) <= max_chars:
        return result
    head = max_chars * 2 // 3
    tail = max_chars // 3
    return (
        result[:head]
        + f"\n\n[...已截断，原始 {len(result)} 字符...]\n\n"
        + result[-tail:]
    )


def maybe_compress_history(messages: list, max_total_chars: int = 100000) -> list:
    """压缩早期工具结果，保留最近 16 条完整。"""
    total = sum(len(json.dumps(m, ensure_ascii=False, default=str)) for m in messages)
    if total < max_total_chars:
        return messages

    keep_recent = 16
    compressed = []
    for i, msg in enumerate(messages):
        if i >= len(messages) - keep_recent:
            compressed.append(msg)
            continue
        if msg.get("role") == "tool":
            content = msg.get("content", "")
            if len(content) > 300:
                msg = {**msg, "content": f"[早期结果已压缩，原始 {len(content)} 字符]"}
        compressed.append(msg)
    return compressed
