import aiosqlite
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.schemas import UserCreate, UserOut

limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def register(
    request: Request,
    body: UserCreate,
    db: aiosqlite.Connection = Depends(get_db),
) -> UserOut:
    async with db.execute(
        "SELECT id FROM users WHERE username = ?", (body.username,)
    ) as cur:
        if await cur.fetchone():
            raise HTTPException(
                status.HTTP_409_CONFLICT, detail="Ce nom d'utilisateur est déjà pris"
            )

    hashed = hash_password(body.password)
    async with db.execute(
        "INSERT INTO users (username, hashed_password) VALUES (?, ?) RETURNING id, username, created_at",
        (body.username, hashed),
    ) as cur:
        row = await cur.fetchone()
    await db.commit()
    return UserOut.model_validate(dict(row))


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    body: UserCreate,
    response: Response,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict:
    async with db.execute(
        "SELECT id, username, hashed_password FROM users WHERE username = ?",
        (body.username,),
    ) as cur:
        row = await cur.fetchone()

    if not row or not verify_password(body.password, row["hashed_password"]):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Identifiants invalides"
        )

    token = create_access_token(
        {"sub": str(row["id"]), "username": row["username"]},
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
    _: dict = Depends(get_current_user),
) -> dict:
    response.delete_cookie("access_token")
    return {"message": "Déconnecté"}
