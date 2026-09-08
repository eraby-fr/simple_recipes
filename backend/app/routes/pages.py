from __future__ import annotations

import re
from typing import Optional

import uuid

import aiosqlite
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.auth import (
    create_access_token,
    get_current_user_optional,
    hash_password,
    verify_password,
)
from app.config import settings
from app.database import get_db
from app.routes.api_recipes import (
    _ensure_unique_slug,
    _get_recipe_tags,
    _render_markdown,
    _row_to_out,
    _sanitize_html,
    _upsert_fts,
    _upsert_tags,
)
from app.schemas import RecipeOut
from app.storage import (
    delete_image,
    delete_recipe_dir,
    list_images,
    read_recipe_content,
    save_image,
    slugify,
    validate_slug,
    write_recipe_content,
)


_limiter = Limiter(key_func=get_remote_address)


def _valid_slug(slug: str) -> str:
    try:
        return validate_slug(slug)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Slug invalide")


router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="templates")

_MD_EXTENSIONS = ["extra", "sane_lists", "toc"]


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


def _htmx_redirect(url: str) -> HTMLResponse:
    r = HTMLResponse("")
    r.headers["HX-Redirect"] = url
    return r


# ---------------------------------------------------------------------------
# Auth pages
# ---------------------------------------------------------------------------


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if current_user:
        return _redirect("/")
    return templates.TemplateResponse(
        "login.html", {"request": request, "current_user": current_user, "error": None}
    )


@router.post("/login", response_class=HTMLResponse)
@_limiter.limit("10/minute")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: aiosqlite.Connection = Depends(get_db),
) -> HTMLResponse:
    async with db.execute(
        "SELECT id, username, hashed_password FROM users WHERE username = ?",
        (username,),
    ) as cur:
        row = await cur.fetchone()

    if not row or not verify_password(password, row["hashed_password"]):
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "current_user": None,
                "error": "Identifiants incorrects",
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token = create_access_token({"sub": str(row["id"]), "username": row["username"]})
    resp = _redirect("/")
    resp.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.access_token_expire_minutes * 60,
    )
    return resp


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if current_user:
        return _redirect("/")
    return templates.TemplateResponse(
        "register.html",
        {"request": request, "current_user": current_user, "error": None},
    )


@router.post("/register", response_class=HTMLResponse)
@_limiter.limit("10/minute")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: aiosqlite.Connection = Depends(get_db),
) -> HTMLResponse:
    username = username.strip()
    error: Optional[str] = None

    if len(username) < 3 or len(username) > 32:
        error = "Le nom d'utilisateur doit faire entre 3 et 32 caractères"
    elif len(password) < 8:
        error = "Le mot de passe doit faire au moins 8 caractères"

    if not error:
        async with db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ) as cur:
            if await cur.fetchone():
                error = "Ce nom d'utilisateur est déjà pris"

    if error:
        return templates.TemplateResponse(
            "register.html",
            {"request": request, "current_user": None, "error": error},
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    hashed = hash_password(password)
    await db.execute(
        "INSERT INTO users (username, hashed_password) VALUES (?, ?)",
        (username, hashed),
    )
    await db.commit()
    return _redirect("/login")


@router.post("/logout")
async def logout(response: Response) -> RedirectResponse:
    resp = _redirect("/login")
    resp.delete_cookie("access_token")
    return resp


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    q: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = 1,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _redirect("/login")
    recipes = await _fetch_recipes(db, q=q, tag=tag, page=page)
    all_tags = await _fetch_all_tags(db)

    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "partials/recipe_list.html",
            {
                "request": request,
                "recipes": recipes,
                "current_user": current_user,
                "q": q,
                "tag": tag,
            },
        )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "recipes": recipes,
            "all_tags": all_tags,
            "current_user": current_user,
            "q": q,
            "tag": tag,
        },
    )


# ---------------------------------------------------------------------------
# Create recipe  (MUST be before /recipes/{slug} to avoid shadowing)
# ---------------------------------------------------------------------------


@router.get("/recipes/new", response_class=HTMLResponse)
async def new_recipe_page(
    request: Request,
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _redirect("/login")
    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "current_user": current_user,
            "recipe": None,
            "images": [],
            "error": None,
        },
    )


