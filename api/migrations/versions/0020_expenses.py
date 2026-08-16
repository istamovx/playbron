"""Xarajatlar — klub darajasidagi qo'lda kiritiladigan xarajat qatorlari.

Loyiha egasining so'rovi (2026-08-16, reja #18): admin konsoldagi
"Xarajatlar" ekrani hozircha to'liq `useClub()` mock do'konidan
(`playbron.club` localStorage kaliti) ishlaydi — real bazada jadval
umuman yo'q edi. Ishga tushirishdan oldin bu oxirgi to'liq-mock domenlar
qatoridan biri (`docs/00-audit.md` §UI→data xaritasi).

Sxema — `docs/01-architecture.md` §domain_model ERD'siga AYNAN mos
(`id, club_id, spent_on(date), category, amount, note`), ustiga ikkita
qo'shimcha: `created_by` (`docs/00-audit.md` data model jadvali — kim
kiritganini bilish uchun, klub egasi xodim harakatini ko'rishi kerak
degan talab bilan bir xil ruh) va `status` (`products`dagi bilan bir xil
naqsh — noto'g'ri kiritilgan xarajat ARXIVGA o'tadi, HECH QACHON o'chmaydi:
loyiha egasining qat'iy talabi — "hech qachon qo'shilgan ma'lumot
yo'qolmasligi kerak"). Shu sabab `APP_ROLE`ga DELETE grant UMUMAN
berilmaydi — arxivlash yagona "o'chirish" yo'li.

**Ruxsat matritsasi — `docs/01-architecture.md`:186 dagi jadval bilan
AYNAN bir xil**: "Xarajatlar | ∑ | A | A | — | —" — o'qish HAM, yozish HAM
faqat OWNER/ADMIN. STAFF bu yerda `products_read`dagidek qisman kirish
OLMAYDI — butunlay chetda (bitta `FOR ALL` policy, ikkinchi `_read`
policy yo'q). Bu — self-test'da ATAYLAB tekshiriladigan qism, chunki
noto'g'ri yozilgan policy STAFF'ga xarajatlarni "jimgina" ochib qo'yishi
mumkin edi (`[[playbron-rls-cross-table-subquery-gap]]` bilan bir xil
sinf xato — ko'rinmas ruxsat teshigi).

Revision ID: 0020_expenses
Revises: 0019_staff_update
"""

import sqlalchemy as sa
from alembic import op

revision = "0020_expenses"
down_revision = "0019_staff_update"
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
        "expenses",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        # `date`, timestamptz EMAS — bu chek/kvitansiya sanasi, aniq vaqt
        # emas (ERD'dagi bilan bir xil: `docs/01-architecture.md:447`).
        sa.Column("spent_on", sa.Date, nullable=False),
        # Erkin matn — `products.category` bilan bir xil falsafa (DB CHECK
        # yo'q, ro'yxat frontendda saqlanadi, kengaytirish migratsiya
        # so'ramaydi).
        sa.Column("category", sa.String(32), nullable=False, server_default="Boshqa"),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="expenses_amount_positive_ck"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="expenses_status_ck"),
    )
    op.create_index("expenses_club_ix", "expenses", ["club_id"])
    # Hisobot davr bo'yicha filtrlaydi (`spent_on BETWEEN`) — tarkib
    # ustuni indeksga qo'shiladi, faqat `club_id` yetarli emas.
    op.create_index("expenses_club_spent_on_ix", "expenses", ["club_id", "spent_on"])


