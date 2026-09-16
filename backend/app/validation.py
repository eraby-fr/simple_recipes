"""Shared input limits and normalisation for recipe and account fields.

Both the JSON API (Pydantic schemas) and the HTML form handlers go through
these helpers, so the two entry points cannot drift apart.
"""

from __future__ import annotations

import re

MAX_TITLE_LENGTH = 200
MAX_SUMMARY_LENGTH = 1_000
MAX_META_LENGTH = 100  # prep_time, cook_time, wait_time, servings
MAX_CONTENT_LENGTH = 256 * 1024  # 256 KiB of Markdown
MAX_TAG_LENGTH = 40
MAX_TAGS = 20
MIN_USERNAME_LENGTH = 3
MAX_USERNAME_LENGTH = 32
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# Tags end up in HTML attributes, so they are restricted to word characters
# (accented letters included), spaces and hyphens. Quotes, angle brackets and
# parentheses are dropped rather than escaped.
_TAG_ALLOWED_RE = re.compile(r"[^\w \-]", re.UNICODE)
_TAG_SPACE_RE = re.compile(r"\s+", re.UNICODE)


def normalize_tag(value: str) -> str:
    """Lowercase a tag and strip every character unsafe for an HTML attribute."""
    cleaned = _TAG_ALLOWED_RE.sub("", value)
    cleaned = _TAG_SPACE_RE.sub(" ", cleaned).strip().lower()
    return cleaned[:MAX_TAG_LENGTH]


def normalize_tags(values: list[str]) -> list[str]:
    """Normalise a tag list, dropping empties and duplicates, order preserved."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        tag = normalize_tag(value)
        if tag and tag not in seen:
            seen.add(tag)
            result.append(tag)
        if len(result) >= MAX_TAGS:
            break
    return result


def parse_tags(raw: str) -> list[str]:
    """Normalise the comma-separated tag field posted by the HTML forms."""
    return normalize_tags(raw.split(","))


def clamp(value: str, max_length: int) -> str:
    return value.strip()[:max_length]