@router.post("/recipes", response_class=HTMLResponse)
async def create_recipe_page(
    request: Request,
    title: str = Form(...),
    summary: str = Form(default=""),
    tags_raw: str = Form(default="", alias="tags"),
    content: str = Form(default=""),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _redirect("/login")
    title = title.strip()
    if not title:
        return templates.TemplateResponse(
            "edit.html",
            {
                "request": request,
                "current_user": current_user,
                "recipe": None,
                "images": [],
                "error": "Le titre est obligatoire",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    tag_names = [t.strip().lower() for t in tags_raw.split(",") if t.strip()]
    recipe_id = str(uuid.uuid4())
    base_slug = slugify(title)
    slug = await _ensure_unique_slug(db, base_slug)

    write_recipe_content(slug, content)

    await db.execute(
        "INSERT INTO recipes (id, slug, title, summary, author_id) VALUES (?, ?, ?, ?, ?)",
        (recipe_id, slug, title, summary.strip(), current_user["id"]),
    )
    await _upsert_tags(db, recipe_id, tag_names)
    await _upsert_fts(db, recipe_id, title, content, tag_names)
    await db.commit()

    return _redirect(f"/recipes/{slug}")


# ---------------------------------------------------------------------------
# Recipe detail
# ---------------------------------------------------------------------------


@router.get("/recipes/{slug}", response_class=HTMLResponse)
async def recipe_detail(
    request: Request,
    slug: str = Depends(_valid_slug),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _redirect("/login")
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
    images = list_images(slug)

    return templates.TemplateResponse(
        "recipe.html",
        {
            "request": request,
            "recipe": _row_to_out(row, tags),
            "content_html": _render_markdown(raw, slug),
            "images": images,
            "current_user": current_user,
            "is_author": current_user is not None
            and current_user["id"] == row["author_id"],
        },
    )


# ---------------------------------------------------------------------------
# Edit recipe
# ---------------------------------------------------------------------------


@router.get("/recipes/{slug}/edit", response_class=HTMLResponse)
async def edit_recipe_page(
    request: Request,
    slug: str = Depends(_valid_slug),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _redirect("/login")
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
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Accès interdit")

    tags = await _get_recipe_tags(db, row["id"])
    raw = read_recipe_content(slug)
    images = list_images(slug)
    content_html = _render_markdown(raw, slug)

    return templates.TemplateResponse(
        "edit.html",
        {
            "request": request,
            "current_user": current_user,
            "recipe": _row_to_out(row, tags),
            "raw_content": raw,
            "content_html": content_html,
            "images": images,
            "error": None,
        },
    )


@router.post("/recipes/{slug}/edit", response_class=HTMLResponse)
async def update_recipe_page(
    request: Request,
    slug: str = Depends(_valid_slug),
    title: str = Form(...),
    summary: str = Form(default=""),
    tags_raw: str = Form(default="", alias="tags"),
    content: str = Form(default=""),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _redirect("/login")
    async with db.execute(
        "SELECT id, author_id FROM recipes WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)

    recipe_id = row["id"]
    title = title.strip()
    tag_names = [t.strip().lower() for t in tags_raw.split(",") if t.strip()]

    write_recipe_content(slug, content)

    await db.execute(
        """
        UPDATE recipes
        SET title = ?, summary = ?, updated_at = datetime('now')
        WHERE id = ?
        """,
        (title, summary.strip(), recipe_id),
    )
    await _upsert_tags(db, recipe_id, tag_names)
    await _upsert_fts(db, recipe_id, title, content, tag_names)
    await db.commit()

    return _redirect(f"/recipes/{slug}")


# ---------------------------------------------------------------------------
# Delete recipe
# ---------------------------------------------------------------------------


@router.delete("/recipes/{slug}", response_class=HTMLResponse)
async def delete_recipe_page(
    slug: str = Depends(_valid_slug),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _htmx_redirect("/login")
    async with db.execute(
        "SELECT id, author_id FROM recipes WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()

    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)

    recipe_id = row["id"]
    await db.execute("DELETE FROM recipes_fts WHERE recipe_id = ?", (recipe_id,))
    await db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
    await db.commit()
    delete_recipe_dir(slug)

    return _htmx_redirect("/")


# ---------------------------------------------------------------------------
# Image upload / delete (page-level, returns partial HTML)
# ---------------------------------------------------------------------------


@router.post("/recipes/{slug}/images", response_class=HTMLResponse)
async def upload_image_page(
    request: Request,
    slug: str = Depends(_valid_slug),
    file: UploadFile = File(...),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _htmx_redirect("/login")
    async with db.execute(
        "SELECT author_id FROM recipes WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()

    if not row or row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)

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
    images = list_images(slug)

    return templates.TemplateResponse(
        "partials/image_list.html",
        {"request": request, "slug": slug, "images": images},
    )


@router.delete("/recipes/{slug}/images/{filename}", response_class=HTMLResponse)
async def delete_image_page(
    request: Request,
    slug: str = Depends(_valid_slug),
    filename: str = ...,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return _htmx_redirect("/login")
    async with db.execute(
        "SELECT author_id FROM recipes WHERE slug = ?", (slug,)
    ) as cur:
        row = await cur.fetchone()

    if not row or row["author_id"] != current_user["id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN)

    delete_image(slug, filename)
    images = list_images(slug)

    return templates.TemplateResponse(
        "partials/image_list.html",
        {"request": request, "slug": slug, "images": images},
    )


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------


@router.post("/partials/preview", response_class=HTMLResponse)
async def markdown_preview(
    content: str = Form(default=""),
    slug: str = Form(default="__preview__"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
) -> HTMLResponse:
    if not current_user:
        return HTMLResponse("", status_code=status.HTTP_401_UNAUTHORIZED)
    html = _render_markdown(content, slug)
    return HTMLResponse(_sanitize_html(html))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _fetch_recipes(
    db: aiosqlite.Connection,
    q: Optional[str] = None,
    tag: Optional[str] = None,
    page: int = 1,
    page_size: int = 24,
) -> list[RecipeOut]:
    offset = (page - 1) * page_size
    rows = []

    if q:
        escaped = re.sub(r'["\*\(\)\:\^~]', " ", q).strip()
        if escaped:
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

    result = []
    for row in rows:
        tags = await _get_recipe_tags(db, row["id"])
        result.append(_row_to_out(row, tags))
    return result


async def _fetch_all_tags(db: aiosqlite.Connection) -> list[str]:
    async with db.execute("SELECT name FROM tags ORDER BY name") as cur:
        return [row["name"] async for row in cur]
