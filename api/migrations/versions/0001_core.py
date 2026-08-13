"""Faza 1: identity, tenancy, sessiya, tarif + RLS.

Qoida: tenant-scoped jadval **shu migratsiyada** RLS bilan birga yaratiladi.
Alembic RLS va EXCLUDE konstreyntlarini ko'rmaydi — ular qo'lda yoziladi.

Revision ID: 0001_core
Revises:
"""

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_core"
down_revision = None
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"


def _safe_password(value: str, name: str) -> str:
    """Parolni DDL ichiga qo'yishdan oldin tekshiradi.

    `CREATE ROLE` da parolni bind qilib bo'lmaydi (DDL parametr qabul qilmaydi),
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


def _create_roles() -> None:
    """Rollarni yaratadi. Prod'da DBA yaratgan bo'lsa — o'tkazib yuboriladi."""
    app_password = _safe_password(os.environ.get("APP_DB_PASSWORD", "app"), "APP_DB_PASSWORD")
    platform_password = _safe_password(
        os.environ.get("PLATFORM_DB_PASSWORD", "platform"), "PLATFORM_DB_PASSWORD"
    )

    # DDL bind parametr qabul qilmaydi; kirish `_safe_password` bilan cheklangan
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
                    CREATE ROLE {APP_ROLE} LOGIN PASSWORD '{app_password}';
                END IF;
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                    CREATE ROLE {PLATFORM_ROLE} LOGIN PASSWORD '{platform_password}';
                END IF;
            END $$;
            """
        )
    )

    # BYPASSRLS superuser huquqini talab qiladi. Yo'q bo'lsa migratsiya to'xtamaydi —
    # DBA qo'lda beradi, aks holda super admin paneli ishlamaydi.
    op.execute(
        sa.text(
            f"""
            DO $$
            BEGIN
                ALTER ROLE {PLATFORM_ROLE} BYPASSRLS;
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'BYPASSRLS berilmadi — DBA qo''lda berishi kerak';
            END $$;
            """
        )
    )


def _context_functions() -> None:
    """`SET LOCAL app.*` ni o'qiydigan yordamchilar — policy'lar shulardan foydalanadi."""
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_user_id() RETURNS bigint
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(NULLIF(current_setting('app.user_id', true), ''), '0')::bigint $$;

            CREATE OR REPLACE FUNCTION app_org_id() RETURNS bigint
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(NULLIF(current_setting('app.org_id', true), ''), '0')::bigint $$;

            CREATE OR REPLACE FUNCTION app_club_id() RETURNS bigint
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(NULLIF(current_setting('app.club_id', true), ''), '0')::bigint $$;

            CREATE OR REPLACE FUNCTION app_telegram_id() RETURNS bigint
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(NULLIF(current_setting('app.telegram_id', true), ''), '0')::bigint $$;

            CREATE OR REPLACE FUNCTION app_refresh_hash() RETURNS text
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(current_setting('app.refresh_hash', true), '') $$;
            """
        )
    )


