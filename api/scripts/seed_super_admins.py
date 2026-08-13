"""Super adminlarni seed qiladi — `SUPER_ADMIN_TELEGRAM_IDS` bo'yicha.

Migratsiya `0002_seed` ham shuni qiladi, lekin u bir marta ishlaydi. Ro'yxat keyin
o'zgarsa (yangi super admin qo'shildi) shu skript qayta yugurtiriladi.

    python scripts/seed_super_admins.py

Idempotent: mavjud yozuvga tegmaydi. Egasi roli (`DIRECT_URL`) bilan ulanadi —
RLS chetlab o'tiladi, chunki bu ma'muriy amal.
"""

import asyncio
import sys

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core.config import settings


async def main() -> int:
    ids = settings.super_admin_ids
    if not ids:
        print("SUPER_ADMIN_TELEGRAM_IDS bo‘sh — hech narsa qilinmadi")
        return 1

    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))

    async with engine.begin() as conn:
        for telegram_id in ids:
            await conn.execute(
                text(
                    "INSERT INTO users (telegram_id, first_name) VALUES (:tid, 'Super admin')"
                    " ON CONFLICT (telegram_id) DO NOTHING"
                ),
                {"tid": telegram_id},
            )
            await conn.execute(
                text(
                    "INSERT INTO super_admins (user_id, note)"
                    " SELECT id, 'seed' FROM users WHERE telegram_id = :tid"
                    " ON CONFLICT (user_id) DO NOTHING"
                ),
                {"tid": telegram_id},
            )

        rows = (
            await conn.execute(
                text(
                    "SELECT u.telegram_id, u.id, u.first_name FROM super_admins s"
                    " JOIN users u ON u.id = s.user_id ORDER BY u.id"
                )
            )
        ).all()

    await engine.dispose()

    print(f"Super adminlar ({len(rows)}):")
    for telegram_id, user_id, name in rows:
        print(f"  telegram_id={telegram_id}  user_id={user_id}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
