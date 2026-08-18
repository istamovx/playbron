"""Xonalar, tariflar va klub sozlamalari.

Manba: `docs/audit-report.md` §2.5 — modelning uchta chegarasi:

  * **Tarif yo'q.** Narx `stations.rate` — bitta flat qiymat. Kechqurun
    qimmat, ish kuni arzon, VIP alohida degan oddiy talab bajarilmaydi.
  * **Xona yo'q.** `stations.room_label` — erkin matn, ya'ni xona bo'yicha
    filtr ham, hisobot ham, VIP xonani butunligicha bron qilish ham yo'q.
  * **Sozlamalar kodda qotirilgan** (`MAX_ADVANCE_DAYS`, `PREPAY_HOURS`,
    davomiylik chegaralari) — klub ularni o'zi o'zgartira olmaydi, ya'ni
    SaaS bir qolipdagi klublargagina yaraydi.

## `bookings.play_amount`

Tarif vaqtga qarab o'zgargani uchun bron narxini `rate_snapshot * hours`
bilan ifodalab BO'LMAYDI: 17:00–19:00 broni ikki xil narxdagi ikki
bo'lakdan iborat. Shu sababli hisoblangan TO'LIQ summa alohida ustunga
yoziladi va hamma joyda o'sha ishlatiladi (hisobot, kassa, platforma
statistikasi). `rate_snapshot` ko'rsatish uchun qoladi.

Eski qatorlar `rate_snapshot * hours` bilan to'ldiriladi — ular uchun
bu aynan o'sha qiymat edi.

## Xonalar ko'chirilishi

`stations.room_label` dagi har bir NOYOB matn klub ichida bitta `rooms`
qatoriga aylanadi va stansiya unga bog'lanadi. Matn ustuni O'CHIRILMAYDI:
eski kod hali uni o'qiydi va migratsiyalar faqat oldinga.

Revision ID: 0033_rooms_tariffs
Revises: 0032_payments
"""

import sqlalchemy as sa
from alembic import op

revision = "0033_rooms_tariffs"
down_revision = "0032_payments"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"

ALL_DAYS = 0b111_1111


def upgrade() -> None:
    _tables()
    _club_settings()
    _booking_play_amount()
    _backfill()
    _rls()
    _grants()
    _self_test()


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")


