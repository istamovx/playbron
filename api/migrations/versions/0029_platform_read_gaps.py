"""Super admin: `memberships` va `stations` uchun yetishmagan o'qish policy'lari.

Audit topilmasi (2026-08-16). `[[playbron-grant-vs-rls-blind-spot]]` bilan
BIR XIL sinf xato, uchinchi marta takrorlandi (`0016` `users` uchun,
`0018` `audit_log`/`auth_events` uchun tuzatgan edi):

  - `platform/service.py::get_organization_detail()` xodimlarni
    `memberships`dan o'qiydi, lekin `app_platform()` uchun policy YO'Q →
    super admin "Tashkilot — ko'rish" modalida DOIM `Xodimlar (0)` ko'radi.

  - `list_organizations()`/`get_organization_detail()` `stations_count`
    hisoblaydi; `stations_read` (`0009`) faqat `clubs.status='active'`
    yoki `club_id = app_club_id()` shoxiga ega. Platform sessiyasida
    `app.club_id` umuman o'rnatilmaydi, `auth_owner_signup()` esa klubni
    `'draft'` holatida yaratadi → yangi ro'yxatdan o'tgan HAR BIR klub
    uchun `Stansiya: 0` ko'rinadi.

Ikkalasi ham XATO BERMAYDI — GRANT bor, POLICY yo'q, ya'ni jimgina BO'SH.
Lokalda ko'rinmaydi: dev'dagi `playbron_platform` roli `BYPASSRLS` bilan,
Render bepul rejasida esa u yo'q (`[[render-free-tier-no-bypassrls]]`).

Revision ID: 0029_platform_read_gaps
Revises: 0028_stock_order_cancel
"""

import sqlalchemy as sa
from alembic import op

revision = "0029_platform_read_gaps"
down_revision = "0028_stock_order_cancel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _rls()
    _self_test()


def _rls() -> None:
    op.execute(
        sa.text(
            """
            -- Mavjud policy'lar bilan OR bo'lib qo'shiladi — tegilmaydi.
            -- `0018_platform_log_read.py`dagi bilan bir xil naqsh.
            CREATE POLICY memberships_platform_read ON memberships
                FOR SELECT USING (app_platform());

            CREATE POLICY stations_platform_read ON stations
                FOR SELECT USING (app_platform());
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
    """`app.platform` o'rnatilmasa ko'rinmaydi, o'rnatilsa ko'rinadi.

    Klub ATAYLAB `'draft'` — aynan shu holat buzilgan edi (`stations_read`
    faqat `status='active'` klublarni ochadi).
    """
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "clubs", "stations", "memberships")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'platform.gap.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:u, 'Platform Gap Org', 'active') RETURNING id"
            ),
            {"u": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Platform Gap Club', 'draft') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        station_id = conn.execute(
            sa.text(
                "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                " VALUES (:c, 'GAP-1', 'Standart', 'ps5', 40000) RETURNING id"
            ),
            {"c": club_id},
        ).scalar_one()
        conn.execute(
            sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"),
            {"u": owner_id, "c": club_id},
        )
    finally:
        _force_rls(conn, scoped, enabled=True)

    try:
        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
        conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_id', '0', true)"))

        blind_members = conn.execute(
            sa.text("SELECT count(*) FROM memberships WHERE club_id = :c"), {"c": club_id}
        ).scalar_one()
        blind_stations = conn.execute(
            sa.text("SELECT count(*) FROM stations WHERE id = :s"), {"s": station_id}
        ).scalar_one()
        if blind_members != 0 or blind_stations != 0:
            raise RuntimeError(
                "platform_read: app.platform o'rnatilmasa ham ko'rindi"
                f" (memberships={blind_members}, stations={blind_stations})"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'true', true)"))
        seen_members = conn.execute(
            sa.text("SELECT count(*) FROM memberships WHERE club_id = :c"), {"c": club_id}
        ).scalar_one()
        if seen_members != 1:
            raise RuntimeError(
                "memberships_platform_read: super admin xodimni ko'rmadi"
                " (preview modal yana bo'sh bo'ladi)"
            )

        seen_stations = conn.execute(
            sa.text("SELECT count(*) FROM stations WHERE id = :s"), {"s": station_id}
        ).scalar_one()
        if seen_stations != 1:
            raise RuntimeError(
                "stations_platform_read: draft klubning stansiyasi ko'rinmadi"
                " (Stansiya ustuni yana 0 bo'ladi)"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM memberships WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM stations WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
