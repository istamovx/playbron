"""Smena — xodim kassa ochish/yopish, qo'lda kirim/chiqim.

Loyiha egasining so'rovi (2026-08-16): "Smena" ekrani (`shift.tsx`)
to'liq dekorativ edi — "Kirim"/"Chiqim"/"Smenani yopish" tugmalarida
`onClick` UMUMAN yo'q edi (jonli sinovda topilgan — bosganda hech narsa
bo'lmasdi). Backend'da `shift` tushunchasi butunlay yo'q edi.

Ikkita jadval:
  * `shifts`         — bitta ochiq/yopiq smena: kim, qachon ochdi,
                        boshlang'ich kassa, sanalgan kassa (yopilganda).
  * `shift_cash_movements` — smena davomida qo'lda kiritilgan kirim/chiqim
                        (masalan kuryer to'lovi, mahsulot yetkazib berish
                        haqi) — bron hisob-kitobidan TASHQARI harakatlar.
                        Bron naqd to'lovlari (`bookings.paid_amount`)
                        ALLAQACHON bor (`0013_pos.py`) — bu yerda
                        TAKRORLANMAYDI, "kutilayotgan naqd" hisoblanganda
                        ikkalasi birlashtiriladi (`finance/shifts.py`).

Bitta xodim BIR VAQTDA faqat bitta ochiq smenaga ega bo'lishi mumkin —
qisman unikal indeks (`status='open'` bo'yicha).

Ruxsat — `staff/router.py`dagi bilan bir xil ruh: xodim FAQAT o'z
smenasini boshqaradi, OWNER/ADMIN esa klubning BARCHA smenalarini
ko'radi/boshqaradi (nazorat/tuzatish uchun).

Revision ID: 0021_shifts
Revises: 0020_expenses
"""

import sqlalchemy as sa
from alembic import op

revision = "0021_shifts"
down_revision = "0020_expenses"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"


def upgrade() -> None:
    _tables()
    _rls()
    _grants()
    _self_test()


def _tables() -> None:
    op.create_table(
        "shifts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("staff_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("opening_cash", sa.BigInteger, nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counted_cash", sa.BigInteger, nullable=True),
        sa.Column("closed_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.CheckConstraint("opening_cash >= 0", name="shifts_opening_cash_nonneg_ck"),
        sa.CheckConstraint("counted_cash IS NULL OR counted_cash >= 0", name="shifts_counted_cash_nonneg_ck"),
        sa.CheckConstraint("status IN ('open', 'closed')", name="shifts_status_ck"),
    )
    op.create_index("shifts_club_ix", "shifts", ["club_id"])
    # Bitta xodim bir vaqtda bitta ochiq smena — qisman unikal indeks
    # (faqat `status='open'` qatorlarga taalluqli, yopilganlar cheklanmaydi).
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX shifts_staff_one_open_uk ON shifts (staff_id)"
            " WHERE status = 'open'"
        )
    )

    op.create_table(
        "shift_cash_movements",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        # `club_id` qatorda takrorlanadi — RLS'ni `shifts`ga JOIN'siz
        # qo'llash uchun (`order_items`dagi bilan bir xil naqsh).
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "shift_id", sa.BigInteger, sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("kind", sa.String(8), nullable=False),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('IN', 'OUT')", name="shift_cash_movements_kind_ck"),
        sa.CheckConstraint("amount > 0", name="shift_cash_movements_amount_positive_ck"),
    )
    op.create_index("shift_cash_movements_shift_ix", "shift_cash_movements", ["shift_id"])
    op.create_index("shift_cash_movements_club_ix", "shift_cash_movements", ["club_id"])


