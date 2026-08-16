"""Bot menyusi — klub admin/egasini `telegram_id` orqali xavfsiz aniqlash.

Loyiha egasining so'rovi (2026-08-16): admin botga klub admini/egasi
yozganda 3 ta hisobot tugmasi (kunlik tushum, xarajat, analitika)
ko'rsatilsin. Webhook'da odatiy RLS konteksti (`app.user_id`/`app.club_id`
GUC) YO'Q — Telegram serveridan kelayotgan chaqiruvda JWT/sessiya yo'q,
faqat `X-Telegram-Bot-Api-Secret-Token` bilan himoyalangan xom HTTP.
Shuning uchun `memberships`/`clubs`ga oddiy so'rov RLS tomonidan
jimgina bo'sh qaytariladi (`[[playbron-grant-vs-rls-blind-spot]]` bilan
bir xil sinf muammo).

`bot_staff_context(p_telegram_id)` — SECURITY DEFINER: `staff_telegram`
orqali `telegram_id`dan `user_id` topadi (bloklangan bo'lsa — bo'sh),
so'ng shu xodimning OWNER/ADMIN bo'lgan birinchi faol a'zoligini
qaytaradi. STAFF (oddiy xodim) — bo'sh natija: hisobot tugmalari faqat
OWNER/ADMIN uchun (`docs/01-architecture.md`:174 ruxsat matritsasi bilan
bir xil ruh — moliyaviy ma'lumot xodimga ko'rinmaydi).

Revision ID: 0022_bot_menu_context
Revises: 0021_shifts
"""

import sqlalchemy as sa
from alembic import op

revision = "0022_bot_menu_context"
down_revision = "0021_shifts"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"


def upgrade() -> None:
    _claim_function()
    _rls()
    _function()
    _self_test()


def _claim_function() -> None:
    """SECURITY DEFINER funksiya EGASI ham (Render bepul rejasida)
    NOBYPASSRLS — funksiya ICHIDAGI so'rovlar HAM RLS ostida qoladi
    (`[[render-free-tier-no-bypassrls]]`). `booking_notify_targets()`
    (`0009_bookings.py`) bilan bir xil naqsh: funksiya o'zi GUC'ni
    o'rnatib-o'chiradi, tashqi hech kim uni to'g'ridan o'rnata olmaydi
    (API faqat parametrlashtirilgan so'rov yuboradi, xom SQL emas)."""
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_bot_lookup_claim() RETURNS boolean
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(NULLIF(current_setting('app.bot_lookup', true), ''), 'false')::boolean $$;
            """
        )
    )


def _rls() -> None:
    op.execute(
        sa.text(
            """
            CREATE POLICY staff_telegram_bot_lookup ON staff_telegram FOR SELECT
                USING (app_bot_lookup_claim());
            CREATE POLICY memberships_bot_lookup ON memberships FOR SELECT
                USING (app_bot_lookup_claim());
            CREATE POLICY users_bot_lookup ON users FOR SELECT
                USING (app_bot_lookup_claim());
            CREATE POLICY clubs_bot_lookup ON clubs FOR SELECT
                USING (app_bot_lookup_claim());
            """
        )
    )


def _function() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION bot_staff_context(p_telegram_id bigint)
                RETURNS TABLE(user_id bigint, first_name text, club_id bigint,
                              club_name text, role text)
                LANGUAGE plpgsql STABLE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                v_user_id bigint;
            BEGIN
                PERFORM set_config('app.bot_lookup', 'true', true);

                SELECT st.user_id INTO v_user_id FROM staff_telegram st
                 WHERE st.telegram_id = p_telegram_id AND st.blocked_at IS NULL;
                IF v_user_id IS NULL THEN
                    PERFORM set_config('app.bot_lookup', '', true);
                    RETURN;
                END IF;

                RETURN QUERY
                SELECT u.id, u.first_name::text, m.club_id, c.name::text, m.role::text
                FROM memberships m
                JOIN users u ON u.id = m.user_id
                JOIN clubs c ON c.id = m.club_id
                WHERE m.user_id = v_user_id AND m.status = 'active'
                  AND m.role IN ('OWNER', 'ADMIN')
                ORDER BY m.club_id
                LIMIT 1;

                PERFORM set_config('app.bot_lookup', '', true);
            END
            $fn$;

            GRANT EXECUTE ON FUNCTION bot_staff_context(bigint) TO {APP_ROLE};
            """
        )
    )


