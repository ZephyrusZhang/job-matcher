from pydantic import BaseModel


class ChatMessageRequest(BaseModel):
    report_id: str
    message: str


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: str


class ChatHistoryOut(BaseModel):
    report_id: str
    messages: list[ChatMessageOut]
