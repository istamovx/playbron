"""Testlar uchun umumiy yordamchilar.

`rls_bypass()` — fixture'lar ichida `FORCE ROW LEVEL SECURITY` ni vaqtincha
olib turish uchun.

Bu fayldagi ko'p fixture butun ob'ekt grafini (foydalanuvchi + tashkilot +
klub + a'zolik + ...) NOL'DAN quradi — hali hech qanday tabiiy AKTOR yo'q,
ya'ni qanoatlantiriladigan `app.*` GUC yo'q (masalan `super_admins`da
umuman INSERT policy'si yo'q). `_owner_engine()`/`owner_engine()` ulanishi
Render'da (BYPASSRLS'siz — `[[render-free-tier-no-bypassrls]]`) ham baza
EGASI, lekin `FORCE ROW LEVEL SECURITY` egaga ham tegishli: GUC'siz yozish
yoki o'qish jimgina 0 qatorga tegadi — «xodim topilmadi» kabi yolg'on
xatolarga olib keladi.

Yechim `api/migrations/versions/0005_two_worlds_auth.py`dagi `_force_rls()`
bilan bir xil: kerakli jadvallar uchun FORCE vaqtincha OLIB TURILADI va
DARHOL qaytariladi. `ENABLE`ga TEGILMAYDI — ilova roli (`playbron_app`)
uchun izolyatsiya bir lahzaga ham ochilmaydi, faqat shu bitta
tranzaksiyada jadval EGASI erkin qoladi.

Diqqat: FK `CASCADE` (masalan `organizations` o'chirilganda unga bog'liq
`clubs`/`memberships`) RLS'ni har doim chetlab o'tadi — referensial
yaxlitlik RLS'ga qaramaydi (Postgres invarianti). Shuning uchun bu yerga
FAQAT ushbu tranzaksiyada TO'G'RIDAN-TO'G'RI SQL bilan tegilgan jadvallar
beriladi, kaskad orqali o'chadigan/o'zgaradigan jadvallar emas.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@asynccontextmanager
async def rls_bypass(conn: AsyncConnection, *tables: str) -> AsyncIterator[None]:
    for table in tables:
        await conn.execute(text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
    try:
        yield
    finally:
        for table in tables:
            await conn.execute(text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))


async def purge_audit_actor(conn: AsyncConnection, *user_ids: int | None) -> None:
    """Fixture teardown'da `DELETE FROM users` dan OLDIN chaqiriladi.

    `audit_log_actor_user_id_fkey` — `NO ACTION` (`club_id`/`org_id`dan farqli,
    ular `SET NULL`). Sinov davomida audit yozadigan amal (masalan
    `club_updated`, `station_created`, `staff_created`) chaqirilgan bo'lsa,
    o'sha aktyorni o'chirish FK buzilishi bilan yiqiladi — sinov muvaffaqiyatli
    o'tgan bo'lsa ham, faqat TEARDOWN'da.
    """
    ids = [i for i in user_ids if i is not None]
    if not ids:
        return
    async with rls_bypass(conn, "audit_log"):
        await conn.execute(
            text("DELETE FROM audit_log WHERE actor_user_id = ANY(:ids)"), {"ids": ids}
        )


# `pg_constraint`da `confdeltype = 'a'` (NO ACTION) bo'lgan, `users.id`ga
# ishora qiluvchi ustunlar — `audit_log_actor_user_id_fkey` (yuqorida) dan
# tashqari HAMMASI. NULLABLE ustun — qatorni saqlab, faqat havolani uzamiz
# (`UPDATE ... SET col = NULL`); NOT NULL ustun — qatorning o'zi ORQASIGA
# tegishli emas (masalan boshqa test/mijoz yozgan bo'lishi mumkin), shuning
# uchun FAQAT shu aktyor yozgan qatorlar o'chiriladi (`DELETE ... WHERE`).
_NULLABLE_ACTOR_COLUMNS = (
    ("bookings", "created_by"),
    ("bookings", "confirmed_by"),
    ("bookings", "cancelled_by"),
    ("bookings", "closed_by"),
    ("bookings", "customer_id"),
    ("shifts", "closed_by"),
    ("memberships", "invited_by"),
)
_NOT_NULL_ACTOR_COLUMNS = (
    ("shift_cash_movements", "created_by"),
    ("shifts", "staff_id"),
    ("expenses", "created_by"),
    ("orders", "created_by"),
    ("platform_payments", "entered_by"),
    ("staff_invites", "created_by"),
    ("organizations", "owner_user_id"),
)


async def null_actor_refs(conn: AsyncConnection, *user_ids: int | None) -> None:
    """Fixture teardown'da `DELETE FROM users` dan OLDIN chaqiriladi (odatda
    `purge_audit_actor`dan KEYIN, so'nggi qadam sifatida — pastga qarang).

    `audit_log`dan tashqari yana bir talay ustun `users.id`ga `NO ACTION`
    bilan ishora qiladi: `bookings.created_by/confirmed_by/cancelled_by/
    closed_by/customer_id`, `orders.created_by`, `expenses.created_by`,
    `shifts.staff_id/closed_by`, `shift_cash_movements.created_by`,
    `platform_payments.entered_by`, `memberships.invited_by`,
    `staff_invites.created_by`, `organizations.owner_user_id`.

    Ko'p fixture o'zi yaratgan qatorlarni (bron, buyurtma, ...) `club_id`/
    `org_id` bo'yicha ANIQ o'chiradi — lekin `login`/`ON CONFLICT DO UPDATE`
    naqshi bilan qayta ishlatiladigan test-aktyorlar orasida OLDINGI, uzilib
    qolgan (masalan CTRL+C bilan to'xtatilgan) sinov yurishidan qolgan
    "yetim" qatorlar bo'lishi mumkin — ular boshqa `club_id`ga tegishli
    bo'lgani uchun fixture'ning o'zi ko'rmaydi. Bu funksiya AYNAN o'sha
    qoldiqlarni aktyor `user_id` bo'yicha (jadval/klub qaramasdan) tozalaydi.

    Chaqiruv TARTIBI muhim: fixture'ning o'z (club_id/org_id bo'yicha aniq)
    tozalashidan KEYIN va `DELETE FROM users`dan OLDIN, ya'ni shu ikkalasi
    orasidagi so'nggi qadam sifatida chaqirilsin — aks holda bu yerdagi ichki
    `rls_bypass()` NO FORCE/FORCE tsikli fixture'ning o'zidagi tashqi
    `rls_bypass()` bilan bir xil jadvalni qamragan bo'lsa, keyingi statement
    uchun FORCE'ni muddatidan oldin qaytarib qo'yishi mumkin.
    """
    ids = [i for i in user_ids if i is not None]
    if not ids:
        return
    tables = tuple(
        dict.fromkeys(
            table for table, _ in (*_NULLABLE_ACTOR_COLUMNS, *_NOT_NULL_ACTOR_COLUMNS)
        )
    )
    async with rls_bypass(conn, *tables):
        for table, column in _NULLABLE_ACTOR_COLUMNS:
            # S608: `table`/`column` — yuqoridagi FIKS ichki tuple'dan, foydalanuvchi
            # kirishi emas; qiymat o'zi bind parametr (`:ids`) bilan o'tadi.
            await conn.execute(
                text(f"UPDATE {table} SET {column} = NULL WHERE {column} = ANY(:ids)"),  # noqa: S608
                {"ids": ids},
            )
        # `shift_cash_movements` — `shifts`dan OLDIN: aks holda `shifts`
        # o'chirilganda kaskad bilan ketgan qatorlar uchun `created_by`
        # boshqa aktyorga tegishli bo'lsa ham baribir ANY(:ids) shart emas
        # bo'lib qoladi (kaskad RLS'ni chetlab o'tadi — zarari yo'q, lekin
        # tartib mantiqiy: avval o'ziga tegishlisini, keyin egasi bo'yicha).
        for table, column in _NOT_NULL_ACTOR_COLUMNS:
            await conn.execute(
                text(f"DELETE FROM {table} WHERE {column} = ANY(:ids)"),  # noqa: S608
                {"ids": ids},
            )
