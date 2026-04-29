from __future__ import annotations

import re
import uuid
from typing import Optional

import aiosqlite
import bleach
import markdown as md_lib
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.auth import get_current_user, get_current_user_optional
from app.database import get_db
from app.schemas import RecipeCreate, RecipeDetail, RecipeOut, RecipeUpdate
from app.storage import (
    delete_image,
    delete_recipe_dir,
    fix_image_urls,
    get_cover_image_url,
    list_images,
    read_recipe_content,
    save_image,
    slugify,
    validate_slug,
    write_recipe_content,
)


def _valid_slug(slug: str) -> str:
    try:
        return validate_slug(slug)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Slug invalide")


router = APIRouter(prefix="/api/recipes", tags=["recipes"])

_MD_EXTENSIONS = ["extra", "sane_lists", "toc"]

_ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "strong", "b", "em", "i", "s", "del",
    "ul", "ol", "li",
    "blockquote", "pre", "code",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span",
    "details", "summary",
]
_ALLOWED_ATTRS: dict = {
    "a": ["href", "title", "rel"],
    "img": ["src", "alt", "title", "width", "height"],
    "code": ["class"],
    "div": ["class"],
    "span": ["class"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}


def _sanitize_html(html: str) -> str:
    return bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        strip=True,
    )


def _render_markdown(text: str, slug: str) -> str:
    html = md_lib.markdown(text, extensions=_MD_EXTENSIONS)
    html = fix_image_urls(html, slug)
    return _sanitize_html(html)


async def _ensure_unique_slug(db: aiosqlite.Connection, base_slug: str) -> str:
    slug = base_slug
    counter = 1
    while True:
        async with db.execute("SELECT 1 FROM recipes WHERE slug = ?", (slug,)) as cur:
            if not await cur.fetchone():
                return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


async def _get_recipe_tags(db: aiosqlite.Connection, recipe_id: str) -> list[str]:
    async with db.execute(
        """
        SELECT t.name FROM tags t
        JOIN recipe_tags rt ON rt.tag_id = t.id
        WHERE rt.recipe_id = ?
        ORDER BY t.name
        """,
        (recipe_id,),
    ) as cur:
        return [row["name"] async for row in cur]


async def _upsert_tags(
    db: aiosqlite.Connection, recipe_id: str, tag_names: list[str]
) -> None:
    await db.execute("DELETE FROM recipe_tags WHERE recipe_id = ?", (recipe_id,))
    for name in tag_names:
        await db.execute(
            "INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,)
        )
        async with db.execute("SELECT id FROM tags WHERE name = ?", (name,)) as cur:
            tag_row = await cur.fetchone()
        await db.execute(
            "INSERT OR IGNORE INTO recipe_tags (recipe_id, tag_id) VALUES (?, ?)",
            (recipe_id, tag_row["id"]),
        )


async def _upsert_fts(
    db: aiosqlite.Connection,
    recipe_id: str,
    title: str,
    body: str,
    tags: list[str],
) -> None:
    await db.execute("DELETE FROM recipes_fts WHERE recipe_id = ?", (recipe_id,))
    await db.execute(
        "INSERT INTO recipes_fts (recipe_id, title, body, tags) VALUES (?, ?, ?, ?)",
        (recipe_id, title, body, " ".join(tags)),
    )


def _row_to_out(row: aiosqlite.Row, tags: list[str]) -> RecipeOut:
    d = dict(row)
    cover = get_cover_image_url(d["slug"])
    return RecipeOut(
        id=d["id"],
        slug=d["slug"],
        title=d["title"],
        summary=d["summary"],
        author_id=d["author_id"],
        author_username=d["author_username"],
        tags=tags,
        created_at=d["created_at"],
        updated_at=d["updated_at"],
        cover_image_url=cover,
    )


