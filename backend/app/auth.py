from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import aiosqlite
import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, status

from app.config import settings
from app.database import get_db
from app.schemas import TokenData
from app.users import STATUS_APPROVED


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        sub: Optional[str] = payload.get("sub")
        username: Optional[str] = payload.get("username")
        if sub is None or username is None:
            return None
        return TokenData(user_id=int(sub), username=username)
    except (jwt.PyJWTError, ValueError):
        return None


async def get_current_user_optional(
    access_token: Optional[str] = Cookie(default=None),
    db: aiosqlite.Connection = Depends(get_db),
) -> Optional[dict]:
    if not access_token:
        return None
    token_data = decode_token(access_token)
    if token_data is None:
        return None
    async with db.execute(
        "SELECT id, username, role, status FROM users WHERE id = ?",
        (token_data.user_id,),
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    user = dict(row)
    if user.get("status") != STATUS_APPROVED:
        return None
    return user


async def get_current_user(
    user: Optional[dict] = Depends(get_current_user_optional),
) -> dict:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Non authentifié",
        )
    return user
