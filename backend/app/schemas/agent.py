"""Pydantic schemas for the agent framework.

Ported from the fastapi-langgraph-agent template (its ``schemas/base.py``,
``auth.py``, ``chat.py`` and ``graph.py`` merged into one module).

Kept separate from the existing business schemas — in particular
``app/schemas/chat.py``, which models the report follow-up chat feature and is
unrelated to agent conversations.
"""

import re
from datetime import datetime
from typing import (
    Annotated,
    List,
    Literal,
    Optional,
)
from uuid import (
    UUID,
    uuid4,
)

from asgi_correlation_id import correlation_id
from langgraph.graph.message import add_messages
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)


def _get_request_id() -> UUID:
    """Return the current correlation ID, or a fresh UUID as a fallback."""
    value = correlation_id.get()
    try:
        return UUID(value) if value else uuid4()
    except ValueError:
        return uuid4()


class BaseResponse(BaseModel):
    """Base response carrying the request correlation ID."""

    request_id: UUID = Field(default_factory=_get_request_id, description="Unique identifier for this request")


# ── Conversation ──────────────────────────────────────────────────────────


class Message(BaseModel):
    """A single conversation message."""

    model_config = {"extra": "ignore"}

    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message", min_length=1)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Reject script tags and null bytes.

        Args:
            v: The content to validate.

        Returns:
            The validated content.

        Raises:
            ValueError: When the content contains disallowed patterns.
        """
        if re.search(r"<script.*?>.*?</script>", v, re.IGNORECASE | re.DOTALL):
            raise ValueError("Content contains potentially harmful script tags")
        if "\0" in v:
            raise ValueError("Content contains null bytes")
        return v


class GraphState(BaseModel):
    """Default state for a LangGraph agent.

    Agents needing extra state subclass this and pass the subclass to
    ``BaseAgent(state_schema=...)``.
    """

    messages: Annotated[list, add_messages] = Field(
        default_factory=list, description="The messages in the conversation"
    )
    long_term_memory: str = Field(default="", description="Long-term memory relevant to this conversation")


# ── Auth ──────────────────────────────────────────────────────────────────


class Token(BaseModel):
    """A JWT access token."""

    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field(default="bearer", description="The type of token")
    expires_at: datetime = Field(..., description="The token expiration timestamp")


class TokenResponse(BaseResponse):
    """Login response."""

    access_token: str = Field(..., description="The JWT access token")
    token_type: str = Field(default="bearer", description="The type of token")
    expires_at: datetime = Field(..., description="When the token expires")


class UserCreate(BaseModel):
    """Registration payload."""

    email: EmailStr = Field(..., description="User's email address")
    password: SecretStr = Field(..., description="User's password", min_length=8, max_length=64)
    username: Optional[str] = Field(default=None, description="Optional display name", max_length=50)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: SecretStr) -> SecretStr:
        """Enforce password strength.

        Args:
            v: The password to validate.

        Returns:
            The validated password.

        Raises:
            ValueError: When the password is too weak.
        """
        password = v.get_secret_value()
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", password):
            raise ValueError("Password must contain at least one number")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            raise ValueError("Password must contain at least one special character")
        return v


class UserResponse(BaseResponse):
    """Registration response."""

    id: int = Field(..., description="User's ID")
    email: str = Field(..., description="User's email address")
    username: Optional[str] = Field(default=None, description="Optional display name")
    token: Token = Field(..., description="Authentication token")


class SessionRequest(BaseModel):
    """Payload for creating an agent session."""

    agent: str = Field(default="", description="Name of the agent this session talks to", max_length=64)
    name: str = Field(default="", description="Human-readable session name", max_length=100)


class SessionResponse(BaseResponse):
    """Agent session creation response."""

    session_id: str = Field(..., description="The unique identifier for the agent session")
    agent: str = Field(default="", description="Name of the agent this session talks to")
    name: str = Field(default="", description="Name of the session", max_length=100)
    token: Token = Field(..., description="The authentication token for the session")

    @field_validator("name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        """Strip characters that could break downstream rendering."""
        return re.sub(r'[<>{}[\]()\'"`]', "", v)


class ChatRequest(BaseModel):
    """A chat turn sent to an agent."""

    messages: List[Message] = Field(..., description="List of messages in the conversation", min_length=1)


class ChatResponse(BaseResponse):
    """An agent's reply."""

    messages: List[Message] = Field(..., description="List of messages in the conversation")


class StreamResponse(BaseResponse):
    """A single chunk of a streamed agent reply."""

    content: str = Field(default="", description="The content of the current chunk")
    done: bool = Field(default=False, description="Whether the stream is complete")
