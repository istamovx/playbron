"""Xodim o'z Telegram'ini bog'laydi + `0009`dagi bildirishnoma teshigini tuzatadi.

**1) `0009` xatosi (bu migratsiya uni TUZATADI, `0009`ning o'zi
o'zgarmaydi — "migratsiyalar faqat oldinga"):**

`booking_notify_targets()` va `staff_telegram_booking_notify` policy'si
ICHIDA `memberships` jadvaliga `EXISTS (SELECT 1 FROM memberships ...)`
bilan murojaat qiladi. Bu SELECT ham RLS ostida — `memberships_read`
(`0007`) faqat `app_user_id()`/`app_club_role_claim()` GUC'lariga qaraydi,
ular esa shu funksiya ishlayotgan paytda (mijoz bron yuborgani — uning
`app.club_id` umuman yo'q) BO'SH. Natija: `[[render-free-tier-no-bypassrls]]`
muhitida (BYPASSRLS'siz) `EXISTS` HAR DOIM yolg'on — xodimga bildirishnoma
HECH QACHON yetib bormaydi, lekin lokal superuser test buni yashiradi
(policy umuman baholanmaydi). Xuddi shu sinf xato bu loyihada bir necha
marta chiqqan (`[[render-free-tier-no-bypassrls]]`dagi ro'yxat).

Yechim — xuddi `staff_telegram_booking_notify`ning o'zi kabi, `memberships`
uchun ham `app_booking_notify_claim()` GUC'iga qarab ochiladigan qo'shimcha
SELECT policy.

**2) Xodim Telegram bog'lash — `staff_telegram`ga yagona yozish yo'li.**

`0005`dagi izoh xato taxminga tayangan edi: "FORCE + policy yo'qligi =
yopiq, yagona kirish SECURITY DEFINER" — lekin BYPASSRLS'siz muhitda
SECURITY DEFINER RLS'ni o'chirmaydi, policy hali ham kerak. Shu sabab
bu yerda ham xuddi shunday GUC-gated yozish policy'si qo'shiladi:
funksiya `app.telegram_link_user` ni ICHKARIDA o'rnatadi, faqat shu
qatorga yozishga ruxsat beradi.

Oqim — `botlogin.py`dagi bilan bir xil nonce+webhook+poll naqshi:
  1. Xodim konsolda (allaqachon kirgan holda) "Bildirishnomani ulash"
     bosadi → `POST /auth/telegram/link/start` o'z `user_id`si bilan
     nonce oladi (Redis, `lnk_` prefiksi — admin bot webhook'i shu
     prefiks bo'yicha kirish oqimidan ajratadi).
  2. Botda **Start** bosiladi → webhook `staff_telegram_link_confirm()`
     ni chaqiradi.
  3. Konsol nonce'ni poll qiladi.

Revision ID: 0010_staff_telegram_link
Revises: 0009_bookings
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_staff_telegram_link"
down_revision = "0009_bookings"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"


def upgrade() -> None:
    _fix_booking_notify_membership_gap()
    _telegram_link()
    _grants()
    _assert_booking_notify_reaches_linked_staff()
    _assert_link_confirm_writes_row()


def _fix_booking_notify_membership_gap() -> None:
    op.execute(
        sa.text(
            """
            -- `booking_notify_targets()` shu GUC'ni allaqachon o'rnatadi
            -- (`0009`) — bu yerda faqat `memberships` ham shu bitta claim'ga
            -- ishonishni o'rganadi, boshqa hech narsa o'zgarmaydi.
            CREATE POLICY memberships_booking_notify ON memberships FOR SELECT
                USING (
                    club_id = app_booking_notify_claim()
                    AND status = 'active'
                );
            """
        )
    )


def _telegram_link() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_telegram_link_claim() RETURNS bigint
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT NULLIF(current_setting('app.telegram_link_user', true), '')::bigint $$;

            -- Yagona yozish yo'li: `user_id` funksiya ICHIDA o'rnatilgan
            -- GUC'ga teng bo'lgandagina. SELECT'ga tegmaydi — `staff_telegram_self`
            -- (`0005`) bilan bir xil natijaga qo'shimcha (permissive OR).
            CREATE POLICY staff_telegram_link_write ON staff_telegram FOR ALL
                USING (user_id = app_telegram_link_claim())
                WITH CHECK (user_id = app_telegram_link_claim());

            -- Ishonch manbai — nonce (Redis'da, `/auth/telegram/link/start`
            -- allaqachon autentifikatsiya qilingan xodim uchun yaratadi).
            -- Funksiya `p_user_id`ni qayta tekshirmaydi: `users`ni o'qish ham
            -- RLS ostida, bu yerda hech qanday mos GUC yo'q — xuddi shu
            -- teshikka tushmaslik uchun ATAYLAB emas.
            CREATE OR REPLACE FUNCTION staff_telegram_link_confirm(
                p_user_id     bigint,
                p_telegram_id bigint,
                p_chat_id     bigint
            ) RETURNS void
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            BEGIN
                IF p_user_id IS NULL OR p_telegram_id IS NULL OR p_chat_id IS NULL THEN
                    RETURN;
                END IF;

                PERFORM set_config('app.telegram_link_user', p_user_id::text, true);

                INSERT INTO staff_telegram (user_id, telegram_id, chat_id, linked_at)
                VALUES (p_user_id, p_telegram_id, p_chat_id, now())
                ON CONFLICT (user_id) DO UPDATE
                    SET telegram_id = EXCLUDED.telegram_id,
                        chat_id     = EXCLUDED.chat_id,
                        linked_at   = now(),
                        blocked_at  = NULL;

                PERFORM set_config('app.telegram_link_user', '', true);
            END
            $fn$;

            REVOKE ALL ON FUNCTION staff_telegram_link_confirm(bigint, bigint, bigint)
                FROM PUBLIC;
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            -- `0005`da faqat SELECT berilgan edi ("yozish SECURITY DEFINER
            -- orqali" degan taxmin bilan) — endi haqiqatan yozadigan funksiya
            -- bor, GRANT ham kerak (POLICY yagona qatlam emas).
            GRANT INSERT, UPDATE ON staff_telegram TO {PLATFORM_ROLE};

            DO $do$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                    ALTER FUNCTION staff_telegram_link_confirm(bigint, bigint, bigint)
                        OWNER TO {PLATFORM_ROLE};
                END IF;
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'staff_telegram_link_confirm egasi o''zgartirilmadi (huquq yo''q)';
            END
            $do$;

            GRANT EXECUTE ON FUNCTION staff_telegram_link_confirm(bigint, bigint, bigint)
                TO {APP_ROLE};
            """
        )
    )


