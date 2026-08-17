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

**Hisobning o'zi ham shu yerda yaratiladi.** `scripts/seed_super_admins.py`
faqat `SUPER_ADMIN_TELEGRAM_IDS` (Telegram orqali kirish) uchun — login
asosidagi hisobni u yaratmaydi. Render bepul rejasida Shell yo'q, ya'ni
skriptni qo'lda ham yugurtirib bo'lmaydi. Avvalgi variant `users` qatori
allaqachon mavjud deb faraz qilardi va faqat parolni yangilardi — agar
`SUPER_ADMIN_LOGINS`dagi login hali umuman mavjud bo'lmasa, funksiya
jimgina hech narsa qilmay qaytar edi (faqat log'da WARNING, foydalanuvchi
buni ko'rmaydi) va super admin HECH QACHON birinchi marta kira olmasdi.
Shuning uchun topilmasa — `users` (kind='staff') va `super_admins` qatori
shu yerning o'zida yaratiladi (`ALTER TABLE ... NO FORCE ROW LEVEL
SECURITY`, `seed_super_admins.py`dagi bilan bir xil texnika).
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

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
            user_id = await _create_super_admin_account(conn, login)
            log.warning("SUPER_ADMIN_PASSWORD: yangi super admin hisobi yaratildi — %r", login)
        else:
            user_id, _status = found
            await _ensure_super_admin_membership(conn, user_id)

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


async def _create_super_admin_account(conn: AsyncConnection, login: str) -> int:
    """`users` (kind='staff') va `super_admins` qatorini nol'dan yaratadi.

    `seed_super_admins.py`dagi bilan bir xil texnika: ikkala jadval ham
    `FORCE ROW LEVEL SECURITY` ostida, hozircha esa hali tabiiy aktor yo'q
    (yangi hisob), shuning uchun vaqtincha `NO FORCE` qilinadi, keyin
    darhol qaytariladi — bitta tranzaksiya ichida (`_sync_one`ning o'zi
    `engine.begin()`).
    """
    await conn.execute(text("ALTER TABLE users NO FORCE ROW LEVEL SECURITY"))
    await conn.execute(text("ALTER TABLE super_admins NO FORCE ROW LEVEL SECURITY"))
    try:
        user_id = await conn.scalar(
            text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', :login, 'active', 'Super admin')"
                " RETURNING id"
            ),
            {"login": login},
        )
        await conn.execute(
            text(
                "INSERT INTO super_admins (user_id, note)"
                " VALUES (:uid, 'SUPER_ADMIN_PASSWORD bootstrap')"
                " ON CONFLICT (user_id) DO NOTHING"
            ),
            {"uid": user_id},
        )
    finally:
        await conn.execute(text("ALTER TABLE users FORCE ROW LEVEL SECURITY"))
        await conn.execute(text("ALTER TABLE super_admins FORCE ROW LEVEL SECURITY"))
    return int(user_id)


async def _ensure_super_admin_membership(conn: AsyncConnection, user_id: int) -> None:
    """Login mavjud, lekin `super_admins`da bo'lmasligi mumkin — masalan avval
    oddiy xodim sifatida yaratilgan hisob keyin `SUPER_ADMIN_LOGINS`ga
    qo'shilsa. Bu holatda ham parolni yangilashning o'zi yetarli emas —
    rol berilmasa kirish `SUPER_ADMIN` sifatida emas, oddiy xodim sifatida
    bo'ladi (`auth/router.py::_top_role`).
    """
    already = await conn.scalar(
        text("SELECT 1 FROM super_admins WHERE user_id = :uid"), {"uid": user_id}
    )
    if already:
        return
    await conn.execute(text("ALTER TABLE super_admins NO FORCE ROW LEVEL SECURITY"))
    try:
        await conn.execute(
            text(
                "INSERT INTO super_admins (user_id, note)"
                " VALUES (:uid, 'SUPER_ADMIN_PASSWORD bootstrap')"
                " ON CONFLICT (user_id) DO NOTHING"
            ),
            {"uid": user_id},
        )
    finally:
        await conn.execute(text("ALTER TABLE super_admins FORCE ROW LEVEL SECURITY"))
