from dataclasses import dataclass, field
from typing import Protocol
import time


@dataclass
class AgentEvent:
    """单个事件记录"""
    turn: int
    event_type: str  # llm_start / llm_end / tool_start / tool_end / error / agent_end
    timestamp: float = field(default_factory=time.time)
    data: dict = field(default_factory=dict)
    duration_ms: float | None = None


class EventHandler(Protocol):
    """事件处理器接口"""
    def handle(self, event: AgentEvent) -> None: ...