def _rls() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE expenses ENABLE ROW LEVEL SECURITY;
            ALTER TABLE expenses FORCE ROW LEVEL SECURITY;

            -- Bitta policy, o'qish HAM yozish HAM shu ichida — STAFF uchun
            -- alohida `_read` YO'Q (`products`dan farqi shu — u yerda xodim
            -- ko'radi, bu yerda ko'rmaydi, spec talabi).
            CREATE POLICY expenses_owner_admin_all ON expenses FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'));
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            -- DELETE ATAYLAB yo'q — arxivlash (`status='archived'`) yagona
            -- "o'chirish" yo'li, qator hech qachon jismoniy o'chmaydi.
            GRANT SELECT, INSERT, UPDATE ON expenses TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE expenses_id_seq TO {APP_ROLE};
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
    """OWNER/ADMIN to'liq ishlaydi, STAFF esa BUTUNLAY ko'rmaydi (0 qator,
    xato emas — `products_read`dan farqli, bu yerda STAFF uchun hech qanday
    policy yo'q).

    `0019`dagi bilan FARQLI naqsh: bu yerda tekshirilayotgan narsa xom
    jadval RLS'i (SECURITY DEFINER funksiya EMAS), ya'ni sinov faqat
    haqiqatan RLS majburlanadigan ulanishda ma'noli — mahalliy superuser/
    BYPASSRLS uni butunlay chetlab o'tadi (`_force_rls` bunga yordam
    bermaydi, FORCE ham superuser/BYPASSRLS'ga taalluqli emas). Shu sabab
    `0016`/`0017`/`0018` bilan bir xil: **exempt bo'lsa sinov butunlay
    o'tkazib yuboriladi**, faqat Render shaklidagi (NOBYPASSRLS) muhitda
    real ishlaydi."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "clubs", "memberships", "expenses")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'expenses.probe.owner', 'active', 'Owner') RETURNING id"
            )
        ).scalar_one()
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'expenses.probe.staff', 'active', 'Staff') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Expenses Probe Org', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Expenses Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        for uid, role in ((owner_id, "OWNER"), (staff_id, "STAFF")):
            conn.execute(
                sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, :r)"),
                {"u": uid, "c": club_id, "r": role},
            )
    finally:
        _force_rls(conn, scoped, enabled=True)

    expense_id: int | None = None
    try:
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(owner_id)})
        conn.execute(sa.text("SELECT set_config('app.club_id', :c, true)"), {"c": str(club_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'OWNER', true)"))

        expense_id = conn.execute(
            sa.text(
                "INSERT INTO expenses (club_id, spent_on, category, amount, note, created_by)"
                " VALUES (:club, current_date, 'Elektr', 150000, 'probe', :by) RETURNING id"
            ),
            {"club": club_id, "by": owner_id},
        ).scalar_one()

        owner_sees = conn.execute(
            sa.text("SELECT count(*) FROM expenses WHERE id = :id"), {"id": expense_id}
        ).scalar_one()
        if owner_sees != 1:
            raise RuntimeError("expenses_owner_admin_all: OWNER o'z xarajatini ko'rmadi")

        updated = conn.execute(
            sa.text("UPDATE expenses SET status = 'archived' WHERE id = :id"), {"id": expense_id}
        )
        if updated.rowcount != 1:
            raise RuntimeError("expenses_owner_admin_all: OWNER arxivlay olmadi")

        # STAFF — BUTUNLAY ko'rmasligi kerak (spec: "—", `products`dagi
        # qisman kirish emas).
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(staff_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'STAFF', true)"))

        staff_sees = conn.execute(
            sa.text("SELECT count(*) FROM expenses WHERE id = :id"), {"id": expense_id}
        ).scalar_one()
        if staff_sees != 0:
            raise RuntimeError("expenses_owner_admin_all: STAFF xarajatni ko'rib qoldi — xavfli")

        conn.execute(sa.text("SAVEPOINT staff_write_probe"))
        blocked = False
        try:
            conn.execute(
                sa.text(
                    "INSERT INTO expenses (club_id, spent_on, category, amount, created_by)"
                    " VALUES (:club, current_date, 'Boshqa', 1000, :by)"
                ),
                {"club": club_id, "by": staff_id},
            )
        except Exception as exc:  # noqa: BLE001
            blocked = True
            del exc
        finally:
            conn.execute(sa.text("ROLLBACK TO SAVEPOINT staff_write_probe"))
        if not blocked:
            raise RuntimeError("expenses_owner_admin_all: STAFF yangi xarajat yoza oldi — xavfli")

        conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_role', '', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        if expense_id is not None:
            conn.execute(sa.text("DELETE FROM expenses WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM memberships WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:o, :s)"), {"o": owner_id, "s": staff_id}
        )
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