def _force_rls(conn: sa.Connection, tables: tuple[str, ...], *, enabled: bool) -> None:
    verb = "FORCE" if enabled else "NO FORCE"
    for table in tables:
        conn.execute(sa.text(f"ALTER TABLE {table} {verb} ROW LEVEL SECURITY"))


def _exempt(conn: sa.Connection) -> bool:
    return bool(
        conn.execute(
            sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    )


def _self_test() -> None:
    """OWNER/ADMIN uchun klub konteksti qaytishi, STAFF uchun BO'SH bo'lishi,
    bloklangan xodim uchun ham BO'SH bo'lishi kerak."""
    conn = op.get_bind()
    exempt = _exempt(conn)

    scoped = ("users", "organizations", "clubs", "memberships", "staff_telegram")
    if not exempt:
        _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'botmenu.probe.owner', 'active', 'Owner') RETURNING id"
            )
        ).scalar_one()
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'botmenu.probe.staff', 'active', 'Staff') RETURNING id"
            )
        ).scalar_one()
        blocked_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'botmenu.probe.blocked', 'active', 'Blocked') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Botmenu Probe Org', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Botmenu Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        for uid, role in ((owner_id, "OWNER"), (staff_id, "STAFF"), (blocked_id, "OWNER")):
            conn.execute(
                sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, :r)"),
                {"u": uid, "c": club_id, "r": role},
            )
        conn.execute(
            sa.text(
                "INSERT INTO staff_telegram (user_id, telegram_id, chat_id, linked_at)"
                " VALUES (:u, :tg, :tg, now())"
            ),
            {"u": owner_id, "tg": 900000001},
        )
        conn.execute(
            sa.text(
                "INSERT INTO staff_telegram (user_id, telegram_id, chat_id, linked_at)"
                " VALUES (:u, :tg, :tg, now())"
            ),
            {"u": staff_id, "tg": 900000002},
        )
        conn.execute(
            sa.text(
                "INSERT INTO staff_telegram (user_id, telegram_id, chat_id, linked_at, blocked_at)"
                " VALUES (:u, :tg, :tg, now(), now())"
            ),
            {"u": blocked_id, "tg": 900000003},
        )
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=True)

    try:
        owner_row = conn.execute(
            sa.text("SELECT club_id, role FROM bot_staff_context(900000001)")
        ).first()
        if owner_row is None or owner_row.role != "OWNER" or owner_row.club_id != club_id:
            raise RuntimeError("bot_staff_context: OWNER uchun klub konteksti topilmadi")

        staff_row = conn.execute(
            sa.text("SELECT club_id FROM bot_staff_context(900000002)")
        ).first()
        if staff_row is not None:
            raise RuntimeError("bot_staff_context: STAFF uchun kontekst qaytdi — xavfli")

        blocked_row = conn.execute(
            sa.text("SELECT club_id FROM bot_staff_context(900000003)")
        ).first()
        if blocked_row is not None:
            raise RuntimeError("bot_staff_context: bloklangan xodim uchun kontekst qaytdi — xavfli")

        unknown_row = conn.execute(
            sa.text("SELECT club_id FROM bot_staff_context(999999999)")
        ).first()
        if unknown_row is not None:
            raise RuntimeError("bot_staff_context: noma'lum telegram_id uchun kontekst qaytdi")
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=False)
        conn.execute(
            sa.text("DELETE FROM staff_telegram WHERE user_id IN (:o, :s, :b)"),
            {"o": owner_id, "s": staff_id, "b": blocked_id},
        )
        conn.execute(sa.text("DELETE FROM memberships WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:o, :s, :b)"),
            {"o": owner_id, "s": staff_id, "b": blocked_id},
        )
        if not exempt:
            _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
