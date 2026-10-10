import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_session, set_user_rls
from app.models import AuthSession, Role, User

password_hasher = PasswordHasher(
    time_cost=3, memory_cost=64 * 1024, parallelism=4, hash_len=32, salt_len=16
)
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Password must be at least 12 characters")
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, VerifyMismatchError, InvalidHashError):
        return False


def _token(claims: dict, expires: timedelta) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {**claims, "iat": now, "exp": now + expires},
        settings.session_secret.get_secret_value(),
        algorithm="HS256",
    )


def issue_access_token(user: User, session_id: UUID) -> str:
    return _token(
        {"sub": str(user.id), "role": user.role.value, "sid": str(session_id), "kind": "access"},
        timedelta(minutes=settings.access_token_minutes),
    )


def issue_refresh_token(user: User, session_id: UUID) -> str:
    return _token(
        {"sub": str(user.id), "role": user.role.value, "sid": str(session_id), "kind": "refresh"},
        timedelta(days=settings.refresh_token_days),
    )


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def opaque_token() -> str:
    return secrets.token_urlsafe(32)


@dataclass(frozen=True)
class AuthContext:
    user: User
    session: AuthSession


async def current_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> AuthContext:
    if credentials is None:
        raise HTTPException(status_code=401, detail={"code": "authentication_required"})
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.session_secret.get_secret_value(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "sid", "kind"]},
        )
        if claims.get("kind") != "access":
            raise ValueError("wrong token kind")
        user_id, session_id = UUID(claims["sub"]), UUID(claims["sid"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise HTTPException(status_code=401, detail={"code": "invalid_token"}) from None

    result = await db.execute(
        select(User, AuthSession)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            User.id == user_id,
            User.status == "active",
            AuthSession.id == session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
            or_(
                AuthSession.last_seen_at.is_(None),
                AuthSession.last_seen_at
                > datetime.now(UTC) - timedelta(minutes=settings.idle_session_minutes),
            ),
        )
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=401, detail={"code": "session_expired"})
    row[1].last_seen_at = datetime.now(UTC)
    await db.commit()
    await set_user_rls(db, str(user_id))
    return AuthContext(user=row[0], session=row[1])


def require_roles(*roles: Role):
    async def dependency(
        auth: Annotated[AuthContext, Depends(current_auth)],
    ) -> AuthContext:
        if auth.user.role not in roles:
            raise HTTPException(status_code=403, detail={"code": "forbidden"})
        return auth

    return dependency
