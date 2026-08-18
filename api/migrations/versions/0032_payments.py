"""To'lov qatlami — pul harakati alohida entity sifatida.

Manba: `docs/audit-report.md` §2.3 va 5-bo'lim 1-bosqichi.

## Nima buzilgan edi

To'lov `bookings` ustunlari edi (`paid_amount`, `payment_method`,
`closed_by`, `closed_at`), smena kassasi esa ularni **vaqt oynasi** bilan
topardi: «shu xodim shu oraliqda yopgan bronlar». `shift_id` yo'q edi.
Uchta oqibat:

  * **Bronsiz sotuv umuman ko'rinmasdi.** `orders.booking_id` NULL bo'lishi
    mumkin, `orders`da esa to'lov ustuni YO'Q — o'tkinchi mijozning naqd
    puli hisobotga tushardi, kassaga esa tushmasdi.
  * **Naqd xarajat kassadan yechilmasdi** — `expenses`da `shift_id` yo'q edi.
  * **Smenasiz yopilgan hisob yetim qolardi** — hech qaysi smenaga tegishli
    bo'lmasdi.

## Nima qilinadi

  * `payments` — har bir pul harakati bitta qator. Smenaga FK bilan
    bog'lanadi, taxminiy vaqt oynasi bilan emas.
  * `bookings.discount_amount` / `debt_amount` — hisoblangan summa bilan
    olingan summa farqi endi SABABI bilan yoziladi (loyiha egasining
    qarori, 2026-08-17: xodim chegirma yoki qarzni o'zi tanlaydi).
    Invariant: `paid + discount + debt = total`.
  * `expenses.shift_id` / `method` — naqd xarajat kassadan yechiladi.
  * Mavjud yopilgan bronlar `payments`ga ko'chiriladi (`shift_id` NULL —
    tarixiy yozuvlar uchun u noma'lum va hech qachon bilinmaydi).

## Backfill va RLS

Ko'chirish `_rls()`dan OLDIN bajariladi va `bookings` uchun FORCE vaqtincha
olinadi. Aks holda: migratsiya EGASI ham FORCE RLS ostida qoladi, mos
GUC yo'q, `SELECT ... FROM bookings` JIMGINA 0 qator qaytaradi va
ko'chirish "muvaffaqiyatli" tugaydi — lokal superuser'da esa hammasi
ishlagandek ko'rinadi (`docs/HOLAT.md` §4.1). `_self_test()` ko'chirilgan
sonni tekshiradi.

Revision ID: 0032_payments
Revises: 0031_stations_bot_lookup
"""

import sqlalchemy as sa
from alembic import op

revision = "0032_payments"
down_revision = "0031_stations_bot_lookup"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"

KINDS = ("FINAL", "REFUND")
METHODS = ("CASH", "TRANSFER")


def upgrade() -> None:
    _tables()
    _booking_columns()
    _expense_columns()
    _backfill()
    _rls()
    _grants()
    _self_test()


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")


