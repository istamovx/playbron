"""Platforma paneli — super admin uchun cross-tenant statistika o'qish.

Loyiha egasining so'rovi (2026-08-16): "Super admin roli uchun ko'proq
narsa qila olamiz — infografikalar bilan boyitish kerak". `docs/06-super-admin.md`
to'liq spetsifikatsiyasi (Glass rejimi, TOTP, audit HMAC zanjiri, billing,
CMS) juda katta va bu loyihada hali yo'q quyi tizimlarga (`subscriptions`,
`platform_payments`, `glass_sessions`) tayanadi. Bu migratsiya faqat
hujjatning **§2.1 (`app_platform()`) va §2.11 (`platform_read` policy'lari)**
qismini, eng kichik va xavfsiz kesimda, amalga oshiradi — faqat O'QISH,
faqat uchta jadval (`organizations`, `clubs`, `bookings`), pul/parol
jadvallariga (`club_payment_credentials`, `staff_credentials` va h.k.)
umuman tegilmaydi.

**Nega kerak, `platform_scope()` (`core/db.py`) allaqachon bor-ku?**
U hozir FAQAT `playbron_platform`ning haqiqiy BYPASSRLS'iga tayanadi.
Render bepul rejasida bu rol BYPASSRLS ololmaydi (`0001_core.py`dagi
`ALTER ROLE ... BYPASSRLS` jimgina o'tkazib yuboriladi — superuser kerak,
`[[render-free-tier-no-bypassrls]]`), ya'ni bugungi holatda statistika
prod'da HAR DOIM bo'sh qaytardi — xato bermay, shunchaki "hammasi nol"
ko'rsatib. Shu migratsiya + `core/db.py::platform_scope()`ga qo'shiladigan
`SET LOCAL app.platform` ikkinchi, GUC asosidagi yo'lni ochadi — BYPASSRLS
bo'lsa ham, bo'lmasa ham ishlaydi.

Revision ID: 0015_platform_stats
Revises: 0014_club_maps_links
"""

import sqlalchemy as sa
from alembic import op

revision = "0015_platform_stats"
down_revision = "0014_club_maps_links"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _function()
    _policies()
    _grants()
    _self_test()


def _function() -> None:
    op.execute(
        sa.text(
            """
            CREATE FUNCTION app_platform() RETURNS boolean
                LANGUAGE sql STABLE AS $$
                    SELECT COALESCE(current_setting('app.platform', true), '') = 'true'
                $$;
            """
        )
    )


def _policies() -> None:
    op.execute(
        sa.text(
            """
            -- Faqat O'QISH. Yozish, merchant kalitlari, xodim/mijoz parollari —
            -- bu policy'lar orqali umuman ochilmaydi (`docs/06-super-admin.md` §2.11).
            CREATE POLICY organizations_platform_read ON organizations
                FOR SELECT USING (app_platform());
            CREATE POLICY clubs_platform_read ON clubs
                FOR SELECT USING (app_platform());
            CREATE POLICY bookings_platform_read ON bookings
                FOR SELECT USING (app_platform());
            """
        )
    )


def _grants() -> None:
    """`bookings` `0009_bookings.py`da yaratilgan — 0001'dagi bir martalik
    `GRANT SELECT ON ALL TABLES` unga tegmagan (o'sha payt jadval hali yo'q
    edi). `playbron_platform`ga hech qachon berilmagan
    (`[[playbron-grant-vs-rls-blind-spot]]`) — `organizations`/`clubs`
    esa 0001'ning o'zida yaratilgani uchun o'sha blanket GRANT ularni
    allaqachon qamragan, qo'shimcha GRANT shart emas.

    `EXECUTE ON app_club_role(bigint)` ham kerak — sabab RLS emas, Postgres
    o'zi: `bookings`da `bookings_staff_all` (mavjud, boshqa) policy'si ham
    shu funksiyani chaqiradi, va bir nechta PERMISSIVE policy OR bilan
    birlashtirilganda Postgres SO'ROVNI REJALASHTIRISH vaqtida BARCHA
    policy ifodalaridagi funksiyalarga EXECUTE huquqini talab qiladi —
    natija runtime'da qaysi policy "g'olib" bo'lishidan qat'i nazar. Ya'ni
    `bookings_platform_read` o'zi `app_club_role()` chaqirmasa ham, uni
    ishlatish uchun bu GRANT shart."""
    op.execute(sa.text("GRANT SELECT ON bookings TO playbron_platform;"))
    op.execute(sa.text("GRANT EXECUTE ON FUNCTION app_club_role(bigint) TO playbron_platform;"))


def _force_rls(conn: sa.Connection, tables: tuple[str, ...], *, enabled: bool) -> None:
    verb = "FORCE" if enabled else "NO FORCE"
    for table in tables:
        conn.execute(sa.text(f"ALTER TABLE {table} {verb} ROW LEVEL SECURITY"))


def _exempt(conn: sa.Connection) -> bool:
    """Superuser/BYPASSRLS ostida bu tekshiruv hech narsa isbotlamaydi —
    o'tkazib yuboriladi (`playbron-grant-vs-rls-blind-spot` bilan bir xil
    sabab: mahalliy `playbron` superuser buni yashiradi)."""
    return bool(
        conn.execute(
            sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    )


def _self_test() -> None:
    """Ikki tomonlama tekshiruv: GUC'siz izolyatsiya SAQLANADI, GUC bilan
    cross-tenant o'qish OCHILADI. Ikkalasi ham muhim — birinchisisiz bu
    migratsiya butun `organizations`/`clubs`/`bookings`ni tasodifan HAR
    KIMGA ochib qo'yishi mumkin edi."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "clubs")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'platform.probe.owner', 'active', 'P')"
                " RETURNING id"
            )
        ).scalar_one()
        org_a = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Platform Test Org A', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        # `status='draft'` ataylab: `clubs_read` (`0003`) `status='active'`ni
        # HAR KIMGA (ochiq katalog uchun) ochadi — 'active' bilan probe qilsak
        # yangi `clubs_platform_read` emas, o'sha eski qoidani sinagan bo'lardik.
        club_a = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'Platform Probe Club', 'draft')"
                " RETURNING id"
            ),
            {"o": org_a},
        ).scalar_one()
    finally:
        _force_rls(conn, scoped, enabled=True)

    try:
        # `app.org_id`/`app.club_id` boshqa (yoki bo'sh) — bu klub bo'lmagan
        # kontekst, `app.platform` ham o'rnatilmagan.
        conn.execute(
            sa.text(
                "SELECT set_config('app.org_id', '0', true),"
                "       set_config('app.club_id', '0', true),"
                "       set_config('app.platform', 'false', true)"
            )
        )
        isolated = conn.execute(
            sa.text("SELECT count(*) FROM clubs WHERE id = :c"), {"c": club_a}
        ).scalar_one()
        if isolated != 0:
            raise RuntimeError(
                "clubs_platform_read: app.platform o'rnatilmasa ham begona klub ko'rindi"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'true', true)"))
        visible = conn.execute(
            sa.text("SELECT count(*) FROM clubs WHERE id = :c"), {"c": club_a}
        ).scalar_one()
        if visible != 1:
            raise RuntimeError("clubs_platform_read: app.platform=true bo'lsa ham klub ko'rinmadi")

        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_a})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_a})
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
