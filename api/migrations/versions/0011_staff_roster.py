"""`users_staff_roster` — OWNER/ADMIN o'z klubi xodimlarini ko'radi.

Yana bir `[[playbron-rls-cross-table-subquery-gap]]` ko'rinishi, bu safar
JOIN orqali: `GET /clubs/{id}/staff` (`modules/staff/router.py::list_staff`)
`memberships JOIN users` qiladi. `memberships_read` (`0007`) OWNER/ADMIN
uchun butun klub a'zoligini ochadi — lekin `users` jadvalida bunga mos
policy YO'Q (`users_self`, `users_login_probe`, `users_staff_provision`,
`users_booking_contact` — hech biri "boshqa xodimni ko'rish"ga ruxsat
bermaydi). Natija: INNER JOIN har bir qatorda `users`ni HAM tekshiradi,
u yopiq bo'lgani uchun faqat CHAQIRUVCHINING O'Z qatori tirik qoladi —
xodimlar ro'yxati sukut ravishda BITTA qatorga (o'ziga) qisqarib qoladi.

Lokal `docker compose`da ham `playbron_app` (RLS ostida, superuser emas)
bilan ulanadi, shuning uchun bu xato birinchi haqiqiy testda (list_staff
uchun yozilgan) darhol ko'rindi — Render-shaped simulyator kerak bo'lmadi.

Revision ID: 0011_staff_roster
Revises: 0010_staff_telegram_link
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_staff_roster"
down_revision = "0010_staff_telegram_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _add_policy()
    _assert_owner_sees_full_roster()


def _add_policy() -> None:
    op.execute(
        sa.text(
            """
            -- Faqat SELECT, faqat o'z klubi, faqat OWNER/ADMIN, faqat FAOL
            -- a'zolik. `users_booking_contact` (0009) bilan bir xil naqsh —
            -- klub kontekstidagi haqiqiy ish ehtiyoji, undan ortiq emas.
            CREATE POLICY users_staff_roster ON users FOR SELECT
                USING (
                    kind = 'staff'
                    AND app_club_id() <> 0
                    AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN')
                    AND EXISTS (
                        SELECT 1 FROM memberships m
                        WHERE m.user_id = users.id
                          AND m.club_id = app_club_id()
                          AND m.status = 'active'
                    )
                );
            """
        )
    )


def _assert_owner_sees_full_roster() -> None:
    """OWNER haqiqatan butun ro'yxatni ko'radimi — real RLS ostida.

    Superuser/BYPASSRLS ostida policy baholanmaydi — soxta yashil
    bermaslik uchun o'tkazib yuboriladi (`0007`/`0010`dagi naqsh).
    """
    conn = op.get_bind()
    exempt = conn.execute(
        sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if exempt:
        return

    scoped = ("users", "organizations", "clubs", "memberships")
    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))

    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'migration.rosterowner', 'active', 'A') RETURNING id"
            )
        ).scalar_one()
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'migration.rosterstaff', 'active', 'B') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                " VALUES (:o, 'rosterprobe', 'active', NULL) RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'rosterprobe', 'active')"
                " RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        conn.execute(
            sa.text(
                "INSERT INTO memberships (user_id, club_id, role) VALUES"
                " (:owner, :club, 'OWNER'), (:staff, :club, 'STAFF')"
            ),
            {"owner": owner_id, "staff": staff_id, "club": club_id},
        )
    finally:
        for table in scoped:
            conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

    conn.execute(
        sa.text(
            "SELECT set_config('app.user_id', :u, true),"
            "       set_config('app.club_id', :c, true),"
            "       set_config('app.club_role', 'OWNER', true)"
        ),
        {"u": str(owner_id), "c": str(club_id)},
    )
    seen = conn.execute(
        sa.text(
            "SELECT count(*) FROM memberships m JOIN users u ON u.id = m.user_id"
            " WHERE m.club_id = :c AND m.status = 'active'"
        ),
        {"c": club_id},
    ).scalar_one()
    conn.execute(
        sa.text(
            "SELECT set_config('app.user_id', '0', true),"
            "       set_config('app.club_id', '0', true),"
            "       set_config('app.club_role', '', true)"
        )
    )

    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text("DELETE FROM organizations WHERE name = 'rosterprobe'"))
    conn.execute(
        sa.text(
            "DELETE FROM users WHERE login IN"
            " ('migration.rosterowner', 'migration.rosterstaff') AND kind = 'staff'"
        )
    )
    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))

    if seen != 2:
        raise RuntimeError(
            f"OWNER xodimlar ro'yxatini to'liq ko'rmadi (kutilgan 2, ko'rindi {seen}) — "
            "users_staff_roster policy'si ishlamayapti"
        )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
