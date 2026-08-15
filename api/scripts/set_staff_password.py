"""Xodim yoki super adminga parol qo'yish.

Manba: `docs/05-auth-redesign.md` §5.6.

Parol **stdin'dan** so'raladi — `argv` yoki env'dan EMAS: birinchisi shell
tarixiga va `ps` chiqishiga tushadi, ikkinchisi konteyner inspeksiyasida
ko'rinadi.

Ulanish `DIRECT_URL` bilan (baza egasi roli): `staff_credentials` ilova roliga
butunlay yopiq va faqat `SECURITY DEFINER` funksiyalari orqali ochiladi, bu
skript esa ulardan tashqarida ishlaydi.

BYPASSRLS'siz muhitda (Render bepul rejasi — `[[render-free-tier-no-bypassrls]]`)
baza EGASI ham `FORCE ROW LEVEL SECURITY` ostida qoladi: `users` va
`refresh_tokens`'dan o'qish/yozish uchun tegishli `app.*` GUC'lar shu skript
ICHIDA o'rnatiladi (pastga qarang). Lokal superuser Postgres buni yashiradi —
shuning uchun bu skript ham Render shaklidagi (superuser emas, BYPASSRLS yo'q)
bazada sinaladi.

    python scripts/set_staff_password.py sa.xurshid
    python scripts/set_staff_password.py sa.xurshid --role SUPER_ADMIN
    python scripts/set_staff_password.py sa.xurshid --must-change
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from playbron.core.config import settings  # noqa: E402
from playbron.core.errors import AppError  # noqa: E402
from playbron.core.passwords import hash_password, validate  # noqa: E402


def _read_password(prompt: str) -> str:
    """Terminalda — ko'rinmas kiritish, quvurda — oddiy satr.

    Windows'da `getpass` konsoldan TO'G'RIDAN-TO'G'RI o'qiydi va quvurni
    umuman ko'rmaydi — shuning uchun avtomatlashtirishda u qotib qolardi.
    Ikkala holatda ham parol `argv` va env'ga tushmaydi, ya'ni shell tarixida
    va `ps` chiqishida qolmaydi.
    """
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    return sys.stdin.readline().rstrip("\n")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Xodimga parol qo'yish")
    parser.add_argument("login", help="Xodim login'i (`users.login`)")
    parser.add_argument(
        "--role",
        default="STAFF",
        choices=["STAFF", "ADMIN", "OWNER", "SUPER_ADMIN"],
        help="Minimal parol uzunligi shu roldan kelib chiqadi",
    )
    parser.add_argument(
        "--must-change",
        action="store_true",
        help="Birinchi kirishda parolni majburan almashtirish",
    )
    args = parser.parse_args()

    login = args.login.strip().casefold()

    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    try:
        async with engine.begin() as conn:
            # `DIRECT_URL` — baza EGASI, lekin BYPASSRLS'siz muhitda (Render
            # bepul rejasi) `FORCE ROW LEVEL SECURITY` egaga ham tegishli:
            # GUC'siz oddiy `SELECT` policy'lar hech qanday qator ochmay,
            # jimgina 0 qaytaradi — «xodim topilmadi» degan YOLG'ON xato
            # (superuser bo'lgan lokal Postgres buni yashiradi). `app.login`
            # `users_login_probe` (`0007`) policy'sini qanoatlantiradi — bu
            # policy `staff_credentials` bilan JOIN talab qilmaydi, ya'ni
            # hali paroli yo'q yangi hisob uchun ham ishlaydi.
            await conn.execute(
                text("SELECT set_config('app.login', :login, true)"), {"login": login}
            )
            row = (
                await conn.execute(
                    text(
                        "SELECT id, status FROM users"
                        " WHERE kind = 'staff' AND lower(login) = :login"
                    ),
                    {"login": login},
                )
            ).first()

            if row is None:
                print(f"Xodim topilmadi: {login!r}", file=sys.stderr)
                return 1

            user_id, status = row
            print(f"Xodim: id={user_id}, status={status}, rol={args.role}")

            # `refresh_tokens_scope` policy'si `user_id = app_user_id()`
            # talab qiladi — pastdagi bekor qilish shu GUC'siz jimgina 0
            # qatorga tegardi (eski sessiya "bekor qilindi" deb chiqib,
            # aslida ishlab qolardi).
            await conn.execute(
                text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)}
            )

            password = _read_password("Yangi parol: ")
            if sys.stdin.isatty():
                if password != _read_password("Takrorlang: "):
                    print("Parollar mos kelmadi", file=sys.stderr)
                    return 1

            try:
                validated = validate(password, role=args.role, login=login)
            except AppError as exc:
                print(f"Rad etildi: {exc.message}", file=sys.stderr)
                return 1

            await conn.execute(
                text(
                    "INSERT INTO staff_credentials"
                    " (user_id, password_hash, password_set_at, must_change)"
                    " VALUES (:uid, :hash, now(), :must)"
                    " ON CONFLICT (user_id) DO UPDATE"
                    " SET password_hash = excluded.password_hash,"
                    "     password_set_at = now(),"
                    "     must_change = excluded.must_change,"
                    "     failed_count = 0"
                ),
                {"uid": user_id, "hash": await hash_password(validated), "must": args.must_change},
            )

            # Parol o'zgarganda eski sessiyalar yashab qolmasin
            revoked = await conn.execute(
                text(
                    "UPDATE refresh_tokens SET revoked_at = now()"
                    " WHERE user_id = :uid AND revoked_at IS NULL"
                ),
                {"uid": user_id},
            )

        print(f"Parol qo'yildi. Bekor qilingan sessiya: {revoked.rowcount}")
        if args.must_change:
            print("Birinchi kirishda parol almashtirilishi talab qilinadi.")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