def _tables() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        # Naqd to'lov MAJBURIY ravishda smenaga tegishli (servis qatlami
        # buni talab qiladi). O'tkazma smenasiz ham bo'lishi mumkin, tarixiy
        # yozuvlarda esa umuman noma'lum — shuning uchun ustun nullable.
        # SET NULL — klub o'chirilganda `shifts` va `payments` bir vaqtda
        # kaskadga tushadi; oddiy (NO ACTION) FK o'chirish tartibiga qarab
        # to'sib qo'yishi mumkin edi. To'lov yozuvi smenasiz ham ma'noli.
        sa.Column(
            "shift_id",
            sa.BigInteger,
            sa.ForeignKey("shifts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # CASCADE — SET NULL emas: aks holda bron o'chganda `payments_target_ck`
        # buzilardi (ikkala havola ham NULL bo'lib qolardi).
        sa.Column(
            "booking_id",
            sa.BigInteger,
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "order_id",
            sa.BigInteger,
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(8), nullable=False, server_default="FINAL"),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("amount", sa.BigInteger, nullable=False),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(f"kind IN {KINDS}", name="payments_kind_ck"),
        sa.CheckConstraint(f"method IN {METHODS}", name="payments_method_ck"),
        sa.CheckConstraint("amount > 0", name="payments_amount_positive_ck"),
        # To'lov ALBATTA biror narsaga tegishli va faqat bittasiga —
        # "havolasiz pul" hisobotdan ham, kassadan ham tushib qolardi.
        sa.CheckConstraint(
            "(booking_id IS NOT NULL) <> (order_id IS NOT NULL)",
            name="payments_target_ck",
        ),
    )
    op.create_index("payments_club_ix", "payments", ["club_id"])
    op.create_index("payments_shift_ix", "payments", ["shift_id"])
    op.create_index("payments_booking_ix", "payments", ["booking_id"])
    op.create_index("payments_order_ix", "payments", ["order_id"])
    op.create_index("payments_club_created_ix", "payments", ["club_id", "created_at"])


def _booking_columns() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE bookings
                ADD COLUMN discount_amount bigint NOT NULL DEFAULT 0,
                ADD COLUMN debt_amount     bigint NOT NULL DEFAULT 0,
                -- Mijoz hisobdan KO'P bergan va qaytimni olmagan qismi.
                -- Rad etilsa xodim kassadagi haqiqiy pulni kam ko'rsatishga
                -- majbur bo'lardi va smena farqi tushuntirib bo'lmas edi —
                -- ya'ni butun `payments` ishining maqsadi buzilardi.
                ADD COLUMN tip_amount      bigint NOT NULL DEFAULT 0;

            ALTER TABLE bookings
                ADD CONSTRAINT bookings_discount_nonneg_ck CHECK (discount_amount >= 0),
                ADD CONSTRAINT bookings_debt_nonneg_ck     CHECK (debt_amount >= 0),
                ADD CONSTRAINT bookings_tip_nonneg_ck      CHECK (tip_amount >= 0);
            """
        )
    )


def _expense_columns() -> None:
    op.execute(
        sa.text(
            """
            -- Naqd xarajat kassadan yechiladi; bank orqali to'langani
            -- yechilmaydi. Eski qatorlar uchun NULL = "noma'lum, kassaga
            -- tegmaydi" (retroaktiv taxmin qilinmaydi).
            -- ON DELETE SET NULL — `payments.shift_id` bilan BIR XIL sabab:
            -- klub o'chirilganda `shifts` ham, unga havola qiluvchi qatorlar
            -- ham kaskadga tushadi va oddiy (NO ACTION) FK o'chirish
            -- tartibiga qarab to'sib qo'yishi mumkin.
            ALTER TABLE expenses
                ADD COLUMN shift_id bigint REFERENCES shifts(id) ON DELETE SET NULL,
                ADD COLUMN method   text;

            ALTER TABLE expenses
                ADD CONSTRAINT expenses_method_ck
                CHECK (method IS NULL OR method IN ('CASH', 'TRANSFER'));
            """
        )
    )
    op.create_index("expenses_shift_ix", "expenses", ["shift_id"])


def _scoped_force(conn: sa.Connection, tables: tuple[str, ...], *, enabled: bool) -> None:
    verb = "FORCE" if enabled else "NO FORCE"
    for table in tables:
        conn.execute(sa.text(f"ALTER TABLE {table} {verb} ROW LEVEL SECURITY"))


def _exempt(conn: sa.Connection) -> bool:
    return bool(
        conn.execute(
            sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    )


CLOSED_BOOKING_FILTER = (
    " WHERE closed_at IS NOT NULL AND closed_by IS NOT NULL"
    "   AND payment_method IS NOT NULL AND paid_amount IS NOT NULL AND paid_amount > 0"
)

BACKFILL_SQL = (
    "INSERT INTO payments (club_id, booking_id, kind, method, amount, created_by, created_at)"
    " SELECT club_id, id, 'FINAL', payment_method, paid_amount, closed_by, closed_at"
    " FROM bookings" + CLOSED_BOOKING_FILTER
)


def _backfill() -> None:
    """Yopilgan bronlarni `payments`ga ko'chiradi.

    `payments`da hali RLS yo'q (`_rls()` keyinroq), lekin `bookings`da BOR
    va u migratsiya egasiga ham tegishli — shuning uchun O'QISH uchun FORCE
    vaqtincha olinadi.
    """
    conn = op.get_bind()
    exempt = _exempt(conn)
    if not exempt:
        _scoped_force(conn, ("bookings",), enabled=False)
    try:
        conn.execute(sa.text(BACKFILL_SQL))
    finally:
        if not exempt:
            _scoped_force(conn, ("bookings",), enabled=True)


def _rls() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
            ALTER TABLE payments FORCE  ROW LEVEL SECURITY;

            -- `orders`/`bookings`dagi bilan bir xil shakl: butun xodim
            -- to'lov yozadi va ko'radi, faqat o'z klubida.
            CREATE POLICY payments_staff_all ON payments FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'));

            -- Super admin hisobotlari uchun (`0015`/`0029` naqshi) —
            -- BYPASSRLS'siz muhitda ham ishlaydi.
            CREATE POLICY payments_platform_read ON payments
                FOR SELECT USING (app_platform());

            -- `expenses` uchun YAGONA policy `expenses_owner_admin_all`
            -- (`0020`) — OWNER/ADMIN. Endi esa smena kassasi naqd
            -- xarajatlarni AYIRADI (`finance/shifts.py::_expected_cash()`),
            -- ya'ni oddiy STAFF o'z smenasini ochganda o'sha SELECT unga
            -- JIMGINA 0 qaytarardi: xodim 100 000 ko'rardi, ega esa
            -- 75 000 — va smena yopilganda xodim aynan xarajat summasiga
            -- "kam" bo'lib chiqardi. Shuning uchun xodimga FAQAT O'Z
            -- smenasiga bog'langan xarajat qatorini O'QISH ochiladi.
            CREATE POLICY expenses_own_shift_read ON expenses FOR SELECT
                USING (
                    club_id = app_club_id()
                    AND shift_id IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM shifts s
                        WHERE s.id = expenses.shift_id
                          AND s.staff_id = app_user_id()
                    )
                );
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            GRANT SELECT, INSERT ON payments TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE payments_id_seq TO {APP_ROLE};
            GRANT SELECT ON payments TO {PLATFORM_ROLE};
            """
        )
    )


