import json
from datetime import datetime
from pathlib import Path

from .events import AgentEvent


class ConsoleHandler:
    """终端输出，开发调试用"""

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def handle(self, event: AgentEvent):
        t = event.turn
        match event.event_type:
            case "llm_start":
                msg_count = event.data.get("message_count", 0)
                total_chars = event.data.get("total_chars", 0)
                print(f"\n{'='*60}")
                print(f"\U0001f504 Turn {t} | 发送 {msg_count} 条消息 (~{total_chars} 字符)")
                if self.verbose:
                    last = event.data.get("last_message", {})
                    role = last.get("role", "")
                    content = str(last.get("content", ""))[:200]
                    print(f"   最新消息 [{role}]: {content}")

            case "llm_end":
                content = event.data.get("content", "")
                tool_calls = event.data.get("tool_calls", [])
                duration = event.duration_ms or 0
                tokens = event.data.get("usage", {})

                if tool_calls:
                    print(f"\U0001f916 LLM 响应 ({duration:.0f}ms, {tokens}):")
                    if content:
                        print(f"   \U0001f4ac {content[:150]}")
                    for tc in tool_calls:
                        args_str = tc["arguments"][:100]
                        print(f"   \U0001f527 调用 {tc['name']}({args_str}...)")
                else:
                    print(f"\U0001f916 LLM 最终回复 ({duration:.0f}ms):")
                    print(f"   {content[:300]}")

            case "tool_start":
                name = event.data["name"]
                args = json.dumps(event.data["args"], ensure_ascii=False)
                if len(args) > 150:
                    args = args[:150] + "..."
                print(f"   \u26a1 执行 {name}: {args}")

            case "tool_end":
                name = event.data["name"]
                result = str(event.data.get("result", ""))
                duration = event.duration_ms or 0
                icon = "\u2705" if event.data.get("success", True) else "\u274c"
                print(f"   {icon} {name} 完成 ({duration:.0f}ms) \u2192 {result[:150]}")

            case "error":
                print(f"   \u2757 错误: {event.data.get('error', '')}")

            case "agent_end":
                total = event.data.get("total_turns", 0)
                total_time = event.data.get("total_time_ms", 0)
                print(f"\n{'='*60}")
                print(f"\U0001f3c1 Agent 结束 | {total} 轮 | {total_time/1000:.1f}s")


class FileHandler:
    """JSONL 文件记录，每行一个事件"""

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = self.log_dir / f"agent_{ts}.jsonl"
        self.f = open(self.filepath, "a", encoding="utf-8")

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