def _rls() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE shifts ENABLE ROW LEVEL SECURITY;
            ALTER TABLE shifts FORCE ROW LEVEL SECURITY;
            ALTER TABLE shift_cash_movements ENABLE ROW LEVEL SECURITY;
            ALTER TABLE shift_cash_movements FORCE ROW LEVEL SECURITY;

            -- Xodim FAQAT o'z smenasini ko'radi/boshqaradi, OWNER/ADMIN esa
            -- klubning BARCHA smenalarini (nazorat/tuzatish — masalan xodim
            -- smenani yopishni unutib ketsa).
            CREATE POLICY shifts_own_or_admin ON shifts FOR ALL
                USING (club_id = app_club_id()
                       AND (staff_id = app_user_id()
                            OR app_club_role(app_club_id()) IN ('OWNER', 'ADMIN')))
                WITH CHECK (club_id = app_club_id()
                            AND (staff_id = app_user_id()
                                 OR app_club_role(app_club_id()) IN ('OWNER', 'ADMIN')));

            -- Harakatlar — o'sha smenaning egasi YOKI OWNER/ADMIN. Bevosita
            -- `shifts`ga JOIN qilinmaydi (RLS ichida RLS'ga tayanish xavfli
            -- — buning o'rniga xuddi shifts'dagi bilan bir xil shart
            -- `club_id`+rol orqali takrorlanadi).
            CREATE POLICY shift_cash_movements_own_or_admin ON shift_cash_movements FOR ALL
                USING (club_id = app_club_id()
                       AND (created_by = app_user_id()
                            OR app_club_role(app_club_id()) IN ('OWNER', 'ADMIN')
                            OR EXISTS (SELECT 1 FROM shifts s
                                       WHERE s.id = shift_cash_movements.shift_id
                                         AND s.staff_id = app_user_id())))
                WITH CHECK (club_id = app_club_id()
                            AND (created_by = app_user_id()
                                 OR app_club_role(app_club_id()) IN ('OWNER', 'ADMIN')));
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            GRANT SELECT, INSERT, UPDATE ON shifts, shift_cash_movements TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE shifts_id_seq TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE shift_cash_movements_id_seq TO {APP_ROLE};
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
    """OWNER/xodimning o'zi ishlaydi, boshqa STAFF'ning smenasini
    BOSHQA STAFF ko'ra olmasligi kerak (faqat OWNER/ADMIN yoki egasi)."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "clubs", "memberships", "shifts", "shift_cash_movements")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'shifts.probe.owner', 'active', 'Owner') RETURNING id"
            )
        ).scalar_one()
        staff_a_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'shifts.probe.staffa', 'active', 'Staff A') RETURNING id"
            )
        ).scalar_one()
        staff_b_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'shifts.probe.staffb', 'active', 'Staff B') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Shifts Probe Org', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Shifts Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        for uid, role in ((owner_id, "OWNER"), (staff_a_id, "STAFF"), (staff_b_id, "STAFF")):
            conn.execute(
                sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, :r)"),
                {"u": uid, "c": club_id, "r": role},
            )
    finally:
        _force_rls(conn, scoped, enabled=True)

    shift_id: int | None = None
    try:
        # STAFF A o'z smenasini ochadi
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(staff_a_id)})
        conn.execute(sa.text("SELECT set_config('app.club_id', :c, true)"), {"c": str(club_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'STAFF', true)"))

        shift_id = conn.execute(
            sa.text(
                "INSERT INTO shifts (club_id, staff_id, opening_cash) VALUES (:club, :staff, 200000)"
                " RETURNING id"
            ),
            {"club": club_id, "staff": staff_a_id},
        ).scalar_one()

        a_sees_own = conn.execute(
            sa.text("SELECT count(*) FROM shifts WHERE id = :id"), {"id": shift_id}
        ).scalar_one()
        if a_sees_own != 1:
            raise RuntimeError("shifts_own_or_admin: STAFF A o'z smenasini ko'rmadi")

        # STAFF B — STAFF A'ning smenasini ko'RMASLIGI kerak
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(staff_b_id)})

        b_sees_a = conn.execute(
            sa.text("SELECT count(*) FROM shifts WHERE id = :id"), {"id": shift_id}
        ).scalar_one()
        if b_sees_a != 0:
            raise RuntimeError(
                "shifts_own_or_admin: STAFF B boshqa xodimning smenasini ko'rib qoldi — xavfli"
            )

        # OWNER — BARCHA smenani ko'rishi kerak (nazorat)
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(owner_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'OWNER', true)"))

        owner_sees = conn.execute(
            sa.text("SELECT count(*) FROM shifts WHERE id = :id"), {"id": shift_id}
        ).scalar_one()
        if owner_sees != 1:
            raise RuntimeError("shifts_own_or_admin: OWNER xodim smenasini ko'ra olmadi")

        # OWNER kirim/chiqim yoza olishi kerak (nazorat/tuzatish)
        movement_id = conn.execute(
            sa.text(
                "INSERT INTO shift_cash_movements (club_id, shift_id, kind, amount, reason, created_by)"
                " VALUES (:club, :shift, 'OUT', 35000, 'probe', :by) RETURNING id"
            ),
            {"club": club_id, "shift": shift_id, "by": owner_id},
        ).scalar_one()

        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(staff_a_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'STAFF', true)"))
        a_sees_movement = conn.execute(
            sa.text("SELECT count(*) FROM shift_cash_movements WHERE id = :id"), {"id": movement_id}
        ).scalar_one()
        if a_sees_movement != 1:
            raise RuntimeError(
                "shift_cash_movements_own_or_admin: smena egasi OWNER kiritgan harakatni ko'rmadi"
            )

        conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_role', '', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        if shift_id is not None:
            conn.execute(sa.text("DELETE FROM shift_cash_movements WHERE club_id = :c"), {"c": club_id})
            conn.execute(sa.text("DELETE FROM shifts WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM memberships WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:o, :a, :b)"),
            {"o": owner_id, "a": staff_a_id, "b": staff_b_id},
        )
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
