from __future__ import annotations

from typing import Optional

import aiosqlite

ROLE_ADMIN = "admin"
ROLE_USER = "user"

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"


class UsernameTaken(Exception):
    pass


def login_block_reason(status: Optional[str]) -> Optional[str]:
    if status == STATUS_PENDING:
        return "Votre compte est en attente d'approbation"
    if status == STATUS_REJECTED:
        return "Votre compte a été refusé"
    if status != STATUS_APPROVED:
        return "Votre compte n'est pas autorisé à se connecter"
    return None


async def create_registered_user(
    db: aiosqlite.Connection,
    username: str,
    hashed_password: str,
) -> dict:
    """Insert a user from the HTML register page.

    The first account becomes admin and is approved. Later accounts are
    regular users waiting for an admin to approve them.
    """
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ) as cur:
            if await cur.fetchone():
                raise UsernameTaken()
        async with db.execute("SELECT COUNT(*) AS n FROM users") as cur:
            is_first = (await cur.fetchone())["n"] == 0
        role = ROLE_ADMIN if is_first else ROLE_USER
        account_status = STATUS_APPROVED if is_first else STATUS_PENDING
        async with db.execute(
            """
            INSERT INTO users (username, hashed_password, role, status)
            VALUES (?, ?, ?, ?)
            RETURNING id, username, role, status
            """,
            (username, hashed_password, role, account_status),
        ) as cur:
            row = await cur.fetchone()
        await db.commit()
        return dict(row)
    except Exception:
        await db.rollback()
        raise


async def list_users(db: aiosqlite.Connection) -> list[dict]:
    async with db.execute(
        """
        SELECT id, username, role, status, created_at
        FROM users
        ORDER BY
            CASE status
                WHEN 'pending' THEN 0
                WHEN 'approved' THEN 1
                ELSE 2
            END,
            created_at ASC
        """
    ) as cur:
        return [dict(row) async for row in cur]


async def get_user_by_id(db: aiosqlite.Connection, user_id: int) -> Optional[dict]:
    async with db.execute(
        "SELECT id, username, role, status FROM users WHERE id = ?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()
    return dict(row) if row else None


async def set_user_status(
    db: aiosqlite.Connection,
    user_id: int,
    account_status: str,
) -> None:
    await db.execute(
        "UPDATE users SET status = ? WHERE id = ?",
        (account_status, user_id),
    )
    await db.commit()


async def set_user_role(
    db: aiosqlite.Connection,
    user_id: int,
    role: str,
) -> None:
    await db.execute(
        "UPDATE users SET role = ? WHERE id = ?",
        (role, user_id),
    )
    await db.commit()
