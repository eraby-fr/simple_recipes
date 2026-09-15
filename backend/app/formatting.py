from __future__ import annotations

from datetime import datetime
from typing import Union

_MONTHS_FR = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def format_date_fr(value: Union[datetime, str]) -> str:
    """Format a datetime as ``15 septembre 2026``."""
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return f"{value.day} {_MONTHS_FR[value.month - 1]} {value.year}"
