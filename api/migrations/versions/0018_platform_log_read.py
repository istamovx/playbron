"""Platforma — super admin audit_log/auth_events'ni o'qishi.

Production-readiness audit (2026-08-16, loyiha egasining so'rovi:
"super admin va klub adminida o'ziga hos bo'lgan loglar yursin").
`0017`gacha bo'lgan audit shuni topdi: `audit_log` va `auth_events`
jadvallarining RLS'i klub OWNER/ADMIN uchun ANCHADAN to'g'ri edi
(`club_id = app_club_id()` shartli policy'lar), lekin `app_platform()`
uchun HECH QANDAY o'qish policy'si yo'q edi.

`playbron_platform` roli `GRANT SELECT ON ALL TABLES` (`0001_core.py`)
orqali GRANT darajasida ruxsatga ega — lekin ikkalasi ham
`FORCE ROW LEVEL SECURITY` ostida (jadval EGASI ham RLS'dan qochmaydi,
faqat BYPASSRLS qocha oladi — Render bepul rejasida bu yo'q,
`[[render-free-tier-no-bypassrls]]`). GRANT bilan RLS ikki ALOHIDA
qatlam (`[[playbron-grant-vs-rls-blind-spot]]`): GRANT bor, mos POLICY
yo'q — natija har doim BO'SH ro'yxat, xato emas. Bu migratsiya aynan
shu yetishmagan policy'larni qo'shadi.
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_platform_log_read"
down_revision = "0017_platform_org_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _rls()
    _self_test()


def _rls() -> None:
    op.execute(
        sa.text(
            """
            -- Mavjud policy'lar (klub OWNER/ADMIN, aktyorning o'zi, tashkilot
            -- egasi) bilan OR bo'lib qo'shiladi — ular tegilmaydi.
            CREATE POLICY audit_log_platform_read ON audit_log
                FOR SELECT USING (app_platform());

            CREATE POLICY auth_events_platform_read ON auth_events
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
    """GUC'siz izolyatsiya, `app.platform=true` bilan cross-tenant o'qish —
    `0015`/`0016`/`0017`dagi bilan bir xil naqsh."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "audit_log", "auth_events")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'platform.log.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        audit_id = conn.execute(
            sa.text(
                "INSERT INTO audit_log (actor_user_id, action, target)"
                " VALUES (:u, 'probe.action', 'probe') RETURNING id"
            ),
            {"u": owner_id},
        ).scalar_one()
        event_id = conn.execute(
            sa.text(
                "INSERT INTO auth_events (event, user_id, detail)"
                " VALUES ('probe_event', :u, '{}') RETURNING id"
            ),
            {"u": owner_id},
        ).scalar_one()
    finally:
        _force_rls(conn, scoped, enabled=True)

    try:
        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
        isolated_audit = conn.execute(
            sa.text("SELECT count(*) FROM audit_log WHERE id = :i"), {"i": audit_id}
        ).scalar_one()
        isolated_event = conn.execute(
            sa.text("SELECT count(*) FROM auth_events WHERE id = :i"), {"i": event_id}
        ).scalar_one()
        if isolated_audit != 0 or isolated_event != 0:
            raise RuntimeError(
                "audit_log/auth_events platform_read: app.platform o'rnatilmasa ham ko'rindi"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'true', true)"))
        visible_audit = conn.execute(
            sa.text("SELECT count(*) FROM audit_log WHERE id = :i"), {"i": audit_id}
        ).scalar_one()
        visible_event = conn.execute(
            sa.text("SELECT count(*) FROM auth_events WHERE id = :i"), {"i": event_id}
        ).scalar_one()
        if visible_audit != 1 or visible_event != 1:
            raise RuntimeError(
                "audit_log/auth_events platform_read: app.platform=true bo'lsa ham ko'rinmadi"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM audit_log WHERE id = :i"), {"i": audit_id})
        conn.execute(sa.text("DELETE FROM auth_events WHERE id = :i"), {"i": event_id})
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
