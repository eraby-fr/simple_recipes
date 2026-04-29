from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 32:
            raise ValueError("Le nom d'utilisateur doit faire entre 3 et 32 caractères")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Le mot de passe doit faire au moins 8 caractères")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime


class TokenData(BaseModel):
    user_id: int
    username: str


class RecipeCreate(BaseModel):
    title: str
    content: str
    summary: str = ""
    tags: list[str] = []

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le titre ne peut pas être vide")
        return v

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        return [t.strip().lower() for t in v if t.strip()]


class RecipeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list[str]] = None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        return [t.strip().lower() for t in v if t.strip()]


class RecipeOut(BaseModel):
    id: str
    slug: str
    title: str
    summary: str
    author_id: int
    author_username: str
    tags: list[str]
    created_at: datetime
    updated_at: datetime
    cover_image_url: Optional[str] = None


class RecipeDetail(RecipeOut):
    content_html: str
    raw_content: str
