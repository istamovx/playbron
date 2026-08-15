"""`SUPER_ADMIN_PASSWORD` orqali super admin paroli — loyiha egasining so'rovi.

**Standart yo'l EMAS.** Standart — `scripts/set_staff_password.py`: parol
stdin'dan so'raladi, hech qayerda saqlanmaydi, faqat bitta terminal
seansida yashaydi (`docs/05-auth-redesign.md` §5.6). Bu modul o'sha
qoidadan ATAYLAB chetlanadi: parol Render dashboard'ining "Environment"
bo'limida DOIMIY o'tiradi — u yerni ochgan har kim ko'radi, konteyner
inspeksiyasida ham chiqadi.

Chetlanish sababi: Render bepul rejasida Shell yo'q, bazaga tashqi ulanish
esa har safar IP allowlist bilan qo'lda o'ynashni talab qiladi. Loyiha
egasi bu xavfni bilib turib, aynan shu variantni tanladi (2026-08-15).

Xavfni KAMAYTIRUVCHI uchta qaror shu faylda:

1. **Faqat o'zgarganda yoziladi.** Har start'da (deploy, restart) parol
   qayta xeshlanib, sessiyalar bekor qilinib qolsa, super admin har
   qayta ishga tushishda "chiqarib yuborilardi" — bu ham xavfsizlik emas,
   ta'qib. Kiritilgan parol saqlangan xesh bilan solishtiriladi, farq
   bo'lmasa hech narsa qilinmaydi.
2. **Xato butun ilovani to'xtatmaydi.** Bitta noto'g'ri sozlangan
   o'zgaruvchi butun API'ni ishga tushirilmay qoldirmasligi kerak —
   xato faqat log'ga yoziladi, `lifespan` davom etadi.
3. **Ishlatilganda OGOHLANTIRADI.** Har safar parol haqiqatan
   o'rnatilganda/yangilanganda WARNING darajasida yoziladi — Render
   log'ida ko'rinib turadi, o'zgaruvchi "unutilib qolgani" jimgina
   yashirinmaydi.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from playbron.core.config import settings
from playbron.core.errors import AppError
from playbron.core.passwords import hash_password, validate, verify_password

log = logging.getLogger("playbron.super_admin_bootstrap")

ROLE = "SUPER_ADMIN"


async def sync_super_admin_password() -> None:
    """`SUPER_ADMIN_PASSWORD` bo'sh bo'lsa — darhol qaytadi, funksiya o'chiq.

    Xato chiqarmaydi: chaqiruvchi (`main.py::lifespan`) buni bitta
    noto'g'ri sozlangan o'zgaruvchi butun API'ni to'xtatib qo'ymasligi
    uchun ataylab `try/except` bilan o'raydi — bu yerda esa faqat
    LOG darajasidagi qaror qabul qilinadi.
    """
    password = settings.super_admin_password.get_secret_value()
    if not password:
        return

    logins = settings.super_admin_login_list
    if not logins:
        log.warning(
            "SUPER_ADMIN_PASSWORD berilgan, lekin SUPER_ADMIN_LOGINS bo'sh — hech kimga qo'yilmaydi"
        )
        return

    # `DIRECT_URL` — baza egasi roli: `staff_credentials` ilova rolidan
    # butunlay yopiq va faqat shu yo'ldan yoziladi.
    engine = create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))
    try:
        for login in logins:
            await _sync_one(engine, login, password)
    finally:
        await engine.dispose()


async def _sync_one(engine: AsyncEngine, login: str, password: str) -> None:
    async with engine.begin() as conn:
        # `DIRECT_URL` — baza EGASI, lekin BYPASSRLS'siz muhitda (Render)
        # `FORCE ROW LEVEL SECURITY` egaga ham tegishli: GUC'siz oddiy
        # `SELECT ... FROM users` policy'lar hech qanday qatorni ochmay,
        # jimgina 0 qator qaytaradi — «login topilmadi» degan YOLG'ON xato
        # (`[[render-free-tier-no-bypassrls]]`). `app.login` `users_login_probe`
        # policy'sini (`0007`) qanoatlantiradi — bu policy `staff_credentials`
        # bilan JOIN talab qilmaydi, ya'ni hali paroli yo'q yangi hisob uchun
        # ham ishlaydi.
        await conn.execute(text("SELECT set_config('app.login', :login, true)"), {"login": login})
        row = await conn.execute(
            text("SELECT id, status FROM users WHERE kind = 'staff' AND lower(login) = :login"),
            {"login": login},
        )
        found = row.first()
        if found is None:
            log.warning("SUPER_ADMIN_PASSWORD: login topilmadi — %r", login)
            return
        user_id, _status = found

        # `refresh_tokens_scope` policy'si `user_id = app_user_id()` talab
        # qiladi — pastdagi bekor qilish shu GUC'siz jimgina 0 qatorga
        # tegardi (eski sessiya "bekor qilindi" deb o'ylab, aslida qolardi).
        await conn.execute(
            text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)}
        )

        try:
            validated = validate(password, role=ROLE, login=login)
        except AppError as exc:
            log.error("SUPER_ADMIN_PASSWORD rad etildi (%s): %s", login, exc.message)
            return

        existing_hash = await conn.scalar(
            text("SELECT password_hash FROM staff_credentials WHERE user_id = :uid"),
            {"uid": user_id},
        )
        # O'zgarmagan bo'lsa hech narsa qilinmaydi: qayta yozish sessiyalarni
        # bekor qiladi, ya'ni har start'da super admin chiqarib yuborilardi.
        if existing_hash is not None and await verify_password(existing_hash, validated):
            return

        await conn.execute(
            text(
                "INSERT INTO staff_credentials"
                " (user_id, password_hash, password_set_at, must_change)"
                " VALUES (:uid, :hash, now(), false)"
                " ON CONFLICT (user_id) DO UPDATE"
                " SET password_hash = excluded.password_hash,"
                "     password_set_at = now(),"
                "     must_change = false,"
                "     failed_count = 0"
            ),
            {"uid": user_id, "hash": await hash_password(validated)},
        )
        await conn.execute(
            text(
                "UPDATE refresh_tokens SET revoked_at = now()"
                " WHERE user_id = :uid AND revoked_at IS NULL"
            ),
            {"uid": user_id},
        )

    log.warning("SUPER_ADMIN_PASSWORD orqali parol yangilandi: login=%r", login)
