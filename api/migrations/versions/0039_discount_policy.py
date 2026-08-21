"""Xodim chegirmasining yuqori chegarasi — `clubs.staff_max_discount_percent`.

Rol auditi topilmasi (2026-08-18): `pos/service.py::close_bill()` da
oddiy `STAFF` roli `paid_amount = 0` va `shortfall_reason = 'DISCOUNT'`
bilan istalgan hisobni TO'LIQ nolga yopa olardi. Chegirmaga na chegara,
na ADMIN tasdig'i bor edi — ya'ni kassadagi har bir xodim summasi
cheklanmagan "chegirma" tugmasiga ega edi.

Chegara KLUB SOZLAMASI sifatida saqlanadi (kodda konstanta emas):
tungi klub bilan bolalar markazining siyosati bir xil bo'lishi shart
emas, va bu qiymatni o'zgartirish uchun deploy kutib o'tirilmaydi.
Sukut 20% — mavjud klublarga ham shu qiymat tushadi.

`OWNER`/`ADMIN` bu chegaradan TASHQARIDA: chegirma ularning biznes
qarori, xodimniki esa emas (`api/src/playbron/modules/pos/service.py`).

## Nega `smallint` va nega foiz

Foiz — pul emas, shuning uchun `bigint` invariantiga tegishli emas.
Absolut summa (masalan "20 000 so'mgacha") o'rniga foiz tanlandi: klub
narxi ko'tarilganda absolut chegara jimgina ma'nosiz bo'lib qolardi.

Revision ID: 0039_discount_policy
Revises: 0038_booking_reminders
"""

import sqlalchemy as sa
from alembic import op

revision = "0039_discount_policy"
down_revision = "0038_booking_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _schema()
    _self_test()


def _schema() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE clubs
                ADD COLUMN staff_max_discount_percent smallint NOT NULL DEFAULT 20;

            ALTER TABLE clubs
                ADD CONSTRAINT clubs_staff_discount_pct_ck
                    CHECK (staff_max_discount_percent BETWEEN 0 AND 100);
            """
        )
    )


def _scoped_force(conn: sa.Connection, tables: tuple[str, ...], *, enabled: bool) -> None:
    verb = "FORCE" if enabled else "NO FORCE"
    for table in tables:
        conn.execute(sa.text(f"ALTER TABLE {table} {verb} ROW LEVEL SECURITY"))


def _self_test() -> None:
    """Konstreynt HAQIQATAN to'sadimi — chegaradan tashqari qiymat yozib ko'riladi.

    Klub SHU YERDA yaratiladi (`0033` naqshi): mavjud qatorni qidirish toza
    bazada probe'ni JIMGINA o'tkazib yuborardi — aynan `check_render_shape.py`
    ishlatadigan bazada.

    Rad etish tranzaksiyani ABORT qiladi, shuning uchun har urinish alohida
    SAVEPOINT ichida — aks holda Alembic'ning `UPDATE alembic_version`
    bayonoti ham "current transaction is aborted" bilan yiqilardi.
    """
    conn = op.get_bind()
    scoped = ("users", "organizations", "clubs")
    _scoped_force(conn, scoped, enabled=False)
    owner_id = org_id = club_id = None
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'discount.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:u, 'Discount Probe Org', 'active') RETURNING id"
            ),
            {"u": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Discount Probe Club', 'draft') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()

        default_pct = conn.execute(
            sa.text("SELECT staff_max_discount_percent FROM clubs WHERE id = :c"),
            {"c": club_id},
        ).scalar_one()
        if default_pct != 20:
            raise RuntimeError(f"staff_max_discount_percent sukuti 20 emas — {default_pct}")

        for bad in (101, -1):
            savepoint = conn.begin_nested()
            try:
                conn.execute(
                    sa.text("UPDATE clubs SET staff_max_discount_percent = :p WHERE id = :c"),
                    {"p": bad, "c": club_id},
                )
            except sa.exc.DBAPIError as exc:
                savepoint.rollback()
                # Aynan CHECK rad etdimi — boshqa xatoni "himoya ishladi"
                # deb hisoblash probe'ni ma'nosiz qilardi.
                if getattr(exc.orig, "sqlstate", None) != "23514":
                    raise
            else:
                savepoint.rollback()
                raise RuntimeError(
                    f"clubs_staff_discount_pct_ck {bad} qiymatini o'tkazib yubordi"
                )
    finally:
        if club_id is not None:
            conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        if org_id is not None:
            conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        if owner_id is not None:
            conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        _scoped_force(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