def _tables() -> None:
    op.create_table(
        "rooms",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(64), nullable=False),
        # Erkin matn — klub o'zi nomlaydi (`stations.room_label` bilan bir
        # xil falsafa). Tarif shu qiymatga qarab yo'naltiriladi.
        sa.Column("kind", sa.String(32), nullable=False, server_default="Standart"),
        sa.Column("sort", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("club_id", "name", name="rooms_club_name_uk"),
    )

    op.execute(
        sa.text("ALTER TABLE stations ADD COLUMN room_id bigint REFERENCES rooms(id)")
    )
    op.create_index("stations_room_ix", "stations", ["room_id"])

    op.create_table(
        "tariffs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(64), nullable=False),
        # Dushanba = 1-bit ... Yakshanba = 64-bit (`datetime.weekday()`).
        sa.Column("days_mask", sa.Integer, nullable=False, server_default=str(ALL_DAYS)),
        # Yarim tundan boshlab daqiqada. `to_min` 1440 dan katta bo'lishi
        # mumkin — masalan 22:00–02:00 uchun 1320..1560.
        sa.Column("from_min", sa.Integer, nullable=False),
        sa.Column("to_min", sa.Integer, nullable=False),
        sa.Column("price_per_hour", sa.BigInteger, nullable=False),
        # Kesishgan tariflardan eng yuqorisi qo'llanadi.
        sa.Column("priority", sa.Integer, nullable=False, server_default="0"),
        # `NULL` — har qanday konsolga / xonaga.
        sa.Column("console_type", sa.String(16), nullable=True),
        sa.Column("room_kind", sa.String(32), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("price_per_hour > 0", name="tariffs_price_positive_ck"),
        sa.CheckConstraint("days_mask BETWEEN 1 AND 127", name="tariffs_days_mask_ck"),
        sa.CheckConstraint(
            "from_min >= 0 AND from_min < 1440 AND to_min > from_min AND to_min <= 2880",
            name="tariffs_window_ck",
        ),
    )
    op.create_index("tariffs_club_active_ix", "tariffs", ["club_id", "is_active"])


def _club_settings() -> None:
    op.execute(
        sa.text(
            """
            -- Ilgari bularning hammasi `modules/bookings/service.py` da
            -- konstanta edi. Klub o'zi o'zgartira olmasdi.
            ALTER TABLE clubs
                ADD COLUMN max_advance_days   integer NOT NULL DEFAULT 14,
                ADD COLUMN min_booking_hours  integer NOT NULL DEFAULT 1,
                ADD COLUMN max_booking_hours  integer NOT NULL DEFAULT 6,
                ADD COLUMN extend_max_hours   integer NOT NULL DEFAULT 3,
                ADD COLUMN slot_step_min      integer NOT NULL DEFAULT 30,
                ADD COLUMN prepay_hours       integer NOT NULL DEFAULT 1;

            ALTER TABLE clubs
                ADD CONSTRAINT clubs_advance_days_ck
                    CHECK (max_advance_days BETWEEN 1 AND 365),
                ADD CONSTRAINT clubs_booking_hours_ck
                    CHECK (min_booking_hours >= 1
                           AND max_booking_hours >= min_booking_hours
                           AND max_booking_hours <= 12),
                ADD CONSTRAINT clubs_extend_hours_ck
                    CHECK (extend_max_hours BETWEEN 1 AND 12),
                ADD CONSTRAINT clubs_slot_step_ck
                    CHECK (slot_step_min IN (15, 30, 60)),
                ADD CONSTRAINT clubs_prepay_hours_ck
                    CHECK (prepay_hours BETWEEN 0 AND 12);
            """
        )
    )


def _booking_play_amount() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE bookings ADD COLUMN play_amount bigint NOT NULL DEFAULT 0;
            ALTER TABLE bookings
                ADD CONSTRAINT bookings_play_amount_nonneg_ck CHECK (play_amount >= 0);
            """
        )
    )


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


ROOMS_FROM_LABELS = """
    INSERT INTO rooms (club_id, name, kind)
    SELECT DISTINCT club_id, room_label, room_label FROM stations
    ON CONFLICT (club_id, name) DO NOTHING
"""

LINK_STATIONS = """
    UPDATE stations s SET room_id = r.id
      FROM rooms r
     WHERE r.club_id = s.club_id AND r.name = s.room_label AND s.room_id IS NULL
"""

FILL_PLAY_AMOUNT = "UPDATE bookings SET play_amount = rate_snapshot * hours WHERE play_amount = 0"


def _backfill() -> None:
    """Xonalarni matn ustunidan quradi va bron summasini to'ldiradi.

    `stations`/`bookings` da RLS BOR va u migratsiya egasiga ham tegishli —
    mos GUC yo'q, ya'ni FORCE olinmasa `SELECT` jimgina 0 qator qaytarardi
    va ko'chirish "muvaffaqiyatli" tugardi (`docs/HOLAT.md` §4.1).
    """
    conn = op.get_bind()
    exempt = _exempt(conn)
    scoped = ("stations", "bookings")
    if not exempt:
        _scoped_force(conn, scoped, enabled=False)
    try:
        conn.execute(sa.text(ROOMS_FROM_LABELS))
        conn.execute(sa.text(LINK_STATIONS))
        conn.execute(sa.text(FILL_PLAY_AMOUNT))
    finally:
        if not exempt:
            _scoped_force(conn, scoped, enabled=True)


def _rls() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE rooms   ENABLE ROW LEVEL SECURITY;
            ALTER TABLE rooms   FORCE  ROW LEVEL SECURITY;
            ALTER TABLE tariffs ENABLE ROW LEVEL SECURITY;
            ALTER TABLE tariffs FORCE  ROW LEVEL SECURITY;

            -- Xona: klub `active` bo'lsa HAR KIM o'qiydi (mijoz bron
            -- qilishdan oldin ko'radi) — `stations_read` bilan bir xil
            -- naqsh. Yozish faqat OWNER/ADMIN.
            CREATE POLICY rooms_read ON rooms FOR SELECT
                USING (
                    EXISTS (SELECT 1 FROM clubs c
                             WHERE c.id = rooms.club_id AND c.status = 'active')
                    OR club_id = app_club_id()
                );

            CREATE POLICY rooms_write ON rooms FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'));

            -- Tarif ham ochiq o'qiladi: mijoz narxni bron qilishdan OLDIN
            -- ko'rishi kerak, aks holda u faqat tasdiqdan keyin ma'lum
            -- bo'lardi.
            CREATE POLICY tariffs_read ON tariffs FOR SELECT
                USING (
                    EXISTS (SELECT 1 FROM clubs c
                             WHERE c.id = tariffs.club_id AND c.status = 'active')
                    OR club_id = app_club_id()
                );

            CREATE POLICY tariffs_write ON tariffs FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'));

            CREATE POLICY rooms_platform_read   ON rooms   FOR SELECT USING (app_platform());
            CREATE POLICY tariffs_platform_read ON tariffs FOR SELECT USING (app_platform());
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            GRANT SELECT, INSERT, UPDATE ON rooms, tariffs TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE rooms_id_seq   TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE tariffs_id_seq TO {APP_ROLE};
            GRANT SELECT ON rooms, tariffs TO {PLATFORM_ROLE};
            """
        )
    )


