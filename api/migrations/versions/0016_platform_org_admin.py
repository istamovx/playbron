"""Platforma — qo'lda klub qo'shish va to'lov yozuvi.

Loyiha egasining so'rovi (2026-08-16): super admin "Klublar" bo'limida
(1) barcha klub/tashkilotlarni ko'rsin, (2) to'lov tizimi bilan bog'liq
muammo bo'lganda yoki tarif sotib olgan mijoz avtomatik tushmasa, klubni
QO'LDA qo'shsin. "Hisobot" bo'limi shundan yig'ilgan daromadni kunlik/
haftalik/oylik/yillik kesimda ko'rsatishi kerak.

**Klub/tashkilot/ega yaratish uchun yangi jadval yoki policy SHART EMAS.**
`0008_owner_signup.py`dagi `auth_owner_signup()` — bitta tranzaksiyada besh
jadval, `app.signup_login` GUC'i bilan qanoatlantiriladigan policy'lar
orqali — aynan shu vazifa uchun yozilgan va sinovdan o'tgan. Super admin
`POST /platform/orgs`'i shu FUNKSIYANING O'ZINI (`modules/auth/signup.py`
orqali) qayta ishlatadi, `playbron_app` sessiyasi (oddiy `db` dependency)
bilan — yangi RLS yo'li ochilmaydi.

**Yangi narsa — faqat to'lov yozuvi.** Platformada hali haqiqiy
to'lov/obuna tizimi yo'q (`subscriptions`/`platform_payments`
`docs/06-super-admin.md`da rejalashtirilgan, hali qurilmagan). Bu
migratsiya eng kichik kesimni qo'shadi: `platform_payments` — qo'lda
kiritiladigan, o'chirilmaydigan (append-only, `audit_log` bilan bir xil
kelishuv) to'lov qatorlari. Faqat `app_platform()` o'qiydi/yozadi —
klub egasi ham, oddiy `playbron_app` ham bu jadvalni ko'rmaydi.

Revision ID: 0016_platform_org_admin
Revises: 0015_platform_stats
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_platform_org_admin"
down_revision = "0015_platform_stats"
branch_labels = None
depends_on = None

PLATFORM_ROLE = "playbron_platform"


def upgrade() -> None:
    _tables()
    _rls()
    _grants()
    _self_test()


def _tables() -> None:
    op.create_table(
        "platform_payments",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "org_id",
            sa.BigInteger,
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("amount", sa.BigInteger, nullable=False),
        # Erkin — plansiz to'lov ham bo'lishi mumkin (masalan bir martalik).
        sa.Column("plan_code", sa.String(32), sa.ForeignKey("plans.code"), nullable=True),
        sa.Column("period_months", sa.Integer, nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("note", sa.Text, nullable=True),
        # Kim kiritdi — audit uchun, `app_user_id()` orqali emas: platforma
        # yo'lida bu GUC odatiy ma'noda o'rnatilmagan.
        sa.Column("entered_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("amount > 0", name="platform_payments_amount_positive_ck"),
        sa.CheckConstraint(
            "period_months IS NULL OR period_months > 0", name="platform_payments_period_ck"
        ),
    )
    op.create_index("platform_payments_org_ix", "platform_payments", ["org_id"])
    op.create_index("platform_payments_paid_at_ix", "platform_payments", ["paid_at"])


def _rls() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE platform_payments ENABLE ROW LEVEL SECURITY;
            ALTER TABLE platform_payments FORCE ROW LEVEL SECURITY;

            -- Yozish HAM shu bitta policy bilan: DELETE/UPDATE grant
            -- umuman berilmaydi (pastda), ya'ni FOR ALL bo'lsa ham
            -- amalda faqat SELECT/INSERT ishlaydi — append-only.
            CREATE POLICY platform_payments_platform_all ON platform_payments
                FOR ALL USING (app_platform()) WITH CHECK (app_platform());

            -- "Klublar" ro'yxati egani ko'rsatish uchun `users`ga JOIN
            -- qiladi (`list_organizations`) — policy'siz INNER JOIN
            -- jimgina BARCHA qatorni yo'qotardi (`users`ning o'z RLS'i
            -- app_platform()ni bilmaydi). `0015`da bu jadval unutilgan edi
            -- (faqat organizations/clubs/bookings qo'shilgan).
            CREATE POLICY users_platform_read ON users
                FOR SELECT USING (app_platform());
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            GRANT SELECT, INSERT ON platform_payments TO {PLATFORM_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE platform_payments_id_seq TO {PLATFORM_ROLE};

            -- `users_platform_read` qator darajasida ochadi, lekin ustun
            -- darajasida eng nozik ikkitasi (`docs/06-super-admin.md` §5.4
            -- — masallangan qidiruv talabi) qaytarib olinadi: "Klublar"
            -- ro'yxati faqat `first_name`/`login`ga muhtoj, `phone`/
            -- `telegram_id` esa aloqa/deanonimizatsiya xavfi tashiydi.
            REVOKE SELECT (phone, telegram_id) ON users FROM {PLATFORM_ROLE};
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
    """`platform_payments` — GUC'siz izolyatsiya, GUC bilan cross-tenant
    o'qish (`0015_platform_stats.py`dagi bilan bir xil naqsh)."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "platform_payments")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'platform.pay.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Platform Payment Probe Org', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        payment_id = conn.execute(
            sa.text(
                "INSERT INTO platform_payments (org_id, amount, entered_by)"
                " VALUES (:org, 500000, :u) RETURNING id"
            ),
            {"org": org_id, "u": owner_id},
        ).scalar_one()
    finally:
        _force_rls(conn, scoped, enabled=True)

    try:
        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
        isolated = conn.execute(
            sa.text("SELECT count(*) FROM platform_payments WHERE id = :p"), {"p": payment_id}
        ).scalar_one()
        if isolated != 0:
            raise RuntimeError(
                "platform_payments_platform_all: app.platform o'rnatilmasa ham to'lov ko'rindi"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'true', true)"))
        visible = conn.execute(
            sa.text("SELECT count(*) FROM platform_payments WHERE id = :p"), {"p": payment_id}
        ).scalar_one()
        if visible != 1:
            raise RuntimeError(
                "platform_payments_platform_all: app.platform=true bo'lsa ham to'lov ko'rinmadi"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM platform_payments WHERE id = :p"), {"p": payment_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
