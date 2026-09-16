from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Optional

from app.config import RECIPES_DIR


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,127}$")

# Canonical extension per image type, and the extensions accepted for each of
# them. Nothing else is ever written to an images/ directory.
IMAGE_MIME_BY_EXTENSION: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".avif": "image/avif",
}
IMAGE_EXTENSIONS: frozenset[str] = frozenset(IMAGE_MIME_BY_EXTENSION)
_CANONICAL_EXTENSION: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/avif": ".avif",
}


def sniff_image_mime(data: bytes) -> Optional[str]:
    """Return the image MIME type implied by the file signature, or None.

    The uploaded Content-Type header is attacker-controlled, so the bytes are
    what decides whether a file is stored at all.
    """
    if len(data) < 12:
        return None
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    if data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis"):
        return "image/avif"
    return None


def image_filename_for(filename: str, mime: str) -> str:
    """Sanitised name whose extension matches the detected image type."""
    safe_name = safe_image_filename(filename)
    canonical = _CANONICAL_EXTENSION[mime]
    stem, _, suffix = safe_name.rpartition(".")
    if not stem:
        stem, suffix = safe_name, ""
    # Compare case-insensitively but keep the name the user uploaded, so it
    # still matches safeImageFilename() in editor.js.
    lowered = f".{suffix.lower()}" if suffix else ""
    if lowered in IMAGE_EXTENSIONS and IMAGE_MIME_BY_EXTENSION[lowered] == mime:
        return f"{stem}.{suffix}"
    return f"{stem or 'image'}{canonical}"


def validate_slug(slug: str) -> str:
    """Raise ValueError if slug contains path-traversal or invalid characters."""
    if not _SLUG_RE.match(slug):
        raise ValueError(f"Slug invalide : {slug!r}")
    return slug


def get_recipe_dir(slug: str) -> Path:
    return RECIPES_DIR / slug


def get_recipe_md_path(slug: str) -> Path:
    return get_recipe_dir(slug) / "recipe.md"


def get_images_dir(slug: str) -> Path:
    return get_recipe_dir(slug) / "images"


def slugify(title: str) -> str:
    slug = unicodedata.normalize("NFKD", title.lower().strip())
    slug = slug.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-{2,}", "-", slug)
    slug = slug.strip("-")
    return slug or "recette"


def write_recipe_content(slug: str, content: str) -> None:
    recipe_dir = get_recipe_dir(slug)
    recipe_dir.mkdir(parents=True, exist_ok=True)
    get_images_dir(slug).mkdir(parents=True, exist_ok=True)
    get_recipe_md_path(slug).write_text(content, encoding="utf-8")


def read_recipe_content(slug: str) -> str:
    path = get_recipe_md_path(slug)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def delete_recipe_dir(slug: str) -> None:
    recipe_dir = get_recipe_dir(slug)
    if recipe_dir.exists():
        shutil.rmtree(recipe_dir)


def safe_image_filename(filename: str) -> str:
    """Sanitize an upload filename (keep in sync with editor.js)."""
    return re.sub(r"[^\w.\-]", "_", Path(filename).name)


def _safe_image_path(images_dir: Path, filename: str) -> Path:
    """Resolve the image path and assert it stays within images_dir."""
    safe_name = safe_image_filename(filename)
    dest = (images_dir / safe_name).resolve()
    try:
        dest.relative_to(images_dir.resolve())
    except ValueError:
        raise ValueError(f"Nom de fichier invalide : {filename}")
    return dest


def save_image(slug: str, filename: str, data: bytes) -> str:
    """Store an uploaded image, refusing anything that is not really an image."""
    mime = sniff_image_mime(data)
    if mime is None:
        raise ValueError("Le fichier n'est pas une image reconnue")
    images_dir = get_images_dir(slug)
    images_dir.mkdir(parents=True, exist_ok=True)
    dest = _safe_image_path(images_dir, image_filename_for(filename, mime))
    dest.write_bytes(data)
    return dest.name


def delete_image(slug: str, filename: str) -> bool:
    images_dir = get_images_dir(slug)
    try:
        path = _safe_image_path(images_dir, filename)
    except ValueError:
        return False
    if path.exists() and path.is_file():
        path.unlink()
        return True
    return False


def list_images(slug: str) -> list[str]:
    images_dir = get_images_dir(slug)
    if not images_dir.exists():
        return []
    return [
        f.name
        for f in sorted(images_dir.iterdir())
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]


def get_cover_image_url(slug: str, preferred: str = "") -> Optional[str]:
    images = list_images(slug)
    if not images:
        return None
    chosen = preferred if preferred in images else images[0]
    return f"/uploads/{slug}/images/{chosen}"


def gallery_filenames(
    slug: str, content: str, cover_image: str = ""
) -> list[str]:
    """Images that are neither the cover nor already referenced in markdown."""
    skip: set[str] = set()
    cover = (cover_image or "").strip()
    if cover:
        skip.add(cover)
    for filename in list_images(slug):
        if f"images/{filename}" in content:
            skip.add(filename)
    return [filename for filename in list_images(slug) if filename not in skip]


def fix_image_urls(html: str, slug: str) -> str:
    return re.sub(
        r'src="images/([^"]+)"',
        f'src="/uploads/{slug}/images/\\1"',
        html,
    )
