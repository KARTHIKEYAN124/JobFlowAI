from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import User, get_db

hashing = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)


def hash_password(value):
    return hashing.hash(value)


def verify_password(value, encoded):
    return hashing.verify(value, encoded)


def create_token(user):
    return jwt.encode(
        {
            "sub": user.id,
            "role": user.role,
            "exp": datetime.now(UTC) + timedelta(minutes=settings.access_token_minutes),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: AsyncSession = Depends(get_db)
):
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    try:
        user_id = jwt.decode(credentials.credentials, settings.jwt_secret, algorithms=["HS256"])["sub"]
    except (InvalidTokenError, KeyError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from None
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def verify_webhook(x_webhook_secret: str = Header(default="")):
    if x_webhook_secret != settings.webhook_secret:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook secret")


def require_role(*roles: str):
    async def authorize(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return authorize