def _self_test() -> None:
    """Ikki narsa tekshiriladi:

    1. Ko'chirish HAQIQATAN ishladi — yopilgan bronlar soni bilan
       ko'chirilgan to'lovlar soni mos.
    2. `payments` tenant bo'yicha izolyatsiyalangan — GUC'siz bo'sh.
    """
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("bookings", "payments")
    _scoped_force(conn, scoped, enabled=False)
    try:
        expected = conn.execute(
            sa.text("SELECT count(*) FROM bookings" + CLOSED_BOOKING_FILTER)
        ).scalar_one()
        migrated = conn.execute(sa.text("SELECT count(*) FROM payments")).scalar_one()
    finally:
        _scoped_force(conn, scoped, enabled=True)

    if expected != migrated:
        raise RuntimeError(
            f"payments ko'chirish to'liq emas: bookings={expected}, payments={migrated} — "
            "ehtimol backfill RLS tomonidan jimgina filtrlangan"
        )

    # GUC yo'q — izolyatsiya ishlayotgan bo'lsa hech nima ko'rinmasligi kerak.
    blind = conn.execute(sa.text("SELECT count(*) FROM payments")).scalar_one()
    if blind != 0:
        raise RuntimeError(
            f"payments_staff_all izolyatsiya qilmadi — GUC'siz {blind} qator ko'rindi"
        )
