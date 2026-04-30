from __future__ import annotations

import re
import shutil
import unicodedata
from pathlib import Path
from typing import Optional

from app.config import RECIPES_DIR


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,127}$")


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


def _safe_image_path(images_dir: Path, filename: str) -> Path:
    """Resolve the image path and assert it stays within images_dir."""
    safe_name = re.sub(r"[^\w.\-]", "_", Path(filename).name)
    dest = (images_dir / safe_name).resolve()
    try:
        dest.relative_to(images_dir.resolve())
    except ValueError:
        raise ValueError(f"Nom de fichier invalide : {filename}")
    return dest


def save_image(slug: str, filename: str, data: bytes) -> str:
    images_dir = get_images_dir(slug)
    images_dir.mkdir(parents=True, exist_ok=True)
    dest = _safe_image_path(images_dir, filename)
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
    exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"}
    return [
        f.name
        for f in sorted(images_dir.iterdir())
        if f.is_file() and f.suffix.lower() in exts
    ]


def get_cover_image_url(slug: str) -> Optional[str]:
    images = list_images(slug)
    if images:
        return f"/uploads/{slug}/images/{images[0]}"
    return None


def fix_image_urls(html: str, slug: str) -> str:
    return re.sub(
        r'src="images/([^"]+)"',
        f'src="/uploads/{slug}/images/\\1"',
        html,
    )
