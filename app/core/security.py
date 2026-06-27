from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ── Password Hashing ──────────────────────────────────────────────────────────
# bcrypt 4.x removed __about__ module which breaks passlib's version detection.
# We suppress the warning and use the working bcrypt backend directly.
import logging as _logging
_logging.getLogger("passlib").setLevel(_logging.ERROR)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using bcrypt."""
    # bcrypt has a 72-byte limit; pre-hash with SHA256 to support any length
    import hashlib
    safe_password = hashlib.sha256(plain_password.encode()).hexdigest()
    return pwd_context.hash(safe_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against a bcrypt hash."""
    import hashlib
    safe_password = hashlib.sha256(plain_password.encode()).hexdigest()
    return pwd_context.verify(safe_password, hashed_password)



# ── JWT Token Creation ────────────────────────────────────────────────────────
def create_access_token(
    subject: str,
    role: str,
    extra_claims: Optional[dict[str, Any]] = None,
) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived JWT refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_email_verify_token(email: str) -> str:
    """Create a one-time email verification token."""
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.JWT_EMAIL_VERIFY_EXPIRE_HOURS
    )
    payload = {
        "sub": email,
        "type": "email_verify",
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_password_reset_token(email: str) -> str:
    """Create a one-time password reset token."""
    expire = datetime.now(timezone.utc) + timedelta(
        hours=settings.JWT_PASSWORD_RESET_EXPIRE_HOURS
    )
    payload = {
        "sub": email,
        "type": "password_reset",
        "exp": expire,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ── JWT Token Decoding ────────────────────────────────────────────────────────
def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.
    Raises JWTError if invalid or wrong type.
    """
    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
    if payload.get("type") != expected_type:
        raise JWTError(f"Expected token type '{expected_type}', got '{payload.get('type')}'")
    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    return decode_token(token, "access")


def decode_refresh_token(token: str) -> dict[str, Any]:
    return decode_token(token, "refresh")


def decode_email_verify_token(token: str) -> dict[str, Any]:
    return decode_token(token, "email_verify")


def decode_password_reset_token(token: str) -> dict[str, Any]:
    return decode_token(token, "password_reset")
