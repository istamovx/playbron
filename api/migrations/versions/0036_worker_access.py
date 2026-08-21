"""Worker uchun tor RLS yo'llari — `app.worker` claim'i.

Fon vazifasida haqiqiy aktyor yo'q (`user_id = 0`), `app_club_role()` esa
rolni `memberships`dan o'qiydi — natijada rol-talab policy'lar worker
uchun yopiq va so'rovlar JIMGINA 0 qator qaytaradi (B3'da testlar shu
holatni ushladi — skill'dagi bosh tuzoqning o'zi).

Yechim — mavjud naqsh (docs/07-patterns.md §2): nomlangan claim + har
jadvalga ANIQ tor policy. Yangi BYPASSRLS roli YO'Q. Claim kuchi klub
bilan cheklangan: worker `app.club_id`ni ham o'rnatadi va policy'lar
`club_id = app_club_id()`ni talab qiladi — bitta klub konteksti boshqa
klub qatorini ochmaydi.

Worker nimaga tegadi (B3 vazifalaridan kelib chiqqan minimal to'plam):
- `bookings`  SELECT + UPDATE (avto-bekor, eslatmalar)
- `users`     SELECT — faqat shu klubda broni bor MIJOZLAR (chat uchun)
- `payments`  SELECT (kunlik xulosa)
- `stations`  SELECT (kunlik xulosa; bandlik hisobi)

Revision ID: 0036_worker_access
Revises: 0035_jobs_notifications
"""

import sqlalchemy as sa
from alembic import op

