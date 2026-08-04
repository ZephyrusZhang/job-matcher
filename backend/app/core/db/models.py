"""SQLModel ORM models for the agent framework store (Postgres).

Ported from the fastapi-langgraph-agent template.

These live in ``app/core/db`` rather than ``app/models`` on purpose: everything
under ``app/models`` is raw-SQL data access against the *business* SQLite
database, while these tables live in the separate agent Postgres instance
alongside the LangGraph checkpoint tables and mem0's pgvector collection.
"""

from datetime import (
    UTC,
    datetime,
)
from typing import (
    TYPE_CHECKING,
    List,
    Optional,
)

import bcrypt
from sqlmodel import (
    Field,
    Relationship,
    SQLModel,
)

if TYPE_CHECKING:
    pass


class TimestampedModel(SQLModel):
    """Base model carrying a creation timestamp."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class User(TimestampedModel, table=True):
    """A user account.

    Attributes:
        id: Primary key.
        email: Unique login identifier.
        hashed_password: Bcrypt password hash.
        username: Optional display name, used to personalize agent prompts.
        sessions: The user's agent sessions.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    username: Optional[str] = Field(default=None)
    sessions: List["Session"] = Relationship(back_populates="user")

    def verify_password(self, password: str) -> bool:
        """Check a plaintext password against the stored hash."""
        return bcrypt.checkpw(password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a plaintext password with bcrypt."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


class Session(TimestampedModel, table=True):
    """An agent conversation session.

    ``id`` doubles as the LangGraph ``thread_id``, which is what ties a session
    to its checkpointed conversation state.
    """

    id: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    agent: str = Field(default="", index=True)
    name: str = Field(default="")
    username: Optional[str] = Field(default=None)
    user: Optional[User] = Relationship(back_populates="sessions")
