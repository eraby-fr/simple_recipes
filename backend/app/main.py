from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import RECIPES_DIR, settings
from app.database import init_db
from app.routes import api_auth, api_recipes, pages
from app.storage import validate_slug

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

_IMAGE_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Simple Recipes",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.middleware("http")
async def security_headers(request: Request, call_next: object) -> Response:
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )
    return response

@app.get("/uploads/{slug}/images/{filename}")
async def serve_upload(slug: str, filename: str) -> FileResponse:
    try:
        validate_slug(slug)
    except ValueError:
        raise HTTPException(404)
    suffix = Path(filename).suffix.lower()
    mime = _IMAGE_MIME.get(suffix)
    if mime is None:
        raise HTTPException(404)
    path = RECIPES_DIR / slug / "images" / Path(filename).name
    if not path.is_file():
        raise HTTPException(404)
    return FileResponse(path, media_type=mime)


app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(pages.router)
app.include_router(api_auth.router)
app.include_router(api_recipes.router)
