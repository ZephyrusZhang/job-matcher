"""Database service for the agent framework store.

Ported from the fastapi-langgraph-agent template. Wraps the SQLModel engine for
users and sessions in the agent Postgres database.

Unlike the template — which manages this schema with Alembic — the tables are
created on demand via ``create_all()``. The schema is small and framework-owned;
the business schema keeps living in ``app/database.py`` against SQLite.
"""

from typing import (
    List,
    Optional,
)

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import QueuePool
from sqlmodel import (
    Session as DBSession,
)
from sqlmodel import (
    SQLModel,
    col,
    create_engine,
    select,
    text,
)

from app.core.config import (
    Environment,
    settings,
)
from app.core.db.models import (
    Session as AgentSession,
)
from app.core.db.models import (
    User,
)
from app.core.logging import logger


class DatabaseService:
    """Synchronous SQLModel access to the agent Postgres store.

    The engine is created lazily so importing this module never requires a
    reachable database — important because the business API must keep serving
    even when the agent store is down.
    """

    def __init__(self):
        """Prepare the service without connecting."""
        self._engine = None

    @property
    def engine(self):
        """Return the SQLAlchemy engine, creating it on first use."""
        if self._engine is None:
            self._engine = create_engine(
                # Explicit psycopg (v3) driver: SQLAlchemy's bare "postgresql://"
                # scheme resolves to psycopg2, which this project does not install.
                settings.postgres_url("postgresql+psycopg"),
                pool_pre_ping=True,
                poolclass=QueuePool,
                pool_size=settings.POSTGRES_POOL_SIZE,
                max_overflow=settings.POSTGRES_MAX_OVERFLOW,
                pool_timeout=30,
                pool_recycle=1800,
            )
            logger.info(
                "agent_database_engine_created",
                host=settings.POSTGRES_HOST,
                database=settings.POSTGRES_DB,
                pool_size=settings.POSTGRES_POOL_SIZE,
            )
        return self._engine

    async def create_tables(self) -> None:
        """Create the framework tables if they do not exist.

        Raises:
            SQLAlchemyError: When the database is unreachable outside production.
        """
        try:
            SQLModel.metadata.create_all(self.engine)
            logger.info("agent_database_tables_ready")
        except SQLAlchemyError as e:
            logger.error("agent_database_table_creation_failed", error=str(e))
            if settings.ENVIRONMENT != Environment.PRODUCTION:
                raise

    async def create_user(self, email: str, password: str, username: str | None = None) -> User:
        """Create a user with an already-hashed password."""
        with DBSession(self.engine) as session:
            user = User(email=email, hashed_password=password, username=username)
            session.add(user)
            session.commit()
            session.refresh(user)
            logger.info("user_created", email=email)
            return user

    async def get_user(self, user_id: int) -> Optional[User]:
        """Return a user by primary key."""
        with DBSession(self.engine) as session:
            return session.get(User, user_id)

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Return a user by email address."""
        with DBSession(self.engine) as session:
            return session.exec(select(User).where(User.email == email)).first()

    async def delete_user_by_email(self, email: str) -> bool:
        """Delete a user by email. Returns ``False`` when not found."""
        with DBSession(self.engine) as session:
            user = session.exec(select(User).where(User.email == email)).first()
            if not user:
                return False
            session.delete(user)
            session.commit()
            logger.info("user_deleted", email=email)
            return True

    async def create_session(
        self,
        session_id: str,
        user_id: int,
        agent: str = "",
        name: str = "",
        username: str | None = None,
    ) -> AgentSession:
        """Create an agent session bound to a user."""
        with DBSession(self.engine) as session:
            agent_session = AgentSession(
                id=session_id, user_id=user_id, agent=agent, name=name, username=username
            )
            session.add(agent_session)
            session.commit()
            session.refresh(agent_session)
            logger.info("session_created", session_id=session_id, user_id=user_id, agent=agent)
            return agent_session

    async def get_session(self, session_id: str) -> Optional[AgentSession]:
        """Return a session by ID."""
        with DBSession(self.engine) as session:
            return session.get(AgentSession, session_id)

    async def get_user_sessions(self, user_id: int) -> List[AgentSession]:
        """Return all sessions belonging to a user, oldest first."""
        with DBSession(self.engine) as session:
            statement = (
                select(AgentSession)
                .where(col(AgentSession.user_id) == user_id)
                .order_by(col(AgentSession.created_at))
            )
            return list(session.exec(statement).all())

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID. Returns ``False`` when not found."""
        with DBSession(self.engine) as session:
            agent_session = session.get(AgentSession, session_id)
            if not agent_session:
                return False
            session.delete(agent_session)
            session.commit()
            logger.info("session_deleted", session_id=session_id)
            return True

    async def update_session_name(self, session_id: str, name: str) -> Optional[AgentSession]:
        """Rename a session. Returns ``None`` when the session is missing."""
        with DBSession(self.engine) as session:
            agent_session = session.get(AgentSession, session_id)
            if not agent_session:
                return None
            agent_session.name = name
            session.add(agent_session)
            session.commit()
            session.refresh(agent_session)
            logger.info("session_name_updated", session_id=session_id, name=name)
            return agent_session

    async def health_check(self) -> bool:
        """Return ``True`` when the agent store answers a trivial query."""
        try:
            with DBSession(self.engine) as session:
                session.exec(text("SELECT 1"))  # pyright: ignore[reportArgumentType]
                return True
        except Exception as e:
            logger.warning("agent_database_health_check_failed", error=str(e))
            return False


database_service = DatabaseService()
