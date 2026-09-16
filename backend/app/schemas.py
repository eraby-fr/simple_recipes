from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from app.validation import (
    MAX_CONTENT_LENGTH,
    MAX_META_LENGTH,
    MAX_PASSWORD_LENGTH,
    MAX_SUMMARY_LENGTH,
    MAX_TITLE_LENGTH,
    MAX_USERNAME_LENGTH,
    MIN_PASSWORD_LENGTH,
    MIN_USERNAME_LENGTH,
    normalize_tags,
)


class UserCreate(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        v = v.strip()
        if len(v) < MIN_USERNAME_LENGTH or len(v) > MAX_USERNAME_LENGTH:
            raise ValueError("Le nom d'utilisateur doit faire entre 3 et 32 caractères")
        return v

    @field_validator("password")
    @classmethod
    def password_valid(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError("Le mot de passe doit faire au moins 8 caractères")
        if len(v) > MAX_PASSWORD_LENGTH:
            raise ValueError("Le mot de passe ne peut pas dépasser 128 caractères")
        return v


class UserOut(BaseModel):
    id: int
    username: str
    created_at: datetime


class TokenData(BaseModel):
    user_id: int
    username: str
    token_version: int = 0


class RecipeCreate(BaseModel):
    title: str
    content: str
    summary: str = ""
    tags: list[str] = []
    prep_time: str = ""
    cook_time: str = ""
    wait_time: str = ""
    servings: str = ""
    cover_image: str = ""

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Le titre ne peut pas être vide")
        if len(v) > MAX_TITLE_LENGTH:
            raise ValueError("Le titre est trop long")
        return v

    @field_validator("content")
    @classmethod
    def content_not_too_long(cls, v: str) -> str:
        if len(v) > MAX_CONTENT_LENGTH:
            raise ValueError("Le contenu de la recette est trop long")
        return v

    @field_validator("summary")
    @classmethod
    def summary_not_too_long(cls, v: str) -> str:
        if len(v) > MAX_SUMMARY_LENGTH:
            raise ValueError("Le résumé est trop long")
        return v

    @field_validator("prep_time", "cook_time", "wait_time", "servings")
    @classmethod
    def meta_not_too_long(cls, v: str) -> str:
        if len(v) > MAX_META_LENGTH:
            raise ValueError("Cette valeur est trop longue")
        return v

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        return normalize_tags(v)


class RecipeUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: Optional[list[str]] = None
    prep_time: Optional[str] = None
    cook_time: Optional[str] = None
    wait_time: Optional[str] = None
    servings: Optional[str] = None
    cover_image: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_not_too_long(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v.strip()) > MAX_TITLE_LENGTH:
            raise ValueError("Le titre est trop long")
        return v

    @field_validator("content")
    @classmethod
    def content_not_too_long(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > MAX_CONTENT_LENGTH:
            raise ValueError("Le contenu de la recette est trop long")
        return v

    @field_validator("summary")
    @classmethod
    def summary_not_too_long(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > MAX_SUMMARY_LENGTH:
            raise ValueError("Le résumé est trop long")
        return v

    @field_validator("prep_time", "cook_time", "wait_time", "servings")
    @classmethod
    def meta_not_too_long(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and len(v) > MAX_META_LENGTH:
            raise ValueError("Cette valeur est trop longue")
        return v

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return None
        return normalize_tags(v)


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
    prep_time: str = ""
    cook_time: str = ""
    wait_time: str = ""
    servings: str = ""
    cover_image: str = ""
    cover_image_url: Optional[str] = None


class RecipeDetail(RecipeOut):
    content_html: str
    raw_content: str
