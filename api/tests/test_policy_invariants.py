"""RLS policy invariantlari — matn darajasida.

Nega funksional emas, statik. Lokal bazada `playbron_platform` BYPASSRLS
huquqiga ega, shuning uchun `SECURITY DEFINER` funksiyalar ichida policy
umuman baholanmaydi va bu yerdagi xatolar KO'RINMAYDI. Render'da esa
`ALTER ROLE ... BYPASSRLS` superuser talab qiladi va o'tmaydi — natijada
o'sha kod boshqacha ishlaydi.

`0007` gacha aynan shu farq prod'da uchta bloklovchi xatoga olib kelgan edi
(`memberships` rekursiyasi, kirish topa olmasligi, xodim qo'sha olmaslik).
Quyidagi tekshiruvlar policy MATNIGA qaraydi, ya'ni har qanday muhitda
bir xil natija beradi.
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from playbron.core.config import settings

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL kerak",
)


@pytest_asyncio.fixture
async def engine():  # type: ignore[no-untyped-def]
    made: AsyncEngine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    yield made
    await made.dispose()


@skip_no_db
async def test_memberships_policies_do_not_call_app_club_role(engine: AsyncEngine) -> None:
    """Rekursiya invarianti.

    `memberships` ustidagi policy `app_club_role()` ni chaqirsa, funksiya
    o'sha jadvaldan o'qiydi va policy qayta ishga tushadi —
    `stack depth limit exceeded`. Rol GUC'dan olinishi shart.
    """
    async with engine.connect() as conn:
        guilty = (
            (
                await conn.execute(
                    text(
                        "SELECT p.polname FROM pg_policy p"
                        " JOIN pg_class c ON c.oid = p.polrelid"
                        " WHERE c.relname = 'memberships'"
                        " AND (COALESCE(pg_get_expr(p.polqual, p.polrelid), '')"
                        "        LIKE '%app_club_role(%'"
                        "   OR COALESCE(pg_get_expr(p.polwithcheck, p.polrelid), '')"
                        "        LIKE '%app_club_role(%')"
                    )
                )
            )
            .scalars()
            .all()
        )

    assert guilty == [], f"rekursiv policy: {guilty}"


@skip_no_db
async def test_login_lookup_has_its_own_scope(engine: AsyncEngine) -> None:
    """Kirish paytida `app.user_id` = 0 — `users_self` hech narsa ochmaydi.

    Bu policy bo'lmasa `auth_lookup_staff` bo'sh qaytaradi va har bir xodim
    kirishi 401 bilan tugaydi (BYPASSRLS yo'q muhitda).
    """
    async with engine.connect() as conn:
        expr = await conn.scalar(
            text(
                "SELECT pg_get_expr(polqual, polrelid) FROM pg_policy"
                " WHERE polname = 'users_login_probe'"
            )
        )

    assert expr is not None, "users_login_probe policy'si yo'q"
    assert "app_login_claim" in expr


@skip_no_db
async def test_staff_provisioning_policy_opens_no_reads(engine: AsyncEngine) -> None:
    """Xodim yaratish policy'si FAQAT yozish uchun.

    `USING` bo'lsa, klub egasi butun `users` jadvalini — boshqa klublarning
    xodimlarini ham — o'qiy olardi. Shu sababli `auth_create_staff` da
    `RETURNING` emas, `currval` ishlatiladi.
    """
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT polcmd, pg_get_expr(polqual, polrelid),"
                    "       pg_get_expr(polwithcheck, polrelid)"
                    " FROM pg_policy WHERE polname = 'users_staff_provision'"
                )
            )
        ).first()

    assert row is not None, "users_staff_provision policy'si yo'q"
    command, using_expr, check_expr = row
    # `polcmd` — Postgres `"char"` turi; drayver uni bayt qilib qaytaradi
    if isinstance(command, bytes):
        command = command.decode()
    assert command == "a", "policy faqat INSERT uchun bo'lishi kerak"
    assert using_expr is None, "USING ochilsa o'qish teshigi paydo bo'ladi"
    assert check_expr is not None and "app_club_role_claim" in check_expr


@skip_no_db
async def test_create_staff_does_not_use_returning(engine: AsyncEngine) -> None:
    """`INSERT ... RETURNING` SELECT policy'sini ham talab qiladi.

    Yangi xodim qatorini ochadigan SELECT policy'si ATAYLAB yo'q, shuning
    uchun id `currval` orqali olinadi. Kimdir `RETURNING` ni qaytarsa,
    xodim qo'shish BYPASSRLS yo'q muhitda jimgina ishlamay qoladi.
    """
    async with engine.connect() as conn:
        body = await conn.scalar(
            text("SELECT prosrc FROM pg_proc WHERE proname = 'auth_create_staff'")
        )

    assert body is not None
    assert "RETURNING id INTO" not in body
    assert "currval" in body
