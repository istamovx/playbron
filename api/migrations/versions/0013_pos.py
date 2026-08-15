"""POS: mahsulotlar, buyurtmalar, kassa (hisob yopish).

Loyiha egasining so'rovi (2026-08-16): "Kassa" — buyurtmalar, hisob-kitob
va chek bitta joyda. Uch yangi jadval + `bookings`ga hisob yopish
ustunlari:

  * `products`  — klub bar/menyu katalogi (OWNER/ADMIN boshqaradi)
  * `orders` + `order_items` — xodim mijoz uchun ochgan buyurtma
    (`docs`dagi ORDER_FLOW: NEW → ACCEPTED → PREPARING → DELIVERED)
  * `bookings.closed_at/payment_method/paid_amount/closed_by` — seans
    yopilganda: o'yin summasi (`rate_snapshot * hours`) + buyurtmalar
    yig'indisi = umumiy hisob

**Naqsh — bir xil butun migratsiya davomida**: yangi jadvallar xodim
(`OWNER/ADMIN/STAFF`) uchun `stations`/`bookings` bilan bir xil
`app_club_role(app_club_id())` asosidagi RLS'ga ega. Mijozga (miniapp)
ochiq emas — bar buyurtmasini hozircha FAQAT xodim ochadi (mijoz o'zi
buyurtma qilish keyingi bosqich, `docs`dagi seans/savat ekrani hali mock).

`0003_rls_hardening.py`dan beri sukut imtiyoz o'chirilgan — har bir yangi
jadval uchun GRANT ham `APP_ROLE`, ham (kerak bo'lsa) `PLATFORM_ROLE`ga
ANIQ yoziladi (`[[playbron-grant-vs-rls-blind-spot]]`).

Revision ID: 0013_pos
Revises: 0012_club_publish
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_pos"
down_revision = "0012_club_publish"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"


def upgrade() -> None:
    _tables()
    _billing_columns()
    _rls()
    _grants()


def _tables() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        # Erkin matn — `stations.room_label` bilan bir xil falsafa
        sa.Column("category", sa.String(32), nullable=False, server_default="Boshqa"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("price", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("price > 0", name="products_price_positive_ck"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="products_status_ck"),
        sa.UniqueConstraint("club_id", "name", name="products_club_name_uk"),
    )
    op.create_index("products_club_ix", "products", ["club_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        # Bron bilan bog'liq — qaysi xona/mijoz uchun ekanini shundan bilamiz.
        # NULL — bron yaratilmagan holatda ham bar buyurtma qabul qilinadi
        # (masalan hali stol band qilinmagan mehmon).
        sa.Column(
            "booking_id", sa.BigInteger, sa.ForeignKey("bookings.id", ondelete="SET NULL")
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="NEW"),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # Yaratilgandagi yig'indi — snapshot, keyingi narx o'zgarishi eski
        # buyurtmaga ta'sir qilmaydi.
        sa.Column("total", sa.BigInteger, nullable=False),
        sa.CheckConstraint(
            "status IN ('NEW', 'ACCEPTED', 'PREPARING', 'DELIVERED')", name="orders_status_ck"
        ),
        sa.CheckConstraint("total >= 0", name="orders_total_nonneg_ck"),
    )
    op.create_index("orders_club_ix", "orders", ["club_id"])
    op.create_index("orders_booking_ix", "orders", ["booking_id"])

    op.create_table(
        "order_items",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        # `club_id` qatorda takrorlanadi — RLS'ni `orders`ga JOIN'siz, to'g'ridan
        # -to'g'ri qo'llash uchun (`bookings`dagi bilan bir xil naqsh).
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "order_id", sa.BigInteger, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("product_id", sa.BigInteger, sa.ForeignKey("products.id"), nullable=True),
        # Snapshot — mahsulot keyin o'chirilsa/nomi o'zgarsa ham eski
        # buyurtma o'zgarmaydi.
        sa.Column("product_name", sa.String(120), nullable=False),
        sa.Column("qty", sa.Integer, nullable=False),
        sa.Column("price_snapshot", sa.BigInteger, nullable=False),
        sa.CheckConstraint("qty > 0", name="order_items_qty_positive_ck"),
        sa.CheckConstraint("price_snapshot > 0", name="order_items_price_positive_ck"),
    )
    op.create_index("order_items_order_ix", "order_items", ["order_id"])
    op.create_index("order_items_club_ix", "order_items", ["club_id"])


def _billing_columns() -> None:
    op.execute(
        sa.text(
            """
            -- `closed_at IS NULL` — seans hali ochiq (hisob yopilmagan).
            -- Yangi `status` qiymati SHART EMAS: `CONFIRMED` + `closed_at`
            -- yetarli, `bookings_no_overlap`ning WHERE shartiga tegilmaydi.
            ALTER TABLE bookings ADD COLUMN closed_at timestamptz;
            ALTER TABLE bookings ADD COLUMN payment_method text;
            ALTER TABLE bookings ADD COLUMN paid_amount bigint;
            ALTER TABLE bookings ADD COLUMN closed_by bigint REFERENCES users(id);

            ALTER TABLE bookings ADD CONSTRAINT bookings_payment_method_ck
                CHECK (payment_method IS NULL OR payment_method IN ('CASH', 'TRANSFER'));
            ALTER TABLE bookings ADD CONSTRAINT bookings_paid_amount_nonneg_ck
                CHECK (paid_amount IS NULL OR paid_amount >= 0);
            """
        )
    )


def _rls() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE products ENABLE ROW LEVEL SECURITY;
            ALTER TABLE products FORCE ROW LEVEL SECURITY;
            ALTER TABLE orders ENABLE ROW LEVEL SECURITY;
            ALTER TABLE orders FORCE ROW LEVEL SECURITY;
            ALTER TABLE order_items ENABLE ROW LEVEL SECURITY;
            ALTER TABLE order_items FORCE ROW LEVEL SECURITY;

            -- Mahsulotlar: o'qish butun xodim uchun, yozish OWNER/ADMIN
            -- (`stations_write` bilan bir xil naqsh).
            CREATE POLICY products_read ON products FOR SELECT
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'));

            CREATE POLICY products_write ON products FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'));

            -- Buyurtmalar: butun xodim to'liq ishlaydi (`bookings_staff_all`
            -- bilan bir xil) — hozircha mijoz o'zi buyurtma qilmaydi.
            CREATE POLICY orders_staff_all ON orders FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'));

            CREATE POLICY order_items_staff_all ON order_items FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'));
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            GRANT SELECT, INSERT, UPDATE ON products, orders, order_items TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE products_id_seq TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE orders_id_seq TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE order_items_id_seq TO {APP_ROLE};

            -- Hisob yopish yangi ustunlarga yozadi — `bookings`ning o'zi
            -- allaqachon `APP_ROLE`ga to'liq ochiq (`0009`), qo'shimcha
            -- GRANT shart emas.
            """
        )
    )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
