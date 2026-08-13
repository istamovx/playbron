"""RLS qattiqlashtirish — adversarial auditdan keyin.

Yopiladigan teshiklar:
  1. `organizations` INSERT — istalgan foydalanuvchi o'zini tasdiqlangan tashkilot
     va istalgan tarif bilan yaratardi (to'lov butunlay chetlab o'tilardi).
  2. `clubs_write` — faqat `org_id` bo'yicha edi, ya'ni bitta klubdagi STAFF
     tashkilotning boshqa klublarini o'chira va `payment_credentials` ni
     o'zgartira olardi (to'lovni o'z hisobiga yo'naltirish).
  3. `clubs.payment_credentials` — `status='active'` klublar anonim o'qilardi,
     RLS ustun darajasida ishlamaydi. Ustun alohida jadvalga ko'chirildi.
  4. `audit_log` — append-only emas edi, aktor o'z izini o'chira olardi.
  5. `clubs_read` / `memberships_scope` — `status` tekshirilmasdi, ishdan
     bo'shatilgan xodim klubni o'qiyverardi.
  6. `ALTER DEFAULT PRIVILEGES` — yangi jadval RLS'siz qo'shilsa fail-open bo'lardi.

Revision ID: 0003_rls_hardening
Revises: 0002_seed
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003_rls_hardening"
down_revision = "0002_seed"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"


def upgrade() -> None:
    # ── Rol yordamchisi ───────────────────────────────────────────────────
    # SECURITY DEFINER: `memberships` ustidagi RLS'ni chetlab o'tadi, aks holda
    # policy ichida policy tekshirilib rekursiya kelib chiqardi.
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_club_role(target_club_id bigint)
                RETURNS text
                LANGUAGE sql STABLE SECURITY DEFINER
                SET search_path = public, pg_temp
            AS $$
                SELECT m.role FROM memberships m
                WHERE m.club_id = target_club_id
                  AND m.user_id = app_user_id()
                  AND m.status = 'active'
                LIMIT 1
            $$;

            REVOKE ALL ON FUNCTION app_club_role(bigint) FROM PUBLIC;
            """
        )
    )
    op.execute(sa.text(f"GRANT EXECUTE ON FUNCTION app_club_role(bigint) TO {APP_ROLE};"))

    # ── 3. To'lov kalitlari alohida jadvalga ──────────────────────────────
    op.create_table(
        "club_payment_credentials",
        sa.Column(
            "club_id",
            sa.BigInteger,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("credentials", postgresql.JSONB, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.drop_column("clubs", "payment_credentials")

    # ── Policy'larni qayta yozish ─────────────────────────────────────────
    op.execute(
        sa.text(
            """
            -- 1. organizations: self-serve qoladi, lekin faqat `pending` va tarifsiz.
            DROP POLICY IF EXISTS organizations_tenant ON organizations;

            CREATE POLICY organizations_read ON organizations
                FOR SELECT USING (owner_user_id = app_user_id() OR id = app_org_id());

            CREATE POLICY organizations_insert ON organizations
                FOR INSERT WITH CHECK (
                    owner_user_id = app_user_id()
                    AND status = 'pending'
                    AND plan_code IS NULL
                );

            CREATE POLICY organizations_update ON organizations
                FOR UPDATE USING (owner_user_id = app_user_id())
                WITH CHECK (owner_user_id = app_user_id());

            -- 2. clubs: yozish roli va faol klubga bog'landi.
            DROP POLICY IF EXISTS clubs_write ON clubs;
            DROP POLICY IF EXISTS clubs_read ON clubs;

            CREATE POLICY clubs_read ON clubs
                FOR SELECT USING (
                    status = 'active'
                    OR org_id = app_org_id()
                    OR id = app_club_id()
                    OR EXISTS (
                        SELECT 1 FROM memberships m
                        WHERE m.club_id = clubs.id
                          AND m.user_id = app_user_id()
                          AND m.status = 'active'
                    )
                );

            CREATE POLICY clubs_insert ON clubs
                FOR INSERT WITH CHECK (
                    org_id = app_org_id()
                    AND EXISTS (
                        SELECT 1 FROM organizations o
                        WHERE o.id = clubs.org_id AND o.owner_user_id = app_user_id()
                    )
                );

            CREATE POLICY clubs_update ON clubs
                FOR UPDATE
                USING (id = app_club_id() AND app_club_role(id) IN ('OWNER', 'ADMIN'))
                WITH CHECK (id = app_club_id() AND org_id = app_org_id());

            -- 5. memberships: bo'shatilgan xodim o'z a'zoligini ko'rmaydi.
            DROP POLICY IF EXISTS memberships_scope ON memberships;

            CREATE POLICY memberships_read ON memberships
                FOR SELECT USING (
                    (user_id = app_user_id() AND status = 'active')
                    OR (club_id = app_club_id()
                        AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'))
                );

            CREATE POLICY memberships_write ON memberships
                FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'));

            -- 4. audit_log: faqat o'qish va qo'shish. O'chirish/tahrirlash yo'q.
            DROP POLICY IF EXISTS audit_log_scope ON audit_log;

            CREATE POLICY audit_log_read ON audit_log
                FOR SELECT USING (org_id = app_org_id() OR actor_user_id = app_user_id());

            CREATE POLICY audit_log_insert ON audit_log
                FOR INSERT WITH CHECK (actor_user_id = app_user_id());

            -- To'lov kalitlari: faqat o'z tashkiloti va faqat OWNER.
            ALTER TABLE club_payment_credentials ENABLE ROW LEVEL SECURITY;
            ALTER TABLE club_payment_credentials FORCE ROW LEVEL SECURITY;

            CREATE POLICY club_payment_credentials_owner ON club_payment_credentials
                USING (
                    EXISTS (
                        SELECT 1 FROM clubs c
                        WHERE c.id = club_payment_credentials.club_id
                          AND c.org_id = app_org_id()
                          AND app_club_role(c.id) = 'OWNER'
                    )
                )
                WITH CHECK (
                    EXISTS (
                        SELECT 1 FROM clubs c
                        WHERE c.id = club_payment_credentials.club_id
                          AND c.org_id = app_org_id()
                          AND app_club_role(c.id) = 'OWNER'
                    )
                );
            """
        )
    )

    # ── Imtiyozlarni toraytirish ──────────────────────────────────────────
    op.execute(
        sa.text(
            f"""
            -- Policy yo'qligi INSERT/UPDATE/DELETE ni bloklaydi, lekin grant'ni ham
            -- olib tashlash ikkinchi qatlam himoya beradi.
            REVOKE DELETE ON organizations, clubs, audit_log FROM {APP_ROLE};
            REVOKE UPDATE ON audit_log FROM {APP_ROLE};

            -- Tarif va holatni ilova roli o'zgartira olmaydi — bu platforma ishi.
            REVOKE UPDATE (status, plan_code) ON organizations FROM {APP_ROLE};
            REVOKE UPDATE (status) ON clubs FROM {APP_ROLE};

            -- 6. Fail-open sukut imtiyozlarini olib tashlaymiz: yangi jadval
            -- avtomatik ochilib qolmaydi, har bir migratsiya grant'ni o'zi yozadi.
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
                REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM {APP_ROLE};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
                REVOKE USAGE, SELECT ON SEQUENCES FROM {APP_ROLE};
            ALTER DEFAULT PRIVILEGES IN SCHEMA public
                REVOKE SELECT ON TABLES FROM {PLATFORM_ROLE};

            -- Yangi jadval uchun grant — aniq yoziladi
            GRANT SELECT, INSERT, UPDATE, DELETE ON club_payment_credentials TO {APP_ROLE};
            GRANT SELECT ON club_payment_credentials TO {PLATFORM_ROLE};
            """
        )
    )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
