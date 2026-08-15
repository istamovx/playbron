"""Bron domeni: xonalar (stations), bronlar, xodimga/mijozga bildirishnoma.

Manba: `docs/01-architecture.md` (EXCLUDE konstreynt rejasi) va loyiha
egasining so'rovi (2026-08-15) — to'lovsiz oqim, xodim qo'lda bron ochishi.

**Bosqich 1 (hozir): to'lovsiz.** Mijoz bron qiladi → `PENDING` → xodim
tasdiqlaydi → `CONFIRMED` → mijozga botda xabar. To'lov (`prepaid_amount`)
ustuni bor, lekin HAMMA yozuvda 0 — `packages/ui/src/format.ts` dagi
`prepayAmount()`/`PREPAY_HOURS` formulasi o'zgarishsiz qoladi, keyingi
bosqichda shu ustunga yozila boshlaydi.

**Ikki manba, bitta jadval** (`0005`dagi `users.kind` bilan bir xil naqsh):

  * `MINIAPP` — mijoz o'zi, `customer_id` bilan, `status='PENDING'`
  * `STAFF`   — xodim telefon/kelib bron qiladi, `guest_name`/`guest_phone`
    bilan (mijozning ilovada hisobi YO'Q), `status='CONFIRMED'` DARHOL —
    xodimning o'zi tasdiqlovchi, ikkinchi bosqich shart emas

Ajratish CHECK bilan majburlanadi, ilova qatlamida emas.

**`bookings_no_overlap`** — `docs/01-architecture.md` da reja qilingan
EXCLUDE konstreynt, endi haqiqiy: bitta xonada ikkita `PENDING`/`CONFIRMED`
bron bir vaqtda bo'la olmaydi. `23P01` → `core/errors.py` dagi global
handler orqali `409 SLOT_TAKEN` (allaqachon bor, `bookings`ga tegishli
kod yozilishini kutib turgan edi).

**Bildirishnoma — ikki yo'nalish, ikkalasi ham cross-tenant o'qish talab
qiladi va shu sabab SECURITY DEFINER + GUC-gated policy kerak
(`[[render-free-tier-no-bypassrls]]` — BYPASSRLS'siz muhitda oddiy
SECURITY DEFINER RLS'ni o'chirmaydi):**

  1. Mijoz bron yuborganda XODIMLARGA — chaqiruvchi mijoz, uning
     `app.club_id` umuman yo'q (mijoz tokenida klub konteksti yo'q),
     ya'ni `staff_telegram`ni o'qish uchun club_id'ni FUNKSIYANING O'ZI
     parametr sifatida oladi va `app.booking_notify_club` GUC'ini
     ICHKARIDA o'rnatadi.
  2. Xodim tasdiqlaganda MIJOZGA — chaqiruvchi xodim, `app.club_id`
     to'g'ri, lekin `users_self` faqat o'z qatorini ochadi. Yangi
     `users_booking_contact` policy'si: agar mijozning shu klubda
     (`app.club_id`) faol bronlari bo'lsa, klub xodimlari uning
     `users` qatorini (demak `telegram_id`) o'qiy oladi — aynan shu
     ish uchun zarur va undan ortiq emas.

Revision ID: 0009_bookings
Revises: 0008_owner_signup
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TSTZRANGE

revision = "0009_bookings"
down_revision = "0008_owner_signup"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"

CONSOLE_TYPES = ("ps3", "ps4", "ps4pro", "ps5", "ps5pro")


def upgrade() -> None:
    _extension()
    _tables()
    _rls()
    _claim_functions()
    _notify_support()
    _grants()
    _assert_overlap_is_rejected()


def _extension() -> None:
    # `EXCLUDE USING gist` uchun — `=` operatorini gist indeksida ishlatish
    # shu kengaytmasiz mumkin emas (bigint ustida ham).
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS btree_gist"))


def _tables() -> None:
    op.create_table(
        "stations",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("code", sa.String(16), nullable=False),
        # Prototipdagi "xona kategoriyasi" — Standart/Turnir/VIP. Erkin matn:
        # klub o'zi nomlaydi, qattiq ro'yxat emas.
        sa.Column("room_label", sa.String(32), nullable=False, server_default="Standart"),
        sa.Column("console_type", sa.String(16), nullable=False),
        # so'm/soat, butun son (CLAUDE.md: pul — bigint, kasrsiz)
        sa.Column("rate", sa.BigInteger, nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(f"console_type IN {CONSOLE_TYPES}", name="stations_console_type_ck"),
        sa.CheckConstraint("status IN ('active', 'maintenance')", name="stations_status_ck"),
        sa.CheckConstraint("rate > 0", name="stations_rate_positive_ck"),
        sa.UniqueConstraint("club_id", "code", name="stations_club_code_uk"),
    )
    op.create_index("stations_club_ix", "stations", ["club_id"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "station_id",
            sa.BigInteger,
            sa.ForeignKey("stations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # `MINIAPP` yo'lida bor, `STAFF` yo'lida NULL
        sa.Column("customer_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        # `STAFF` yo'lida bor: mijozning ilovada hisobi yo'q, u faqat ism/
        # telefon bilan qog'ozsiz yoziladi (`docs` — "qog'ozbozlikdan qutilish")
        sa.Column("guest_name", sa.String(128), nullable=True),
        sa.Column("guest_phone", sa.String(20), nullable=True),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        # `tstzrange` — EXCLUDE konstreynt shuni talab qiladi, alohida
        # `starts_at`/`ends_at` ustida GIST bilan bir xil samarada ishlamaydi
        sa.Column("period", TSTZRANGE, nullable=False),
        sa.Column("hours", sa.Integer, nullable=False),
        # Bron paytidagi narx — stansiya keyinchalik narxini o'zgartirsa ham
        # eski bron o'zgarmaydi
        sa.Column("rate_snapshot", sa.BigInteger, nullable=False),
        # Bosqich 1: HAMMA yozuvda 0. Ustun endi bor — Bosqich 2 to'lovni
        # qo'shganda migratsiya emas, faqat yozish mantig'i o'zgaradi.
        sa.Column("prepaid_amount", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("source IN ('MINIAPP', 'STAFF')", name="bookings_source_ck"),
        sa.CheckConstraint(
            "status IN ('PENDING', 'CONFIRMED', 'CANCELLED')", name="bookings_status_ck"
        ),
        sa.CheckConstraint("hours > 0 AND hours <= 12", name="bookings_hours_range_ck"),
        sa.CheckConstraint("rate_snapshot > 0", name="bookings_rate_positive_ck"),
        sa.CheckConstraint("prepaid_amount >= 0", name="bookings_prepaid_nonneg_ck"),
        # Ikki dunyo — `users.kind` bilan bir xil falsafa: shakl DB'da
        # majburlanadi, ilova qatlamida emas.
        sa.CheckConstraint(
            "(source = 'STAFF' AND customer_id IS NULL AND guest_name IS NOT NULL)"
            " OR (source = 'MINIAPP' AND customer_id IS NOT NULL AND guest_name IS NULL"
            "     AND guest_phone IS NULL)",
            name="bookings_source_shape_ck",
        ),
    )
    op.create_index("bookings_club_ix", "bookings", ["club_id"])
    op.create_index("bookings_customer_ix", "bookings", ["customer_id"])
    op.create_index("bookings_station_period_ix", "bookings", ["station_id", "period"])

    # Bitta xonada ikkita FAOL (PENDING yoki CONFIRMED) bron bir vaqtda
    # bo'la olmaydi. `23P01` — `core/errors.py` global handler'i buni
    # `409 SLOT_TAKEN`ga aylantiradi (kod allaqachon bor edi).
    op.execute(
        sa.text(
            "ALTER TABLE bookings ADD CONSTRAINT bookings_no_overlap"
            " EXCLUDE USING gist (station_id WITH =, period WITH &&)"
            " WHERE (status IN ('PENDING', 'CONFIRMED'))"
        )
    )


def _rls() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE stations ENABLE ROW LEVEL SECURITY;
            ALTER TABLE stations FORCE ROW LEVEL SECURITY;
            ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;
            ALTER TABLE bookings FORCE ROW LEVEL SECURITY;

            -- Stansiyalar: klub `active` bo'lsa HAR KIM o'qiydi (mijoz
            -- klub tanlashdan oldin ko'radi) — `clubs_read`dagi naqsh bilan
            -- bir xil. Yozish faqat OWNER/ADMIN, o'z klubida.
            CREATE POLICY stations_read ON stations FOR SELECT
                USING (
                    EXISTS (SELECT 1 FROM clubs c WHERE c.id = stations.club_id
                             AND c.status = 'active')
                    OR club_id = app_club_id()
                );

            CREATE POLICY stations_write ON stations FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN'));

            -- Bronlar: mijoz FAQAT o'zinikini, xodim FAQAT o'z klubinikini.
            CREATE POLICY bookings_customer_read ON bookings FOR SELECT
                USING (customer_id = app_user_id());

            CREATE POLICY bookings_customer_insert ON bookings FOR INSERT
                WITH CHECK (
                    customer_id = app_user_id()
                    AND source = 'MINIAPP'
                    AND status = 'PENDING'
                );

            CREATE POLICY bookings_staff_all ON bookings FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'));
            """
        )
    )


