from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Optional
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.auth import get_current_user
from app.config import RECIPES_DIR, settings
from app.database import init_db
from app.routes import api_auth, api_recipes, pages
from app.storage import IMAGE_MIME_BY_EXTENSION, validate_slug

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])

# Methods that must not change state, and therefore need no CSRF check.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    RECIPES_DIR.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="Simple Recipes",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.enable_docs else None,
    redoc_url="/api/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.allowed_hosts_list != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts_list
    )


def _request_origin(request: Request) -> Optional[str]:
    """The origin the browser should have sent, derived from the Host header."""
    host = request.headers.get("host")
    if not host:
        return None
    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    return f"{scheme.split(',')[0].strip()}://{host}"


def _origin_allowed(origin: str, request: Request) -> bool:
    expected = _request_origin(request)
    if expected is None:
        return False
    sent = urlsplit(origin)
    want = urlsplit(expected)
    # Compare host *and* port: SameSite cookies ignore the port, so a different
    # service on the same hostname would otherwise be able to forge requests.
    return (sent.hostname, sent.port) == (want.hostname, want.port)


@app.middleware("http")
async def csrf_protect(request: Request, call_next: object) -> Response:
    """Reject cross-origin state-changing requests.

    The session cookie is SameSite=Lax, which browsers already enforce, but it
    ignores the port and is a single point of failure. Checking Origin (with
    Sec-Fetch-Site as a fallback) closes both gaps. Requests with neither header
    are not browser-initiated and are left to the regular authentication.
    """
    if request.method not in _SAFE_METHODS:
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site")
        if origin is not None and origin != "null":
            if not _origin_allowed(origin, request):
                return JSONResponse(
                    {"detail": "Requête cross-origin refusée"}, status_code=403
                )
        elif fetch_site is not None and fetch_site not in ("same-origin", "none"):
            return JSONResponse(
                {"detail": "Requête cross-origin refusée"}, status_code=403
            )
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next: object) -> Response:
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        # Pico.css and the browser's own UA styles still need inline styles.
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none';"
    )
    if settings.cookie_secure:
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    path = request.url.path
    if path.startswith("/static/"):
        pass  # Versionless public assets, cached by the browser as usual.
    elif path.startswith("/uploads/"):
        # Private images: revalidate every time, never store in a shared cache.
        response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
    else:
        # Authenticated HTML must not survive in a cache after logout.
        response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict:
    return {"status": "ok"}


@app.get("/uploads/{slug}/images/{filename}")
async def serve_upload(
    slug: str,
    filename: str,
    _: dict = Depends(get_current_user),
) -> FileResponse:
    try:
        validate_slug(slug)
    except ValueError:
        raise HTTPException(404)
    suffix = Path(filename).suffix.lower()
    mime = IMAGE_MIME_BY_EXTENSION.get(suffix)
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
