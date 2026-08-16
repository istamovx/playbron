"""RLS izolyatsiyasi — Faza 1 ning asosiy tugash mezoni.

Ikki tenant bir xil so'rovni yuborsa, har biri **faqat o'zinikini** ko'rishi kerak.
Bu testlar haqiqiy PostgreSQL talab qiladi (`docker compose up -d postgres`),
shuning uchun DB bo'lmasa o'tkazib yuboriladi.
"""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from conftest import rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from playbron.core.config import settings

pytestmark = pytest.mark.asyncio

DB_AVAILABLE = os.environ.get("RUN_DB_TESTS") == "1"
skip_no_db = pytest.mark.skipif(
    not DB_AVAILABLE,
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL kerak",
)


async def _as_context(
    conn: AsyncConnection,
    *,
    user_id: int = 0,
    org_id: int = 0,
    club_id: int = 0,
) -> None:
    await conn.execute(
        text(
            "SELECT set_config('app.user_id', :u, true),"
            "       set_config('app.org_id', :o, true),"
            "       set_config('app.club_id', :c, true),"
            "       set_config('app.telegram_id', '0', true),"
            "       set_config('app.refresh_hash', '', true)"
        ),
        {"u": str(user_id), "o": str(org_id), "c": str(club_id)},
    )


@pytest_asyncio.fixture
async def seeded() -> AsyncIterator[dict[str, int]]:
    """Ikki tashkilot, ikki klub, ikki egasi — egasi roli bilan yaratiladi."""
    owner = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    ids: dict[str, int] = {}

    async with owner.begin() as conn:
        # `seeded` butun grafni nol'dan quradi — hali tabiiy aktor yo'q,
        # shuning uchun `rls_bypass` (`conftest.py`).
        async with rls_bypass(conn, "users", "organizations", "clubs", "memberships"):
            # A'zolik oladigan foydalanuvchi XODIM bo'lishi shart: kompozit FK
            # mijoz qatoriga `memberships` yozishga yo'l qo'ymaydi.
            for key, login in (("user_a", "rls.usera"), ("user_b", "rls.userb")):
                ids[key] = await conn.scalar(
                    text(
                        "INSERT INTO users (kind, login, status, first_name)"
                        " VALUES ('staff', :login, 'active', :name)"
                        " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                        " DO UPDATE SET first_name = EXCLUDED.first_name"
                        " RETURNING id"
                    ),
                    {"login": login, "name": f"Test {key}"},
                )

            for key, owner_key in (("org_a", "user_a"), ("org_b", "user_b")):
                ids[key] = await conn.scalar(
                    text(
                        "INSERT INTO organizations (owner_user_id, name, status)"
                        " VALUES (:owner, :name, 'active') RETURNING id"
                    ),
                    {"owner": ids[owner_key], "name": f"Org {key}"},
                )

            for key, org_key in (("club_a", "org_a"), ("club_b", "org_b")):
                ids[key] = await conn.scalar(
                    text(
                        "INSERT INTO clubs (org_id, name, status)"
                        " VALUES (:org, :name, 'draft') RETURNING id"
                    ),
                    {"org": ids[org_key], "name": f"Club {key}"},
                )

            await conn.execute(
                text(
                    "INSERT INTO memberships (user_id, club_id, role)"
                    " VALUES (:u, :c, 'OWNER') ON CONFLICT DO NOTHING"
                ),
                {"u": ids["user_a"], "c": ids["club_a"]},
            )

    yield ids

    async with owner.begin() as conn:
        async with rls_bypass(conn, "organizations", "users"):
            # Login shabloni bo'yicha o'chiriladi, aniq id bo'yicha emas:
            # login `ON CONFLICT DO UPDATE` bilan qatorni doim qayta
            # ishlatadi, ya'ni bitta muvaffaqiyatsiz tozalash keyingi HAR
            # BIR yurishni `organizations_owner_user_id_fkey` bilan abadiy
            # blokidan qoldirardi — o'z-o'zini davolaydigan tozalash kerak.
            await conn.execute(
                text(
                    "DELETE FROM organizations WHERE owner_user_id IN"
                    " (SELECT id FROM users WHERE kind = 'staff' AND login LIKE 'rls.%')"
                )
            )
            await conn.execute(
                text("DELETE FROM users WHERE kind = 'staff' AND login LIKE 'rls.%'")
            )
    await owner.dispose()


@skip_no_db
async def test_club_write_is_tenant_isolated(seeded: dict[str, int]) -> None:
    """A tashkiloti B ning klubini ko'rmaydi va yoza olmaydi."""
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await _as_context(conn, user_id=seeded["user_a"], org_id=seeded["org_a"])

        visible = (
            (await conn.execute(text("SELECT id FROM clubs WHERE status = 'draft'")))
            .scalars()
            .all()
        )

        assert seeded["club_a"] in visible, "o'z klubi ko'rinishi kerak"
        assert seeded["club_b"] not in visible, "begona klub ko'rinmasligi kerak"

        updated = await conn.execute(
            text("UPDATE clubs SET name = 'Bosib olindi' WHERE id = :id RETURNING id"),
            {"id": seeded["club_b"]},
        )
        assert updated.first() is None, "begona klubga yozish RLS bilan bloklanishi kerak"

    await engine.dispose()


@skip_no_db
async def test_user_sees_only_self(seeded: dict[str, int]) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await _as_context(conn, user_id=seeded["user_a"])
        rows = (await conn.execute(text("SELECT id FROM users"))).scalars().all()

        assert rows == [seeded["user_a"]]

    await engine.dispose()


@skip_no_db
async def test_active_club_is_publicly_readable(seeded: dict[str, int]) -> None:
    """Mijoz klublar ro'yxatini ko'radi — faol klub hamma uchun ochiq."""
    owner = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    async with owner.begin() as conn:
        async with rls_bypass(conn, "clubs"):
            await conn.execute(
                text("UPDATE clubs SET status = 'active' WHERE id = :id"),
                {"id": seeded["club_b"]},
            )
    await owner.dispose()

    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        # Autentifikatsiyasiz kontekst
        await _as_context(conn)
        rows = (await conn.execute(text("SELECT id FROM clubs"))).scalars().all()

        assert seeded["club_b"] in rows
        assert seeded["club_a"] not in rows, "draft klub ochiq bo'lmasligi kerak"

    await engine.dispose()


@skip_no_db
async def test_membership_visible_to_member_and_club(seeded: dict[str, int]) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await _as_context(conn, user_id=seeded["user_b"])
        rows = (await conn.execute(text("SELECT id FROM memberships"))).scalars().all()
        assert rows == [], "begona a'zolik ko'rinmasligi kerak"

    async with engine.begin() as conn:
        await _as_context(conn, user_id=seeded["user_a"])
        rows = (await conn.execute(text("SELECT club_id FROM memberships"))).scalars().all()
        assert rows == [seeded["club_a"]]

    await engine.dispose()
