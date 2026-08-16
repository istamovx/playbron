"""Adversarial auditda topilgan teshiklar qayta ochilmasligi uchun testlar.

Har biri aniq hujum stsenariysini takrorlaydi.
"""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from conftest import null_actor_refs, purge_audit_actor, rls_bypass
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from playbron.core.config import settings

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL kerak",
)


async def ctx(
    conn: AsyncConnection, *, user_id: int = 0, org_id: int = 0, club_id: int = 0
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


def owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture
async def world() -> AsyncIterator[dict[str, int]]:
    """Bitta tashkilot, ikkita klub; STAFF faqat birinchisida."""
    engine = owner_engine()
    ids: dict[str, int] = {}

    async with engine.begin() as conn:
        # `world` butun grafni nol'dan quradi — hali tabiiy aktor yo'q,
        # shuning uchun `rls_bypass` (`conftest.py`).
        async with rls_bypass(
            conn, "users", "organizations", "clubs", "memberships", "club_payment_credentials"
        ):
            ids["owner"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', 'hard.owner', 'active', 'Owner')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET first_name='Owner' RETURNING id"
                )
            )
            ids["staff"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', 'hard.staff', 'active', 'Staff')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET first_name='Staff' RETURNING id"
                )
            )
            ids["outsider"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', 'hard.outsider', 'active', 'Outsider')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET first_name='Outsider' RETURNING id"
                )
            )
            ids["org"] = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                    " VALUES (:u, 'Hard Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            for key, name in (("club_a", "Club A"), ("club_b", "Club B")):
                ids[key] = await conn.scalar(
                    text(
                        "INSERT INTO clubs (org_id, name, status) VALUES (:o, :n, 'active')"
                        " RETURNING id"
                    ),
                    {"o": ids["org"], "n": name},
                )
            await conn.execute(
                text(
                    "INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'STAFF')"
                    " ON CONFLICT DO NOTHING"
                ),
                {"u": ids["staff"], "c": ids["club_a"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"
                    " ON CONFLICT DO NOTHING"
                ),
                {"u": ids["owner"], "c": ids["club_a"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO club_payment_credentials (club_id, provider, credentials)"
                    " VALUES (:c, 'payme', '{\"merchant_id\": \"secret-a\"}')"
                    " ON CONFLICT (club_id) DO NOTHING"
                ),
                {"c": ids["club_a"]},
            )

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users"):
            # Login shabloni bo'yicha o'chiriladi, aniq id bo'yicha emas:
            # login `ON CONFLICT DO UPDATE` bilan qatorni doim qayta
            # ishlatadi, ya'ni bitta muvaffaqiyatsiz tozalash keyingi HAR
            # BIR yurishni `organizations_owner_user_id_fkey` bilan abadiy
            # blokidan qoldirardi — o'z-o'zini davolaydigan tozalash kerak.
            stale_ids = [
                row[0]
                for row in (
                    await conn.execute(
                        text(
                            "SELECT id FROM users WHERE kind = 'staff' AND login LIKE 'hard.%'"
                        )
                    )
                ).all()
            ]
            await purge_audit_actor(conn, *stale_ids)
            await conn.execute(
                text(
                    "DELETE FROM organizations WHERE owner_user_id IN"
                    " (SELECT id FROM users WHERE kind = 'staff' AND login LIKE 'hard.%')"
                )
            )
            await null_actor_refs(conn, *stale_ids)
            await conn.execute(
                text("DELETE FROM users WHERE kind = 'staff' AND login LIKE 'hard.%'")
            )
    await engine.dispose()


@skip_no_db
async def test_staff_cannot_touch_sibling_club(world: dict[str, int]) -> None:
    """A klubdagi STAFF B klubni o'zgartira yoki o'chira olmaydi."""
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await ctx(conn, user_id=world["staff"], org_id=world["org"], club_id=world["club_a"])

        updated = await conn.execute(
            text("UPDATE clubs SET name = 'Bosib olindi' WHERE id = :i RETURNING id"),
            {"i": world["club_b"]},
        )
        assert updated.first() is None, "qo‘shni klub o‘zgartirilmasligi kerak"

        # `clubs`da umuman DELETE policy'si YO'Q, VA `playbron_app` roli
        # DELETE uchun GRANT ham olmagan (`[[playbron-grant-vs-rls-blind-spot]]`
        # — GRANT va RLS ikki alohida qatlam) — ya'ni bu HECH KIM uchun
        # (STAFF uchun ham) "0 qator" bilan emas, to'g'ridan-to'g'ri
        # "permission denied" bilan bloklanadi.
        with pytest.raises(DBAPIError, match="permission denied"):
            await conn.execute(
                text("DELETE FROM clubs WHERE id = :i RETURNING id"), {"i": world["club_b"]}
            )

    await engine.dispose()


@skip_no_db
async def test_staff_cannot_edit_own_club_either(world: dict[str, int]) -> None:
    """STAFF o'z klubini ham tahrirlay olmaydi — bu OWNER/ADMIN ishi."""
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await ctx(conn, user_id=world["staff"], org_id=world["org"], club_id=world["club_a"])
        updated = await conn.execute(
            text("UPDATE clubs SET name = 'Yangi nom' WHERE id = :i RETURNING id"),
            {"i": world["club_a"]},
        )
        assert updated.first() is None

    await engine.dispose()


@skip_no_db
async def test_owner_can_edit_own_club(world: dict[str, int]) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await ctx(conn, user_id=world["owner"], org_id=world["org"], club_id=world["club_a"])
        updated = await conn.execute(
            text("UPDATE clubs SET about = 'Yangilandi' WHERE id = :i RETURNING id"),
            {"i": world["club_a"]},
        )
        assert updated.first() is not None, "OWNER o‘z klubini tahrirlay olishi kerak"

    await engine.dispose()


@skip_no_db
async def test_payment_credentials_hidden_from_anonymous(world: dict[str, int]) -> None:
    """Merchant kalitlari anonim kontekstda ko'rinmaydi."""
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await ctx(conn)  # app.user_id = 0
        rows = (
            (await conn.execute(text("SELECT club_id FROM club_payment_credentials")))
            .scalars()
            .all()
        )
        assert rows == [], "to‘lov kalitlari anonim o‘qilmasligi kerak"

        # Faol klub o'qiladi, lekin unda kalit ustuni umuman yo'q
        cols = (
            (
                await conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns"
                        " WHERE table_name = 'clubs'"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert "payment_credentials" not in cols

    await engine.dispose()


@skip_no_db
async def test_staff_cannot_read_payment_credentials(world: dict[str, int]) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await ctx(conn, user_id=world["staff"], org_id=world["org"], club_id=world["club_a"])
        rows = (
            (await conn.execute(text("SELECT club_id FROM club_payment_credentials")))
            .scalars()
            .all()
        )
        assert rows == [], "STAFF merchant kalitini ko‘rmasligi kerak"

    await engine.dispose()


@skip_no_db
async def test_self_activated_organization_is_blocked(world: dict[str, int]) -> None:
    """Oddiy foydalanuvchi o'ziga tasdiqlangan tashkilot va tarif yasay olmaydi."""
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await ctx(conn, user_id=world["outsider"])

        with pytest.raises(DBAPIError):
            await conn.execute(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                    " VALUES (:u, 'Bepul', 'active', 'infinite')"
                ),
                {"u": world["outsider"]},
            )

    # `pending` va tarifsiz bo'lsa ruxsat
    async with engine.begin() as conn:
        await ctx(conn, user_id=world["outsider"])
        created = await conn.scalar(
            text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:u, 'Ariza', 'pending') RETURNING id"
            ),
            {"u": world["outsider"]},
        )
        assert created is not None

    async with owner_engine().begin() as conn:
        async with rls_bypass(conn, "organizations"):
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": created})

    await engine.dispose()


@skip_no_db
async def test_audit_log_is_append_only(world: dict[str, int]) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await ctx(conn, user_id=world["owner"], org_id=world["org"])
        await conn.execute(
            text(
                "INSERT INTO audit_log (actor_user_id, org_id, action)"
                " VALUES (:u, :o, 'test.action')"
            ),
            {"u": world["owner"], "o": world["org"]},
        )

    # `audit_log`da FAQAT INSERT/SELECT policy'si bor VA `playbron_app` roli
    # UPDATE/DELETE uchun GRANT ham olmagan (`[[playbron-grant-vs-rls-blind-spot]]`)
    # — ya'ni ikkalasi ham "0 qator" bilan emas, to'g'ridan-to'g'ri
    # "permission denied" bilan bloklanadi ("append-only" aynan shu ma'noda).
    async with engine.begin() as conn:
        await ctx(conn, user_id=world["owner"], org_id=world["org"])
        with pytest.raises(DBAPIError, match="permission denied"):
            await conn.execute(
                text("DELETE FROM audit_log WHERE org_id = :o RETURNING id"), {"o": world["org"]}
            )

    async with engine.begin() as conn:
        await ctx(conn, user_id=world["owner"], org_id=world["org"])
        with pytest.raises(DBAPIError, match="permission denied"):
            await conn.execute(
                text("UPDATE audit_log SET action = 'yashirildi' WHERE org_id = :o RETURNING id"),
                {"o": world["org"]},
            )

    async with owner_engine().begin() as conn:
        async with rls_bypass(conn, "audit_log"):
            await conn.execute(text("DELETE FROM audit_log WHERE org_id = :o"), {"o": world["org"]})

    await engine.dispose()


@skip_no_db
async def test_every_table_has_rls() -> None:
    """Yangi jadval RLS'siz qo'shilib qolmasin — fail-open himoyasi."""
    exempt = {"alembic_version", "plans"}

    engine = owner_engine()
    async with engine.begin() as conn:
        rows = (
            (
                await conn.execute(
                    text(
                        "SELECT relname FROM pg_class c"
                        " JOIN pg_namespace n ON n.oid = c.relnamespace"
                        " WHERE n.nspname = 'public' AND c.relkind = 'r'"
                        "   AND NOT (c.relrowsecurity AND c.relforcerowsecurity)"
                    )
                )
            )
            .scalars()
            .all()
        )
    await engine.dispose()

    unprotected = set(rows) - exempt
    assert not unprotected, f"RLS yoqilmagan jadvallar: {sorted(unprotected)}"
