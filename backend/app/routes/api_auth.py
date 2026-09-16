import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import (
    create_access_token,
    get_current_user,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.schemas import UserCreate
from app.users import bump_token_version, login_block_reason

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_403_FORBIDDEN)
async def register() -> dict:
    raise HTTPException(
        status.HTTP_403_FORBIDDEN,
        detail="L'inscription se fait uniquement via la page /register",
    )


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: UserCreate,
    response: Response,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    async with db.execute(
        "SELECT id, username, hashed_password, status, token_version "
        "FROM users WHERE username = ?",
        (body.username,),
    ) as cur:
        row = await cur.fetchone()

    if not row or not verify_password(body.password, row["hashed_password"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides"
        )

    blocked = login_block_reason(row["status"])
    if blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=blocked)

    token = create_access_token(
        {
            "sub": str(row["id"]),
            "username": row["username"],
            "ver": int(row["token_version"] or 0),
        },
    )
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    return {"message": "Connecté"}


@router.post("/logout")
async def logout(
    response: Response,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    # Revoke the token itself, not just the browser's copy of it.
    await bump_token_version(db, current_user["id"])
    response.delete_cookie(
        "access_token",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return {"message": "Déconnecté"}