@router.get("", response_model=list[RecipeOut])
async def list_recipes(
    q: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[RecipeOut]:
    offset = (page - 1) * page_size
    results: list[RecipeOut] = []

    if q:
        escaped = re.sub(r'["\*\(\)\:\^~]', " ", q).strip()
        if not escaped:
            return []
        async with db.execute(
            """
            SELECT r.id, r.slug, r.title, r.summary, r.author_id, r.created_at,
                   r.updated_at, u.username AS author_username
            FROM recipes_fts fts
            JOIN recipes r ON r.id = fts.recipe_id
            JOIN users u ON u.id = r.author_id
            WHERE recipes_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
            """,
            (escaped + "*", page_size, offset),
        ) as cur:
            rows = await cur.fetchall()
    elif tag:
        async with db.execute(
            """
            SELECT r.id, r.slug, r.title, r.summary, r.author_id, r.created_at,
                   r.updated_at, u.username AS author_username
            FROM recipes r
            JOIN users u ON u.id = r.author_id
            JOIN recipe_tags rt ON rt.recipe_id = r.id
            JOIN tags t ON t.id = rt.tag_id
            WHERE t.name = ?
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (tag, page_size, offset),
        ) as cur:
            rows = await cur.fetchall()
    else:
        async with db.execute(
            """
            SELECT r.id, r.slug, r.title, r.summary, r.author_id, r.created_at,
                   r.updated_at, u.username AS author_username
            FROM recipes r
            JOIN users u ON u.id = r.author_id
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (page_size, offset),
        ) as cur:
            rows = await cur.fetchall()

    for row in rows:
        tags = await _get_recipe_tags(db, row["id"])
        results.append(_row_to_out(row, tags))

    return results


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def create_recipe(
    body: RecipeCreate,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> RecipeOut:
    recipe_id = str(uuid.uuid4())
    base_slug = slugify(body.title)
    slug = await _ensure_unique_slug(db, base_slug)

    write_recipe_content(slug, body.content)

    await db.execute(
        """
        INSERT INTO recipes (id, slug, title, summary, author_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (recipe_id, slug, body.title.strip(), body.summary.strip(), current_user["id"]),
    )
    await _upsert_tags(db, recipe_id, body.tags)
    await _upsert_fts(db, recipe_id, body.title, body.content, body.tags)
    await db.commit()

    async with db.execute(
        """
        SELECT r.id, r.slug, r.title, r.summary, r.author_id, r.created_at,
               r.updated_at, u.username AS author_username
        FROM recipes r JOIN users u ON u.id = r.author_id
        WHERE r.id = ?
        """,
        (recipe_id,),
    ) as cur:
        row = await cur.fetchone()

    return _row_to_out(row, body.tags)


@router.get("/{slug}", response_model=RecipeDetail)
async def get_recipe(
    slug: str = Depends(_valid_slug),
    db: aiosqlite.Connection = Depends(get_db),
) -> RecipeDetail:
    async with db.execute(
        """
        SELECT r.id, r.slug, r.title, r.summary, r.author_id, r.created_at,
               r.updated_at, u.username AS author_username
        FROM recipes r JOIN users u ON u.id = r.author_id
        WHERE r.slug = ?
        """,
        (slug,),
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recette introuvable")

    tags = await _get_recipe_tags(db, row["id"])
    raw = read_recipe_content(slug)
    out = _row_to_out(row, tags)
    return RecipeDetail(
        **out.model_dump(),
        content_html=_render_markdown(raw, slug),
        raw_content=raw,
    )


@router.patch("/{slug}", response_model=RecipeOut)
async def update_recipe(
    slug: str = Depends(_valid_slug),
    body: RecipeUpdate = ...,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> RecipeOut:
    async with db.execute(
        "SELECT id, author_id FROM recipes WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recette introuvable")
    if row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Accès interdit")

    recipe_id = row["id"]
    updates: dict = {}

    if body.title is not None:
        updates["title"] = body.title.strip()
    if body.summary is not None:
        updates["summary"] = body.summary.strip()
    if body.content is not None:
        write_recipe_content(slug, body.content)

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = datetime('now')"
        await db.execute(
            f"UPDATE recipes SET {set_clause} WHERE id = ?",
            (*updates.values(), recipe_id),
        )

    if body.tags is not None:
        await _upsert_tags(db, recipe_id, body.tags)

    raw = read_recipe_content(slug)
    if "title" not in updates:
        async with db.execute(
            "SELECT title FROM recipes WHERE id = ?", (recipe_id,)
        ) as _cur:
            _row = await _cur.fetchone()
            fts_title = _row["title"] if _row else ""
    else:
        fts_title = updates["title"]
    tags = body.tags if body.tags is not None else await _get_recipe_tags(db, recipe_id)
    await _upsert_fts(db, recipe_id, fts_title, raw, tags)

    await db.commit()

    async with db.execute(
        """
        SELECT r.id, r.slug, r.title, r.summary, r.author_id, r.created_at,
               r.updated_at, u.username AS author_username
        FROM recipes r JOIN users u ON u.id = r.author_id
        WHERE r.id = ?
        """,
        (recipe_id,),
    ) as cur:
        updated_row = await cur.fetchone()

    final_tags = await _get_recipe_tags(db, recipe_id)
    return _row_to_out(updated_row, final_tags)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_recipe(
    slug: str = Depends(_valid_slug),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    async with db.execute(
        "SELECT id, author_id FROM recipes WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recette introuvable")
    if row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Accès interdit")

    recipe_id = row["id"]
    await db.execute("DELETE FROM recipes_fts WHERE recipe_id = ?", (recipe_id,))
    await db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    await db.commit()
    delete_recipe_dir(slug)


@router.post("/{slug}/images")
async def upload_image(
    slug: str = Depends(_valid_slug),
    file: UploadFile = File(...),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> dict:
    async with db.execute(
        "SELECT author_id FROM recipes WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recette introuvable")
    if row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Accès interdit")

    if file.content_type not in {
        "image/jpeg", "image/png", "image/gif", "image/webp", "image/avif"
    }:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Type d'image non supporté",
        )

    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image trop volumineuse (max 20 Mo)",
        )

    filename = save_image(slug, file.filename or "image.jpg", data)
    url = f"/uploads/{slug}/images/{filename}"
    return {"filename": filename, "url": url}


@router.delete("/{slug}/images/{filename}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_image(
    slug: str = Depends(_valid_slug),
    filename: str = ...,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> None:
    async with db.execute(
        "SELECT author_id FROM recipes WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recette introuvable")
    if row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Accès interdit")

    if not delete_image(slug, filename):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Image introuvable")


@router.get("/{slug}/images")
async def list_recipe_images(
    slug: str = Depends(_valid_slug),
    db: aiosqlite.Connection = Depends(get_db),
) -> list[dict]:
    async with db.execute("SELECT 1 FROM recipes WHERE slug = ?", (slug,)) as cur:
        if not await cur.fetchone():
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recette introuvable")

    images = list_images(slug)
    return [{"filename": f, "url": f"/uploads/{slug}/images/{f}"} for f in images]
