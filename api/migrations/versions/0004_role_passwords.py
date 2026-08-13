"""Rol parollarini almashtirish — xavfsizlik auditi topilmasi.

`0001_core` env bo'lmaganda rollarni sukut "app"/"platform" parollari bilan
yaratardi. Render'da `APP_DB_PASSWORD`/`PLATFORM_DB_PASSWORD` berilmagan edi —
jonli bazadagi LOGIN rollari zaif parol bilan qolgan. Endi `render.yaml`
`generateValue: true` bilan kuchli qiymat beradi, bu migratsiya esa mavjud
rollarning parolini o'sha qiymatga almashtiradi.

Env bo'sh bo'lsa (lokal dev) — rol tegilmaydi, `.env.example` dagi ulanish
satrlari ishlayveradi.

Revision ID: 0004_role_passwords
Revises: 0003_rls_hardening
"""

import os

import sqlalchemy as sa
from alembic import op

revision = "0004_role_passwords"
down_revision = "0003_rls_hardening"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"


def _safe_password(value: str, name: str) -> str:
    """Parolni DDL ichiga qo'yishdan oldin tekshiradi.

    `ALTER ROLE` da parolni bind qilib bo'lmaydi (DDL parametr qabul qilmaydi),
    shuning uchun belgilar to'plami cheklanadi — qo'shtirnoq yoki nuqtali vergul
    kirsa migratsiya to'xtaydi.
    """
    if not value or len(value) > 128:
        raise ValueError(f"{name} bo‘sh yoki juda uzun")
    allowed = set(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.~!@#%^&*+=:"
    )
    if not set(value) <= allowed:
        raise ValueError(f"{name} da ruxsat etilmagan belgi bor")
    return value


def upgrade() -> None:
    for role, env_name in ((APP_ROLE, "APP_DB_PASSWORD"), (PLATFORM_ROLE, "PLATFORM_DB_PASSWORD")):
        raw = os.environ.get(env_name, "")
        if not raw:
            continue
        password = _safe_password(raw, env_name)

        # DDL bind parametr qabul qilmaydi; kirish `_safe_password` bilan cheklangan.
        # Rol yo'q bo'lsa (boshqariladigan hosting `CREATEROLE` bermagan) yoki
        # huquq yetmasa migratsiya to'xtamaydi — 0001 dagi kelishuv bilan bir xil.
        op.execute(
            sa.text(
                f"""
                DO $$
                BEGIN
                    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                        ALTER ROLE {role} PASSWORD '{password}';
                    ELSE
                        RAISE NOTICE '{role} yo''q — parol almashtirilmadi';
                    END IF;
                EXCEPTION WHEN insufficient_privilege THEN
                    RAISE NOTICE '{role} paroli almashtirilmadi (huquq yo''q) — DBA qo''lda almashtiradi';
                END $$;
                """
            )
        )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
