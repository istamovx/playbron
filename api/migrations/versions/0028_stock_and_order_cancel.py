"""Mahsulot qoldig'i + buyurtmani bekor qilish.

Loyiha egasining ikki so'rovi (2026-08-16):

  2) "Mahsulot qo'shish qismida aytgan edim. Biror mahsulot qo'shganda
     sonini ham kiritishi kerak." → `products.stock_qty`.
  7) "Xodim buyurtma kiritganda uni bekor qilishi ham mumkin. Bu yangi
     bo'lgan qiymatida mumkin faqat." → `orders.status`ga `CANCELLED`
     qiymati (faqat `NEW`dan o'tish mumkin — bu QOIDA ilova qatlamida,
     `pos/service.py::cancel_order()`da).

Bu reja #21 (to'liq inventar: tannarx, kirim/chiqim harakati, hisobot)
NING O'RNINI BOSMAYDI — u kattaroq ish va alohida qoladi. Bu yerda
faqat eng kerakli qism: qancha qolganini KO'RSATISH va sotuvda
kamaytirish. `stock_qty` NOT NULL DEFAULT 0 — mavjud mahsulotlar
"0 dona" bo'lib qoladi, bu ROSTGO'Y (hech kim hali kiritmagan) va
sotuvni bloklamaydi (pastdagi izohga qarang).

MUHIM: qoldiq sotuvni BLOKLAMAYDI. Klub bar mahsulotini hisobga olmay
sotayotgan bo'lishi mumkin; qoldiq 0 bo'lgani uchun xodimni kassada
to'xtatib qo'yish real ishni buzardi. Qoldiq faqat kuzatuv uchun —
manfiyga ham tushaveradi (CHECK YO'Q), bu "hisobga olinmagan" holatning
rost ko'rsatkichi bo'ladi.

Revision ID: 0028_stock_order_cancel
Revises: 0027_bookings_avail_read
"""

import sqlalchemy as sa
from alembic import op

revision = "0028_stock_order_cancel"
down_revision = "0027_bookings_avail_read"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _stock()
    _order_cancel()
    _self_test()


def _stock() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE products
                ADD COLUMN stock_qty integer NOT NULL DEFAULT 0;

            COMMENT ON COLUMN products.stock_qty IS
                'Ombordagi qoldiq (dona). Sotuvni bloklamaydi — manfiy ham '
                'bo''lishi mumkin, bu hisobga olinmagan sotuv belgisi.';
            """
        )
    )


def _order_cancel() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE orders DROP CONSTRAINT orders_status_ck;
            ALTER TABLE orders ADD CONSTRAINT orders_status_ck
                CHECK (status IN ('NEW', 'ACCEPTED', 'PREPARING', 'DELIVERED', 'CANCELLED'));
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
    """`CANCELLED` qabul qilinishi, o'ylanmagan qiymat esa RAD ETILISHI kerak."""
    conn = op.get_bind()
    exempt = _exempt(conn)

    scoped = ("users", "organizations", "clubs", "products", "orders")
    if not exempt:
        _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'stock.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:u, 'Stock Probe Org', 'active') RETURNING id"
            ),
            {"u": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Stock Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()

        # Yangi ustun sukut bilan 0 bo'lishi kerak
        product_id = conn.execute(
            sa.text(
                "INSERT INTO products (club_id, category, name, price, status)"
                " VALUES (:c, 'bar', 'Probe Cola', 12000, 'active') RETURNING id"
            ),
            {"c": club_id},
        ).scalar_one()
        stock = conn.execute(
            sa.text("SELECT stock_qty FROM products WHERE id = :i"), {"i": product_id}
        ).scalar_one()
        if stock != 0:
            raise RuntimeError(f"products.stock_qty sukut qiymati 0 emas: {stock}")

        order_id = conn.execute(
            sa.text(
                "INSERT INTO orders (club_id, status, created_by, total)"
                " VALUES (:c, 'NEW', :u, 12000) RETURNING id"
            ),
            {"c": club_id, "u": owner_id},
        ).scalar_one()

        conn.execute(
            sa.text("UPDATE orders SET status = 'CANCELLED' WHERE id = :i"), {"i": order_id}
        )

        # Lug'atdan tashqari qiymat hali ham rad etilishi kerak. CHECK buzilishi
        # tranzaksiyani ABORT qiladi — SAVEPOINT'siz keyingi HAR QANDAY bayonot
        # (jumladan pastdagi tozalash) "current transaction is aborted" beradi.
        rejected = False
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                sa.text("UPDATE orders SET status = 'NONSENSE' WHERE id = :i"), {"i": order_id}
            )
        except sa.exc.DBAPIError:
            savepoint.rollback()
            rejected = True
        else:
            savepoint.rollback()
        if not rejected:
            raise RuntimeError("orders_status_ck o'ylanmagan qiymatni qabul qildi")
    finally:
        conn.execute(sa.text("DELETE FROM orders WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM products WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        if not exempt:
            _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
