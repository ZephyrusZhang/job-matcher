"""JWT helpers for the agent framework.

Ported from the fastapi-langgraph-agent template. The token subject is the
agent session ID, which is also the LangGraph ``thread_id``.
"""

import re
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from typing import Optional

from jose import (
    JWTError,
    jwt,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.agent import Token
from app.utils.sanitization import sanitize_string

logger = get_logger(__name__)

_JWT_FORMAT = re.compile(r"^[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+\.[A-Za-z0-9-_]+$")


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> Token:
    """Create a signed access token.

    Args:
        subject: The session or user ID to encode as ``sub``.
        expires_delta: Optional custom lifetime.

    Returns:
        Token: The generated access token.

    Raises:
        RuntimeError: When ``JWT_SECRET_KEY`` is unset.
    """
    if not settings.JWT_SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is not configured")

    expire = datetime.now(UTC) + (expires_delta or timedelta(days=settings.JWT_ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode = {
        "sub": subject,
        "exp": expire,
        "iat": datetime.now(UTC),
        "jti": sanitize_string(f"{subject}-{datetime.now(UTC).timestamp()}"),
    }

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    logger.info("token_created", subject=subject, expires_at=expire.isoformat())
    return Token(access_token=encoded_jwt, expires_at=expire)


def verify_token(token: str) -> Optional[str]:
    """Verify a token and return its subject.

    Args:
        token: The JWT to verify.

    Returns:
        The subject claim, or ``None`` when verification fails.

    Raises:
        ValueError: When the token is not a well-formed JWT string.
    """
    if not token or not isinstance(token, str):
        logger.warning("token_invalid_format")
        raise ValueError("Token must be a non-empty string")

    if not _JWT_FORMAT.match(token):
        logger.warning("token_suspicious_format")
        raise ValueError("Token format is invalid - expected JWT format")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        subject: str | None = payload.get("sub")
        if subject is None:
            logger.warning("token_missing_subject")
            return None
        return subject
    except JWTError as e:
        logger.warning("token_verification_failed", error=str(e))
        return None
