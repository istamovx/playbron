"""Mijoz bo'sh-slot tekshiruvi: `bookings`da PUBLIC o'qish policy'si yo'q edi.

Loyiha egasining topilmasi (2026-08-16): "mijoz sifatida bron
qilolmadim, bu vaqt tanlangan deb xato beryapti". Ildiz sabab —
`GET /clubs/{id}/bookings/day` (`bookings/router.py::list_day_bookings`,
`Depends(public_db)` — token TALAB QILINMAYDI, mijoz hali tizimga
kirmasdan ham klub kalendarini ko'ra olishi kerak) hech qanday `app.*`
GUC o'rnatmaydi. `bookings` jadvalida esa faqat uchta SELECT policy bor
edi (`0009_bookings.py`): `bookings_customer_read` (FAQAT o'zining
bronlari), `bookings_bot_lookup`, `bookings_platform_read` — bularning
BIRI HAM anonim (GUC'siz) so'rovga mos kelmaydi.

Natija — `[[playbron-grant-vs-rls-blind-spot]]` bilan BIR XIL sinf xato:
GRANT bor (`playbron_app` rolida `bookings`ga SELECT GRANT'i bor), lekin
mos POLICY yo'q — so'rov XATO bermaydi, jimgina BO'SH ro'yxat qaytaradi.
Miniapp buni "hech kim band qilmagan" deb talqin qilib, HAR QANDAY
vaqtni "bo'sh" ko'rsatgan; mijoz shu vaqtni tanlab bron yuborganda esa
`bookings_no_overlap` EXCLUDE konstreynti (RLS'dan MUSTAQIL, DB darajasida
ishlaydi) haqiqiy to'qnashuvni to'g'ri aniqlab, `409 SLOT_TAKEN` bergan —
mijozga bu "men bo'sh deb ko'rgan vaqt nega band" bo'lib tuyulgan.

Bu policy `list_day_bookings()`ning o'zi FAQAT PII'siz ustunlarni
(`station_id`, `starts_at`, `ends_at`, `status`) tanlashiga tayanadi
(`docs`dagi izoh: "xom band oraliqlar qaytariladi, mehmon ismi yo'q") —
xuddi `clubs_read` (`0009_bookings.py`) qanday `status='active'` bo'yicha
PUBLIC bo'lsa-yu, `guest_name`/`guest_phone`/`customer_id` kabi shaxsiy
ustunlarni loyiha kodi (RLS emas) himoya qilsa, shu bilan bir xil naqsh.

Revision ID: 0027_bookings_avail_read
Revises: 0026_org_suspend_login
"""

import sqlalchemy as sa
from alembic import op

revision = "0027_bookings_avail_read"
down_revision = "0026_org_suspend_login"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _rls()
    _self_test()


def _rls() -> None:
    op.execute(
        sa.text(
            """
            -- Mavjud policy'lar (mijozning o'zi, bot, platforma) bilan OR
            -- bo'lib qo'shiladi — ular tegilmaydi. Faqat PENDING/CONFIRMED —
            -- CANCELLED bron kimningdir kalendarida "band" bo'lib ko'rinmasin.
            CREATE POLICY bookings_availability_read ON bookings
                FOR SELECT USING (status IN ('PENDING', 'CONFIRMED'));
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
    """GUC'siz (anonim) so'rov PENDING/CONFIRMED bronni ko'rishi, CANCELLED
    bronni KO'RMASLIGI kerak."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "clubs", "stations", "bookings")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'bkgavail.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:u, 'BkgAvail Org', 'active') RETURNING id"
            ),
            {"u": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'BkgAvail Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        station_id = conn.execute(
            sa.text(
                "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                " VALUES (:c, 'AVL-1', 'Standart', 'ps5', 40000) RETURNING id"
            ),
            {"c": club_id},
        ).scalar_one()
        confirmed_id = conn.execute(
            sa.text(
                "INSERT INTO bookings (club_id, station_id, guest_name, guest_phone,"
                " source, status, period, hours, rate_snapshot, console_type)"
                " VALUES (:c, :s, 'Probe', '+998900000000', 'STAFF', 'CONFIRMED',"
                " tstzrange(now() + interval '1 day', now() + interval '1 day 1 hour'),"
                " 1, 40000, 'ps5') RETURNING id"
            ),
            {"c": club_id, "s": station_id},
        ).scalar_one()
        cancelled_id = conn.execute(
            sa.text(
                "INSERT INTO bookings (club_id, station_id, guest_name, guest_phone,"
                " source, status, period, hours, rate_snapshot, console_type)"
                " VALUES (:c, :s, 'Probe', '+998900000000', 'STAFF', 'CANCELLED',"
                " tstzrange(now() + interval '2 day', now() + interval '2 day 1 hour'),"
                " 1, 40000, 'ps5') RETURNING id"
            ),
            {"c": club_id, "s": station_id},
        ).scalar_one()
    finally:
        _force_rls(conn, scoped, enabled=True)

    try:
        # Anonim — hech qanday app.* GUC o'rnatilmagan (`public_db()` bilan bir xil).
        conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_id', '0', true)"))

        visible_confirmed = conn.execute(
            sa.text("SELECT count(*) FROM bookings WHERE id = :i"), {"i": confirmed_id}
        ).scalar_one()
        if visible_confirmed != 1:
            raise RuntimeError(
                "bookings_availability_read: anonim so'rov CONFIRMED bronni ko'rmadi"
                " (mijoz bo'sh-slot tekshiruvi yana bo'sh ro'yxat qaytaradi)"
            )

        visible_cancelled = conn.execute(
            sa.text("SELECT count(*) FROM bookings WHERE id = :i"), {"i": cancelled_id}
        ).scalar_one()
        if visible_cancelled != 0:
            raise RuntimeError(
                "bookings_availability_read: anonim so'rov CANCELLED bronni HAM ko'rdi"
                " (haddan tashqari keng policy)"
            )
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM bookings WHERE id IN (:a, :b)"), {"a": confirmed_id, "b": cancelled_id})
        conn.execute(sa.text("DELETE FROM stations WHERE id = :s"), {"s": station_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