def _claim_functions() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_booking_notify_claim() RETURNS bigint
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT NULLIF(current_setting('app.booking_notify_club', true), '')::bigint $$;
            """
        )
    )


def _notify_support() -> None:
    """Ikki yo'nalishdagi bildirishnoma uchun tor yo'llar."""
    op.execute(
        sa.text(
            """
            -- 1) Mijoz bron yuborganda — XODIMLARGA. `staff_telegram_self`
            -- (0005) faqat o'zinikini ochadi; bu policy funksiya ICHIDA
            -- o'rnatilgan `app.booking_notify_club` GUC'iga qarab, o'sha
            -- klubning xodimlari qatorini ochadi.
            CREATE POLICY staff_telegram_booking_notify ON staff_telegram FOR SELECT
                USING (
                    app_booking_notify_claim() IS NOT NULL
                    AND EXISTS (
                        SELECT 1 FROM memberships m
                        WHERE m.user_id = staff_telegram.user_id
                          AND m.club_id = app_booking_notify_claim()
                          AND m.status = 'active'
                    )
                );

            -- 2) Xodim tasdiqlaganda — MIJOZGA. `users_self` faqat o'z
            -- qatorini ochadi. Agar mijozning FAOL (PENDING/CONFIRMED)
            -- broni shu klubda (`app.club_id` — xodim so'rovida to'g'ri
            -- keladi) bo'lsa, o'sha klub xodimlari uning `users` qatorini
            -- (demak `telegram_id`ni) o'qiy oladi. Aynan shu ish uchun
            -- zarur va undan ortiq emas — boshqa klubning mijozi ko'rinmaydi.
            CREATE POLICY users_booking_contact ON users FOR SELECT
                USING (
                    kind = 'customer'
                    AND app_club_id() <> 0
                    AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF')
                    AND EXISTS (
                        SELECT 1 FROM bookings b
                        WHERE b.customer_id = users.id
                          AND b.club_id = app_club_id()
                          AND b.status IN ('PENDING', 'CONFIRMED')
                    )
                );

            CREATE OR REPLACE FUNCTION booking_notify_targets(p_club_id bigint)
                RETURNS TABLE(chat_id bigint)
                LANGUAGE plpgsql STABLE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            BEGIN
                -- Chaqiruvchi (mijoz) bu klubda hech qanday standart huquqqa
                -- ega emas — GUC shu funksiya ICHIDA, faqat shu so'rov uchun
                -- o'rnatiladi va darhol tozalanadi.
                PERFORM set_config('app.booking_notify_club', p_club_id::text, true);

                RETURN QUERY
                SELECT st.chat_id FROM staff_telegram st
                WHERE st.chat_id IS NOT NULL AND st.blocked_at IS NULL
                  AND EXISTS (
                      SELECT 1 FROM memberships m
                      WHERE m.user_id = st.user_id AND m.club_id = p_club_id
                        AND m.status = 'active'
                  );

                PERFORM set_config('app.booking_notify_club', '', true);
            END
            $fn$;

            REVOKE ALL ON FUNCTION booking_notify_targets(bigint) FROM PUBLIC;
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            GRANT SELECT ON stations, bookings TO {APP_ROLE};
            GRANT INSERT, UPDATE ON stations, bookings TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE stations_id_seq TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE bookings_id_seq TO {APP_ROLE};

            DO $do$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                    ALTER FUNCTION booking_notify_targets(bigint) OWNER TO {PLATFORM_ROLE};
                    GRANT SELECT ON staff_telegram, memberships TO {PLATFORM_ROLE};
                END IF;
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'booking_notify_targets egasi o''zgartirilmadi (huquq yo''q)';
            END
            $do$;

            GRANT EXECUTE ON FUNCTION booking_notify_targets(bigint) TO {APP_ROLE};
            """
        )
    )


def _assert_overlap_is_rejected() -> None:
    """`bookings_no_overlap` haqiqatan ikkita mos keluvchi bronni to'xtatadi.

    Bu tekshiruv superuser/BYPASSRLS'dan qat'i nazar ma'noli — u FAQAT
    konstreyntning o'zini sinaydi (RLS'ga bog'liq emas), lekin baribir
    yozuv uchun `NO FORCE` va tozalash kerak (RLS yozishga xalaqit bermasin).
    """
    conn = op.get_bind()

    scoped = ("clubs", "organizations", "users", "stations", "bookings")
    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))

    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'migration.bkprobe', 'active', 'probe') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                " VALUES (:o, 'probe', 'active', NULL) RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'probe', 'active')"
                " RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        station_id = conn.execute(
            sa.text(
                "INSERT INTO stations (club_id, code, console_type, rate)"
                " VALUES (:c, 'PROBE', 'ps5', 30000) RETURNING id"
            ),
            {"c": club_id},
        ).scalar_one()

        conn.execute(
            sa.text(
                "INSERT INTO bookings (club_id, station_id, customer_id, source, status,"
                " period, hours, rate_snapshot)"
                " VALUES (:c, :s, :u, 'MINIAPP', 'PENDING',"
                " tstzrange(now(), now() + interval '1 hour'), 1, 30000)"
            ),
            {"c": club_id, "s": station_id, "u": owner_id},
        )

        raised = False
        try:
            with conn.begin_nested():
                conn.execute(
                    sa.text(
                        "INSERT INTO bookings (club_id, station_id, customer_id, source,"
                        " status, period, hours, rate_snapshot)"
                        " VALUES (:c, :s, :u, 'MINIAPP', 'PENDING',"
                        " tstzrange(now() + interval '30 minutes',"
                        "           now() + interval '90 minutes'), 1, 30000)"
                    ),
                    {"c": club_id, "s": station_id, "u": owner_id},
                )
        except sa.exc.DBAPIError as exc:
            raised = getattr(getattr(exc, "orig", None), "sqlstate", None) == "23P01"

        if not raised:
            raise RuntimeError(
                "bookings_no_overlap kesishgan bronni to'xtatmadi — EXCLUDE"
                " konstreynti kutilganidek ishlamayapti"
            )
    finally:
        conn.execute(sa.text("DELETE FROM organizations WHERE name = 'probe'"))
        conn.execute(
            sa.text("DELETE FROM users WHERE login = 'migration.bkprobe' AND kind = 'staff'")
        )
        for table in scoped:
            conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
