"""Ochiq smena unikalligi klub kesimiga o'tkazildi.

`0021` dagi `shifts_staff_one_open_uk` indeksi `staff_id` bo'yicha GLOBAL
edi — `memberships` esa bir xodimning bir nechta klubda ishlashini ataylab
qo'llab-quvvatlaydi. Natijada ikki klubda ishlaydigan xodim ikkinchi
klubda smena ocholmasdi (CLAUDE.md §«Ma'lum texnik qarz»dagi band).

Indeks `(club_id, staff_id) WHERE status = 'open'` ga almashtiriladi:
bitta klubda bitta ochiq smena qoladi, boshqa klubda parallel ochiq smena
endi mumkin. Nom o'zgarmaydi — servis xatoni sqlstate `23505` bo'yicha
ushlaydi (`finance/shifts.py::open_shift`), indeks nomiga bog'lanmagan.

Revision ID: 0033_shift_per_club_uk
Revises: 0032_payments
"""

import sqlalchemy as sa
from alembic import op

revision = "0033_shift_per_club_uk"
down_revision = "0032_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "DROP INDEX shifts_staff_one_open_uk;"
            " CREATE UNIQUE INDEX shifts_staff_one_open_uk"
            " ON shifts (club_id, staff_id) WHERE status = 'open'"
        )
    )
    _self_test()


def _force_rls(conn: sa.Connection, tables: tuple[str, ...], *, enabled: bool) -> None:
    verb = "FORCE" if enabled else "NO FORCE"
    for table in tables:
        conn.execute(sa.text(f"ALTER TABLE {table} {verb} ROW LEVEL SECURITY"))


def _self_test() -> None:
    """Indeks invariantini ikkala yo'nalishda buzishga urinadi.

    Unikal indeks rolga qaramaydi, shuning uchun test superuser'da ham,
    render-shape'da ham to'liq yuradi — `_exempt()` guard'i yo'q. Kutilgan
    buzilishlar SAVEPOINT ichida sinaladi: aks holda IntegrityError butun
    migratsiya tranzaksiyasini bekor qilib yuborardi.
    """
    conn = op.get_bind()

    scoped = ("users", "organizations", "clubs", "shifts")
    _force_rls(conn, scoped, enabled=False)
    staff_id = org_id = club_a = club_b = None
    try:
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'shiftuk.probe.staff', 'active', 'Probe') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'ShiftUK Probe Org', 'active') RETURNING id"
            ),
            {"o": staff_id},
        ).scalar_one()
        club_a = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'ShiftUK Probe A', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        club_b = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'ShiftUK Probe B', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()

        conn.execute(
            sa.text("INSERT INTO shifts (club_id, staff_id, opening_cash) VALUES (:c, :s, 0)"),
            {"c": club_a, "s": staff_id},
        )

        # 1. Ikkinchi klubda parallel ochiq smena — endi O'TISHI kerak
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                sa.text("INSERT INTO shifts (club_id, staff_id, opening_cash) VALUES (:c, :s, 0)"),
                {"c": club_b, "s": staff_id},
            )
        except sa.exc.IntegrityError as exc:
            savepoint.rollback()
            raise RuntimeError(
                "shifts_staff_one_open_uk: ikkinchi klubdagi smena hali ham bloklanadi —"
                " indeks club_id'siz qolgan"
            ) from exc
        else:
            savepoint.commit()

        # 2. Bitta klubda ikkinchi ochiq smena — RAD ETILISHI kerak
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                sa.text("INSERT INTO shifts (club_id, staff_id, opening_cash) VALUES (:c, :s, 0)"),
                {"c": club_a, "s": staff_id},
            )
        except sa.exc.IntegrityError:
            savepoint.rollback()  # kutilgan
        else:
            savepoint.commit()
            raise RuntimeError(
                "shifts_staff_one_open_uk: bitta klubda ikkita ochiq smena o'tib ketdi"
            )

        # 3. Yopilgan smena cheklanmaydi (`WHERE status='open'` saqlangan)
        conn.execute(
            sa.text(
                "INSERT INTO shifts (club_id, staff_id, opening_cash, status, closed_at)"
                " VALUES (:c, :s, 0, 'closed', now())"
            ),
            {"c": club_a, "s": staff_id},
        )
    finally:
        if club_a is not None:
            conn.execute(
                sa.text("DELETE FROM shifts WHERE club_id IN (:a, :b)"),
                {"a": club_a, "b": club_b},
            )
            conn.execute(
                sa.text("DELETE FROM clubs WHERE id IN (:a, :b)"), {"a": club_a, "b": club_b}
            )
        if org_id is not None:
            conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        if staff_id is not None:
            conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": staff_id})
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")
