"""`stations` uchun bot-lookup policy'si (0025dagi teshikni yopadi).

`0025_payment_proof_bot.py` `bookings`/`clubs`/`users` uchun bot-lookup
policy'larini qo'shgan, lekin `stations` UNUTILGAN edi. Uning
`bot_submit_payment_proof()` funksiyasi esa `UPDATE ... FROM stations s,
clubs c` qiladi va JOIN uchun `stations`ga SELECT huquqi kerak.

Oqibati BYPASSRLS'siz bazada (Render bepul rejasi,
`[[render-free-tier-no-bypassrls]]`): join bo'sh qaytadi, UPDATE hech
qanday qatorga tegmaydi, `0025`ning o'z `_self_test()`i "holat
SUBMITTED'ga o'tmadi" bilan yiqiladi va MIGRATSIYA TO'XTAYDI — ya'ni
butun deploy o'tmaydi. Lokal superuser buni yashirgan: `_exempt()`
self-testni umuman o'tkazib yuboradi.

`0025`ning o'zi ham tuzatildi (yangi bazalar uchun). Bu migratsiya esa
`0025` ALLAQACHON qo'llangan bazalar uchun — shuning uchun idempotent
(`DROP POLICY IF EXISTS` + `CREATE`).

Revision ID: 0031_stations_bot_lookup
Revises: 0030_suspend_revoke
"""

import sqlalchemy as sa
from alembic import op

revision = "0031_stations_bot_lookup"
down_revision = "0030_suspend_revoke"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _rls()
    _self_test()


def _rls() -> None:
    op.execute(
        sa.text(
            """
            -- Idempotent: `0025` tuzatilgandan keyin yangi bazada policy
            -- allaqachon mavjud bo'ladi.
            DROP POLICY IF EXISTS stations_bot_lookup ON stations;
            CREATE POLICY stations_bot_lookup ON stations FOR SELECT
                USING (app_bot_lookup_claim());
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
    """`bot_submit_payment_proof()` UCHDAN UCHIGACHA ishlashi kerak —
    aynan `0025` sinagan narsa, lekin endi `stations` ko'rinadigan holda."""
    conn = op.get_bind()
    exempt = _exempt(conn)

    scoped = ("users", "organizations", "clubs", "stations", "bookings")
    if not exempt:
        _force_rls(conn, scoped, enabled=False)
    ids: dict[str, int] = {}
    try:
        ids["customer"] = conn.execute(
            sa.text(
                "INSERT INTO users (kind, telegram_id, status, first_name)"
                " VALUES ('customer', 900000731, 'active', 'Sinov') RETURNING id"
            )
        ).scalar_one()
        ids["owner"] = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'stbot.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        ids["org"] = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:u, 'StBot Org', 'active') RETURNING id"
            ),
            {"u": ids["owner"]},
        ).scalar_one()
        ids["club"] = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'StBot Club', 'active') RETURNING id"
            ),
            {"o": ids["org"]},
        ).scalar_one()
        ids["station"] = conn.execute(
            sa.text(
                "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                " VALUES (:c, 'SBT-1', 'Standart', 'ps5', 40000) RETURNING id"
            ),
            {"c": ids["club"]},
        ).scalar_one()
        ids["booking"] = conn.execute(
            sa.text(
                "INSERT INTO bookings (club_id, station_id, customer_id, source, status,"
                " period, hours, rate_snapshot, console_type, payment_proof_status)"
                " VALUES (:c, :s, :u, 'MINIAPP', 'CONFIRMED',"
                " tstzrange(now() + interval '1 hour', now() + interval '2 hour'),"
                " 1, 40000, 'ps5', 'PENDING') RETURNING id"
            ),
            {"c": ids["club"], "s": ids["station"], "u": ids["customer"]},
        ).scalar_one()
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=True)

    try:
        row = conn.execute(
            sa.text("SELECT * FROM bot_submit_payment_proof(:tg, 'probe-file-id')"),
            {"tg": 900000731},
        ).first()
        if row is None:
            raise RuntimeError(
                "bot_submit_payment_proof: kontekst qaytmadi"
                " (stations JOIN yana bo'sh — policy ishlamadi)"
            )
        if row.booking_id != ids["booking"] or row.station_code != "SBT-1":
            raise RuntimeError(f"bot_submit_payment_proof: noto'g'ri kontekst — {row}")
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=False)
        status = conn.execute(
            sa.text("SELECT payment_proof_status FROM bookings WHERE id = :i"),
            {"i": ids["booking"]},
        ).scalar_one()

        conn.execute(sa.text("DELETE FROM bookings WHERE id = :i"), {"i": ids["booking"]})
        conn.execute(sa.text("DELETE FROM stations WHERE id = :i"), {"i": ids["station"]})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :i"), {"i": ids["club"]})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:a, :b)"),
            {"a": ids["customer"], "b": ids["owner"]},
        )
        if not exempt:
            _force_rls(conn, scoped, enabled=True)

        if status != "SUBMITTED":
            raise RuntimeError(f"bot_submit_payment_proof: holat SUBMITTED emas — {status}")


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
