"""Request/response models for conversational job matching."""

from typing import Literal

from pydantic import BaseModel, Field


class MatchScope(BaseModel):
    """Which jobs a turn is allowed to consider.

    Exactly one mode is active. ``companies`` restricts to the named companies;
    ``favorites`` restricts to the user's saved jobs.
    """

    mode: Literal["companies", "favorites"] = "companies"
    company_ids: list[str] = Field(default_factory=list)

    def describe(self) -> str:
        """Render the scope for the agent's system prompt."""
        if self.mode == "favorites":
            return "用户的收藏岗位"
        if self.company_ids:
            return "、".join(self.company_ids) + " 的岗位"
        return "未指定范围"


class TraceStep(BaseModel):
    """One entry in an assistant turn's reasoning trace.

    ``narration`` steps hold the model's intermediate prose; ``tool`` steps hold
    the call, its arguments, and the observation the model read back.
    """

    type: Literal["narration", "tool"] = "tool"
    index: int = 0
    content: str = ""
    call_id: str | None = None
    name: str | None = None
    label: str = ""
    args: dict | str | None = None
    ok: bool = True
    summary: str = ""
    observation: str = ""
    count: int | None = None
    duration_ms: float | None = None


class MatchMessageOut(BaseModel):
    """A stored message as the UI renders it."""

    id: str
    session_id: str
    role: str
    content: str = ""
    final_answer: str | None = None
    scope: MatchScope | None = None
    resume_id: str | None = None
    steps: list[TraceStep] = Field(default_factory=list)
    job_ids: list[str] = Field(default_factory=list)
    created_at: str


class ConversationOut(BaseModel):
    """A conversation as listed in the sidebar."""

    id: str
    title: str
    message_count: int = 0
    created_at: str
    updated_at: str


class ConversationCreate(BaseModel):
    """Payload for creating a conversation."""

    title: str = ""


class ConversationUpdate(BaseModel):
    """Payload for renaming a conversation."""

    title: str = Field(min_length=1, max_length=200)


class SendMessageRequest(BaseModel):
    """A user turn."""

    content: str = Field(min_length=1, max_length=8000)
    scope: MatchScope = Field(default_factory=MatchScope)
    resume_id: str | None = None