def _assert_booking_notify_reaches_linked_staff() -> None:
    """`booking_notify_targets()` HAQIQATAN bog'langan xodimni topadimi.

    Superuser/BYPASSRLS ostida policy baholanmaydi — soxta yashil bermaslik
    uchun o'sha holatda o'tkazib yuboriladi (`0007`dagi naqsh bilan bir xil).
    """
    conn = op.get_bind()
    exempt = conn.execute(
        sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if exempt:
        return

    scoped = ("users", "organizations", "clubs", "memberships", "staff_telegram")
    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))

    try:
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'migration.notifyprobe', 'active', 'probe') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                " VALUES (:o, 'notifyprobe', 'active', NULL) RETURNING id"
            ),
            {"o": staff_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'notifyprobe', 'active')"
                " RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        conn.execute(
            sa.text(
                "INSERT INTO memberships (user_id, club_id, role, status)"
                " VALUES (:u, :c, 'STAFF', 'active')"
            ),
            {"u": staff_id, "c": club_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO staff_telegram (user_id, telegram_id, chat_id)"
                " VALUES (:u, 999001, 999001)"
            ),
            {"u": staff_id},
        )
    finally:
        for table in scoped:
            conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

    seen = conn.execute(
        sa.text("SELECT chat_id FROM booking_notify_targets(:c)"), {"c": club_id}
    ).scalars().all()

    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DELETE FROM organizations WHERE name = 'notifyprobe'"))
    conn.execute(
        sa.text("DELETE FROM users WHERE login = 'migration.notifyprobe' AND kind = 'staff'")
    )
    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

    if 999001 not in seen:
        raise RuntimeError(
            "booking_notify_targets() bog'langan xodimni topmadi — "
            "memberships_booking_notify policy'si ishlamayapti, xodimga "
            "HECH QACHON bron bildirishnomasi yetib bormaydi"
        )


def _assert_link_confirm_writes_row() -> None:
    """`staff_telegram_link_confirm()` haqiqatan qator yozadimi (real RLS ostida)."""
    conn = op.get_bind()
    exempt = conn.execute(
        sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if exempt:
        return

    conn.execute(sa.text("ALTER TABLE users NO FORCE ROW LEVEL SECURITY"))
    try:
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'migration.linkprobe', 'active', 'probe') RETURNING id"
            )
        ).scalar_one()
    finally:
        conn.execute(sa.text("ALTER TABLE users FORCE ROW LEVEL SECURITY"))

    conn.execute(
        sa.text("SELECT staff_telegram_link_confirm(:u, 999002, 999002)"), {"u": staff_id}
    )

    conn.execute(sa.text("ALTER TABLE staff_telegram NO FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE users NO FORCE ROW LEVEL SECURITY"))
    try:
        chat_id = conn.execute(
            sa.text("SELECT chat_id FROM staff_telegram WHERE user_id = :u"), {"u": staff_id}
        ).scalar_one_or_none()
        conn.execute(sa.text("DELETE FROM staff_telegram WHERE user_id = :u"), {"u": staff_id})
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": staff_id})
    finally:
        conn.execute(sa.text("ALTER TABLE staff_telegram FORCE ROW LEVEL SECURITY"))
        conn.execute(sa.text("ALTER TABLE users FORCE ROW LEVEL SECURITY"))

    if chat_id != 999002:
        raise RuntimeError(
            "staff_telegram_link_confirm() qator yozmadi — "
            "staff_telegram_link_write policy'si yoki GRANT tekshirilsin"
        )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
