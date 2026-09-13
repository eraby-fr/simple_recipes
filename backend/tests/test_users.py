import asyncio

import aiosqlite

from app.auth import hash_password
from app.database import _SCHEMA, _migrate_user_roles
from app.users import (
    ROLE_ADMIN,
    ROLE_USER,
    STATUS_APPROVED,
    STATUS_PENDING,
    create_registered_user,
    login_block_reason,
)


async def _fresh_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(_SCHEMA)
    await _migrate_user_roles(db)
    await db.commit()
    return db


class TestCreateRegisteredUser:
    def test_first_user_is_admin_and_approved(self):
        async def run():
            db = await _fresh_db()
            user = await create_registered_user(
                db, "alice", hash_password("password123")
            )
            assert user["role"] == ROLE_ADMIN
            assert user["status"] == STATUS_APPROVED
            await db.close()

        asyncio.run(run())

    def test_later_users_are_pending(self):
        async def run():
            db = await _fresh_db()
            await create_registered_user(db, "alice", hash_password("password123"))
            bob = await create_registered_user(
                db, "bob", hash_password("password123")
            )
            assert bob["role"] == ROLE_USER
            assert bob["status"] == STATUS_PENDING
            await db.close()

        asyncio.run(run())


class TestLoginBlockReason:
    def test_pending(self):
        assert "attente" in login_block_reason(STATUS_PENDING)

    def test_approved_allows_login(self):
        assert login_block_reason(STATUS_APPROVED) is None


class TestMigrateExistingUsers:
    def test_oldest_user_becomes_admin_others_stay_approved(self):
        async def run():
            db = await aiosqlite.connect(":memory:")
            db.row_factory = aiosqlite.Row
            await db.executescript(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    hashed_password TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                INSERT INTO users (username, hashed_password) VALUES ('Stun', 'x');
                INSERT INTO users (username, hashed_password) VALUES ('stun', 'y');
                """
            )
            await _migrate_user_roles(db)
            await db.commit()
            async with db.execute(
                "SELECT username, role, status FROM users ORDER BY id"
            ) as cur:
                rows = [dict(r) async for r in cur]
            assert rows[0]["username"] == "Stun"
            assert rows[0]["role"] == ROLE_ADMIN
            assert rows[0]["status"] == STATUS_APPROVED
            assert rows[1]["username"] == "stun"
            assert rows[1]["role"] == ROLE_USER
            assert rows[1]["status"] == STATUS_APPROVED
            await db.close()

        asyncio.run(run())
