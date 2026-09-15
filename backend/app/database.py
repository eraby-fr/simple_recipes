from typing import AsyncGenerator

import aiosqlite

from app.config import DB_PATH

_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    author_id INTEGER NOT NULL REFERENCES users(id),
    cover_image TEXT NOT NULL DEFAULT '',
    prep_time TEXT NOT NULL DEFAULT '',
    cook_time TEXT NOT NULL DEFAULT '',
    wait_time TEXT NOT NULL DEFAULT '',
    servings TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS recipe_tags (
    recipe_id TEXT NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (recipe_id, tag_id)
);

CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
    recipe_id UNINDEXED,
    title,
    body,
    tags,
    tokenize='unicode61'
);
"""


async def _migrate_user_roles(db: aiosqlite.Connection) -> None:
    """Add role/status on existing DBs and promote the oldest user to admin."""
    async with db.execute("PRAGMA table_info(users)") as cur:
        columns = {row[1] async for row in cur}

    if "role" not in columns:
        await db.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
        )
    if "status" not in columns:
        await db.execute(
            "ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'approved'"
        )

    async with db.execute(
        "SELECT COUNT(*) AS n FROM users WHERE role = 'admin'"
    ) as cur:
        admin_count = (await cur.fetchone())["n"]
    if admin_count == 0:
        await db.execute(
            """
            UPDATE users
            SET role = 'admin', status = 'approved'
            WHERE id = (SELECT MIN(id) FROM users)
            """
        )


_RECIPE_META_COLUMNS = (
    ("cover_image", "TEXT NOT NULL DEFAULT ''"),
    ("prep_time", "TEXT NOT NULL DEFAULT ''"),
    ("cook_time", "TEXT NOT NULL DEFAULT ''"),
    ("wait_time", "TEXT NOT NULL DEFAULT ''"),
    ("servings", "TEXT NOT NULL DEFAULT ''"),
)


async def _migrate_recipe_meta(db: aiosqlite.Connection) -> None:
    """Add cover and timing columns on databases created before this schema."""
    async with db.execute("PRAGMA table_info(recipes)") as cur:
        columns = {row[1] async for row in cur}
    for name, spec in _RECIPE_META_COLUMNS:
        if name not in columns:
            await db.execute(f"ALTER TABLE recipes ADD COLUMN {name} {spec}")


async def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript(_SCHEMA)
        await _migrate_user_roles(db)
        await _migrate_recipe_meta(db)
        await db.commit()


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        yield db
