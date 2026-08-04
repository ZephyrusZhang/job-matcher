"""Authentication endpoints for the agent framework.

Ported from the fastapi-langgraph-agent template.

This router is only mounted when ``AUTH_ENABLED=true`` (see ``app/main.py``).
The existing business endpoints under ``/api`` never require a token regardless
of this setting.
"""

import uuid
from typing import List

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
    Request,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.config import settings
from app.core.db.models import Session as AgentSession
from app.core.db.models import User
from app.core.db.service import database_service
from app.core.limiter import limiter
from app.core.logging import (
    bind_context,
    logger,
)
from app.schemas.agent import (
    SessionRequest,
    SessionResponse,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from app.utils.auth import (
    create_access_token,
    verify_token,
)
from app.utils.sanitization import (
    sanitize_email,
    sanitize_string,
    validate_password_strength,
)

router = APIRouter()
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """Resolve the authenticated user from a bearer token.

    Args:
        credentials: The bearer credentials.

    Returns:
        The authenticated user.

    Raises:
        HTTPException: When the token is invalid or the user is unknown.
    """
    try:
        token = sanitize_string(credentials.credentials)
        user_id = verify_token(token)
        if user_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await database_service.get_user(int(user_id))
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")

        bind_context(user_id=user.id)
        return user
    except ValueError as ve:
        logger.warning("token_validation_failed", error=str(ve))
        raise HTTPException(status_code=422, detail="Invalid token format")


async def get_current_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> AgentSession:
    """Resolve the agent session from a bearer token.

    Use this as the dependency for any endpoint that drives an agent — the
    session ID it returns is the LangGraph ``thread_id``.

    Args:
        credentials: The bearer credentials.

    Returns:
        The agent session.

    Raises:
        HTTPException: When the token is invalid or the session is unknown.
    """
    try:
        token = sanitize_string(credentials.credentials)
        session_id = verify_token(token)
        if session_id is None:
            raise HTTPException(
                status_code=401,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        session = await database_service.get_session(sanitize_string(session_id))
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")

        bind_context(user_id=session.user_id, session_id=session.id)
        return session
    except ValueError as ve:
        logger.warning("token_validation_failed", error=str(ve))
        raise HTTPException(status_code=422, detail="Invalid token format")


@router.post("/register", response_model=UserResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["register"][0])
async def register_user(request: Request, user_data: UserCreate):
    """Register a new user and return an access token."""
    try:
        sanitized_email = sanitize_email(user_data.email)
        password = user_data.password.get_secret_value()
        validate_password_strength(password)

        if await database_service.get_user_by_email(sanitized_email):
            raise HTTPException(status_code=400, detail="Email already registered")

        user = await database_service.create_user(
            email=sanitized_email,
            password=User.hash_password(password),
            username=sanitize_string(user_data.username) if user_data.username else None,
        )

        token = create_access_token(str(user.id))
        return UserResponse(id=user.id or 0, email=user.email, username=user.username, token=token)
    except ValueError as ve:
        logger.warning("user_registration_validation_failed", error=str(ve))
        raise HTTPException(status_code=422, detail=str(ve))


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["login"][0])
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    grant_type: str = Form(default="password"),
):
    """Exchange credentials for a user access token."""
    if sanitize_string(grant_type) != "password":
        raise HTTPException(status_code=400, detail="Unsupported grant type. Must be 'password'")

    user = await database_service.get_user_by_email(sanitize_string(email))
    if not user or not user.verify_password(password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token.access_token, token_type="bearer", expires_at=token.expires_at)


@router.post("/session", response_model=SessionResponse)
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["session"][0])
async def create_session(
    request: Request,
    body: SessionRequest,
    user: User = Depends(get_current_user),
):
    """Create an agent session and return a session-scoped token."""
    session_id = str(uuid.uuid4())
    session = await database_service.create_session(
        session_id=session_id,
        user_id=user.id or 0,
        agent=sanitize_string(body.agent),
        name=sanitize_string(body.name),
        username=user.username,
    )
    token = create_access_token(session_id)
    return SessionResponse(session_id=session.id, agent=session.agent, name=session.name, token=token)


@router.get("/sessions", response_model=List[SessionResponse])
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["session"][0])
async def list_sessions(request: Request, user: User = Depends(get_current_user)):
    """List every session belonging to the authenticated user."""
    sessions = await database_service.get_user_sessions(user.id or 0)
    return [
        SessionResponse(
            session_id=s.id,
            agent=s.agent,
            name=s.name,
            token=create_access_token(s.id),
        )
        for s in sessions
    ]


@router.delete("/session/{session_id}")
@limiter.limit(settings.RATE_LIMIT_ENDPOINTS["session"][0])
async def delete_session(request: Request, session_id: str, user: User = Depends(get_current_user)):
    """Delete one of the authenticated user's sessions."""
    session = await database_service.get_session(sanitize_string(session_id))
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    await database_service.delete_session(session.id)
    return {"message": "Session deleted successfully"}
