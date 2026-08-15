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