def _self_test() -> None:
    """Ko'chirish HAQIQATAN ishladimi va izolyatsiya joyidami."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("stations", "bookings", "rooms")
    _scoped_force(conn, scoped, enabled=False)
    try:
        orphan_stations = conn.execute(
            sa.text("SELECT count(*) FROM stations WHERE room_id IS NULL")
        ).scalar_one()
        # Tekshirilayotgani — ko'chirish ISHLADIMI. `play_amount =
        # rate_snapshot * hours` tengligini invariant sifatida yozib
        # qo'yish NOTO'G'RI bo'lardi: butun o'zgarishning maqsadi — tarif
        # oyna ichida o'zgarganda bu tenglik BUZILISHI.
        unpriced = conn.execute(
            sa.text(
                "SELECT count(*) FROM bookings"
                " WHERE play_amount = 0 AND rate_snapshot * hours > 0"
            )
        ).scalar_one()
    finally:
        _scoped_force(conn, scoped, enabled=True)

    if orphan_stations:
        raise RuntimeError(
            f"{orphan_stations} ta stansiya xonaga bog'lanmadi — "
            "ehtimol backfill RLS tomonidan jimgina filtrlangan"
        )
    if unpriced:
        raise RuntimeError(f"{unpriced} ta bronning play_amount'i to'ldirilmadi")

    _probe_isolation(conn)


def _probe_isolation(conn: sa.Connection) -> None:
    """GUC'siz yozuv RAD ETILISHINI tekshiradi.

    Policy mavjudligini `pg_policies` dan o'qish hech narsa isbotlamasdi —
    `CREATE POLICY` shu tranzaksiyada bajarilgan, ya'ni u doim bor
    (`CLAUDE.md`: migratsiya invariantni BUZISHGA urinadi).

    Klub SHU YERDA yaratiladi. Ilgari `SELECT id FROM clubs LIMIT 1`
    olinardi va bo'sh bazada probe jimgina o'tkazib yuborilardi — aynan
    `check_render_shape.py` ishlatadigan toza bazada, ya'ni invariant
    tekshirilmasdan yashil natija chiqardi.
    """
    scoped = ("users", "organizations", "clubs")
    _scoped_force(conn, scoped, enabled=False)
    owner_id = org_id = club_id = None
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'tariffs.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:u, 'Tariffs Probe Org', 'active') RETURNING id"
            ),
            {"u": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Tariffs Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()

        # RAD ETISH tranzaksiyani ABORT qiladi — SAVEPOINT'siz keyingi HAR
        # QANDAY bayonot, jumladan Alembic'ning `UPDATE alembic_version`
        # bayonoti ham, "current transaction is aborted" beradi va
        # migratsiya UMUMAN qo'llanmaydi (`0028` da ham shu naqsh).
        wrote = True
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                sa.text(
                    "INSERT INTO tariffs (club_id, name, from_min, to_min, price_per_hour)"
                    " VALUES (:c, 'rls-probe', 0, 60, 1)"
                ),
                {"c": club_id},
            )
        except sa.exc.DBAPIError as exc:
            savepoint.rollback()
            # Aynan RLS rad etdimi. FK yoki CHECK xatosini "izolyatsiya
            # ishladi" deb hisoblash probe'ni ma'nosiz qilardi.
            if getattr(exc.orig, "sqlstate", None) != "42501":
                raise
            wrote = False
        else:
            savepoint.rollback()

        if wrote:
            raise RuntimeError("tariffs_write izolyatsiya qilmadi — GUC'siz yozuv qabul qilindi")
    finally:
        if club_id is not None:
            conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        if org_id is not None:
            conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        if owner_id is not None:
            conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        _scoped_force(conn, scoped, enabled=True)