def _tables() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(128), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(128)),
        sa.Column("language_code", sa.String(8)),
        sa.Column("photo_url", sa.Text),
        sa.Column("phone", sa.String(20)),
        sa.Column("phone_verified_at", sa.DateTime(timezone=True)),
        sa.Column("tg_blocked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("telegram_id", name="users_telegram_id_uk"),
    )

    op.create_table(
        "super_admins",
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("note", sa.Text),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "plans",
        sa.Column("code", sa.String(32), primary_key=True),
        sa.Column("title", sa.String(64), nullable=False),
        sa.Column("price_month", sa.BigInteger, nullable=False),
        sa.Column("price_year", sa.BigInteger, nullable=False),
        sa.Column("limits", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("features", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("sort", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_public", sa.Boolean, nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "organizations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("owner_user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("plans.code")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("organizations_owner_ix", "organizations", ["owner_user_id"])
    op.create_index("organizations_status_ix", "organizations", ["status"])

    op.create_table(
        "clubs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "org_id",
            sa.BigInteger,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("address", sa.Text, nullable=False, server_default=""),
        sa.Column("phone", sa.String(20)),
        sa.Column("cover_url", sa.Text),
        sa.Column("about", sa.Text, nullable=False, server_default=""),
        sa.Column("opens_at_min", sa.Integer, nullable=False, server_default="600"),
        sa.Column("closes_at_min", sa.Integer, nullable=False, server_default="1560"),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Tashkent"),
        sa.Column("lat", sa.Numeric(9, 6)),
        sa.Column("lng", sa.Numeric(9, 6)),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("payment_credentials", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("clubs_org_ix", "clubs", ["org_id"])
    op.create_index("clubs_status_ix", "clubs", ["status"])

    op.create_table(
        "memberships",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "club_id",
            sa.BigInteger,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("invited_by", sa.BigInteger, sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "club_id", name="memberships_user_club_uk"),
        sa.CheckConstraint("role IN ('OWNER','ADMIN','STAFF')", name="memberships_role_ck"),
    )
    op.create_index("memberships_user_ix", "memberships", ["user_id"])
    op.create_index("memberships_club_role_ix", "memberships", ["club_id", "role"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("replaced_by", sa.String(64)),
        sa.Column("user_agent", sa.Text),
        sa.Column("ip", sa.String(45)),
    )
    op.create_index("refresh_tokens_user_ix", "refresh_tokens", ["user_id", "revoked_at"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.BigInteger, sa.ForeignKey("users.id")),
        sa.Column("org_id", sa.BigInteger, sa.ForeignKey("organizations.id")),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target", sa.String(128)),
        sa.Column("before", postgresql.JSONB),
        sa.Column("after", postgresql.JSONB),
        sa.Column("ip", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("audit_log_action_ix", "audit_log", ["action"])
    op.create_index("audit_log_org_at_ix", "audit_log", ["org_id", "at"])


def _rls() -> None:
    """Har bir jadval uchun izolyatsiya. `FORCE` — jadval egasiga ham qo'llanadi."""
    op.execute(
        sa.text(
            """
            -- ── users ────────────────────────────────────────────────────────
            -- Foydalanuvchi faqat o'zini ko'radi. Kirish paytida hali `app.user_id`
            -- yo'q, shuning uchun imzosi tekshirilgan `app.telegram_id` ochiladi.
            ALTER TABLE users ENABLE ROW LEVEL SECURITY;
            ALTER TABLE users FORCE ROW LEVEL SECURITY;
            CREATE POLICY users_self ON users
                USING (id = app_user_id()
                       OR (app_telegram_id() <> 0 AND telegram_id = app_telegram_id()))
                WITH CHECK (id = app_user_id()
                       OR (app_telegram_id() <> 0 AND telegram_id = app_telegram_id()));

            -- ── super_admins ─────────────────────────────────────────────────
            -- O'zining super admin ekanini tekshira oladi, ro'yxatni ko'ra olmaydi.
            ALTER TABLE super_admins ENABLE ROW LEVEL SECURITY;
            ALTER TABLE super_admins FORCE ROW LEVEL SECURITY;
            CREATE POLICY super_admins_self ON super_admins
                FOR SELECT USING (user_id = app_user_id());

            -- ── organizations ────────────────────────────────────────────────
            ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
            ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
            CREATE POLICY organizations_tenant ON organizations
                USING (owner_user_id = app_user_id() OR id = app_org_id())
                WITH CHECK (owner_user_id = app_user_id() OR id = app_org_id());

            -- ── clubs ────────────────────────────────────────────────────────
            -- Faol klub hamma uchun ochiq (mijoz klublar ro'yxatini ko'radi),
            -- yozish esa faqat o'z tashkiloti ichida.
            ALTER TABLE clubs ENABLE ROW LEVEL SECURITY;
            ALTER TABLE clubs FORCE ROW LEVEL SECURITY;
            CREATE POLICY clubs_read ON clubs
                FOR SELECT USING (
                    status = 'active'
                    OR org_id = app_org_id()
                    OR id = app_club_id()
                    OR EXISTS (
                        SELECT 1 FROM memberships m
                        WHERE m.club_id = clubs.id AND m.user_id = app_user_id()
                    )
                );
            CREATE POLICY clubs_write ON clubs
                FOR ALL USING (org_id = app_org_id())
                WITH CHECK (org_id = app_org_id());

            -- ── memberships ──────────────────────────────────────────────────
            ALTER TABLE memberships ENABLE ROW LEVEL SECURITY;
            ALTER TABLE memberships FORCE ROW LEVEL SECURITY;
            CREATE POLICY memberships_scope ON memberships
                USING (user_id = app_user_id() OR club_id = app_club_id())
                WITH CHECK (club_id = app_club_id());

            -- ── refresh_tokens ───────────────────────────────────────────────
            -- Token o'zi sir; almashtirishda aynan shu xeshli qator ochiladi.
            ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;
            ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY;
            CREATE POLICY refresh_tokens_scope ON refresh_tokens
                USING (user_id = app_user_id()
                       OR (app_refresh_hash() <> '' AND token_hash = app_refresh_hash()))
                WITH CHECK (user_id = app_user_id());

            -- ── audit_log ────────────────────────────────────────────────────
            ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
            ALTER TABLE audit_log FORCE ROW LEVEL SECURITY;
            CREATE POLICY audit_log_scope ON audit_log
                USING (org_id = app_org_id() OR actor_user_id = app_user_id())
                WITH CHECK (actor_user_id = app_user_id());
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            GRANT USAGE ON SCHEMA public TO {APP_ROLE}, {PLATFORM_ROLE};

            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};

            -- Platforma roli asosan o'qiydi; yozish faqat uch jadvalda
            GRANT SELECT ON ALL TABLES IN SCHEMA public TO {PLATFORM_ROLE};
            GRANT INSERT, UPDATE ON organizations, audit_log TO {PLATFORM_ROLE};
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {PLATFORM_ROLE};

            ALTER DEFAULT PRIVILEGES IN SCHEMA public
                GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
                GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
                GRANT SELECT ON TABLES TO {PLATFORM_ROLE};
            """
        )
    )


def upgrade() -> None:
    _create_roles()
    _context_functions()
    _tables()
    _rls()
    _grants()


def downgrade() -> None:
    """Migratsiyalar faqat oldinga — prod'da ishlatilmaydi."""
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