revision = "0036_worker_access"
down_revision = "0035_jobs_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_worker() RETURNS boolean
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(current_setting('app.worker', true), '') = 'true' $$;

            CREATE POLICY bookings_worker_read ON bookings FOR SELECT
                USING (app_worker() AND club_id = app_club_id());
            -- UPDATE'ga SELECT policy'si ham kerak (qator topish bosqichi) —
            -- yuqoridagi read policy shu vazifani bajaradi
            CREATE POLICY bookings_worker_update ON bookings FOR UPDATE
                USING (app_worker() AND club_id = app_club_id())
                WITH CHECK (app_worker() AND club_id = app_club_id());

            -- Mijoz qatori faqat shu klubda broni bo'lsa ochiladi —
            -- users_booking_contact bilan bir xil chegara, rolsiz
            CREATE POLICY users_worker_customer ON users FOR SELECT
                USING (
                    app_worker() AND kind = 'customer'
                    AND EXISTS (
                        SELECT 1 FROM bookings b
                        WHERE b.customer_id = users.id AND b.club_id = app_club_id()
                    )
                );

            CREATE POLICY payments_worker_read ON payments FOR SELECT
                USING (app_worker() AND club_id = app_club_id());

            CREATE POLICY stations_worker_read ON stations FOR SELECT
                USING (app_worker() AND club_id = app_club_id());
            """
        )
    )
    _self_test()


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
    """Claim'siz yopiq; claim bilan faqat O'Z klubi; mijoz faqat bron orqali."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "clubs", "stations", "bookings")
    _force_rls(conn, scoped, enabled=False)
    try:
        cust_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, telegram_id, first_name)"
                " VALUES ('customer', 909001, 'WProbe') RETURNING id"
            )
        ).scalar_one()
        lone_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, telegram_id, first_name)"
                " VALUES ('customer', 909002, 'WLone') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'WAccess Org', 'active') RETURNING id"
            ),
            {"o": cust_id},
        ).scalar_one()
        club_a = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'WAccess A', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        club_b = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'WAccess B', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        station_a = conn.execute(
            sa.text(
                "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                " VALUES (:c, 'WA-1', 'Std', 'ps5', 40000) RETURNING id"
            ),
            {"c": club_a},
        ).scalar_one()
        booking_a = conn.execute(
            sa.text(
                "INSERT INTO bookings (club_id, station_id, customer_id, source, status,"
                " period, hours, rate_snapshot, console_type)"
                " VALUES (:c, :s, :u, 'MINIAPP', 'PENDING',"
                " tstzrange(now() + interval '3 hours', now() + interval '4 hours'),"
                " 1, 40000, 'ps5') RETURNING id"
            ),
            {"c": club_a, "s": station_a, "u": cust_id},
        ).scalar_one()
    finally:
        _force_rls(conn, scoped, enabled=True)

    try:
        # Worker konteksti: club A, claim YO'Q. Bron O'QISH ochiq bo'lishi
        # mumkin (bandlik uchun rolsiz public policy bor) — haqiqiy chegara
        # YOZISH: claim'siz UPDATE 0 qatorga tegishi kerak.
        conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_id', :c, true)"), {"c": str(club_a)})
        touched = conn.execute(
            sa.text("UPDATE bookings SET cancel_reason = 'probe' WHERE id = :b RETURNING id"),
            {"b": booking_a},
        ).scalar()
        if touched is not None:
            raise RuntimeError("bookings_worker_update: claim'siz UPDATE o'tib ketdi")
        # Mijoz qatori ham claim'siz yopiq bo'lishi kerak
        seen = conn.execute(
            sa.text("SELECT count(*) FROM users WHERE id = :u"), {"u": cust_id}
        ).scalar_one()
        if seen != 0:
            raise RuntimeError("users_worker_customer: claim'siz mijoz ochilib qoldi")

        # Claim bilan — ko'rinadi va yangilanadi
        conn.execute(sa.text("SELECT set_config('app.worker', 'true', true)"))
        visible = conn.execute(
            sa.text("SELECT count(*) FROM bookings WHERE id = :b"), {"b": booking_a}
        ).scalar_one()
        if visible != 1:
            raise RuntimeError("bookings_worker_read: claim bilan qator ko'rinmadi")
        updated = conn.execute(
            sa.text(
                "UPDATE bookings SET cancel_reason = 'probe' WHERE id = :b RETURNING id"
            ),
            {"b": booking_a},
        ).scalar()
        if updated is None:
            raise RuntimeError("bookings_worker_update: claim bilan UPDATE ishlamadi")

        # Mijoz: broni bor — ko'rinadi; bronsiz mijoz — YO'Q
        seen = conn.execute(
            sa.text("SELECT count(*) FROM users WHERE id = :u"), {"u": cust_id}
        ).scalar_one()
        if seen != 1:
            raise RuntimeError("users_worker_customer: bronli mijoz ko'rinmadi")
        lone = conn.execute(
            sa.text("SELECT count(*) FROM users WHERE id = :u"), {"u": lone_id}
        ).scalar_one()
        if lone != 0:
            raise RuntimeError("users_worker_customer: bronsiz mijoz ochilib qoldi — sizish")

        # Boshqa klub konteksti — A'ning bronini YOZIB bo'lmaydi (claim klub
        # bilan cheklangan). O'QISH tekshirilmaydi: PENDING/CONFIRMED bronlar
        # `bookings_availability_read` bilan barchaga ochiq (miniapp bandligi
        # dizayni) — bu 0036'dan oldin ham shunday edi.
        conn.execute(sa.text("SELECT set_config('app.club_id', :c, true)"), {"c": str(club_b)})
        cross = conn.execute(
            sa.text("UPDATE bookings SET cancel_reason = 'x' WHERE id = :b RETURNING id"),
            {"b": booking_a},
        ).scalar()
        if cross is not None:
            raise RuntimeError(
                "bookings_worker_update: claim boshqa klub qatorini yozdi — sizish"
            )

        conn.execute(sa.text("SELECT set_config('app.worker', '', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_id', '0', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM bookings WHERE club_id IN (:a, :b)"),
                     {"a": club_a, "b": club_b})
        conn.execute(sa.text("DELETE FROM stations WHERE club_id IN (:a, :b)"),
                     {"a": club_a, "b": club_b})
        conn.execute(sa.text("DELETE FROM clubs WHERE id IN (:a, :b)"), {"a": club_a, "b": club_b})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:u, :l)"), {"u": cust_id, "l": lone_id}
        )
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")
