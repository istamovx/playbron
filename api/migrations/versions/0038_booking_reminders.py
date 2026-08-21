"""Bron eslatmasi — boshlanishidan 20 daqiqa oldin mijozga.

Loyiha egasining so'rovi (2026-08-18): tasdiq xabari bilan bir xil
kartochka bron boshlanishidan oldin YANA bir marta yuborilsin.

## Nega alohida GUC kerak

Eslatmani yuboruvchi FON VAZIFASI — hech qanday so'rov konteksti yo'q,
ya'ni `app.club_id`/`app.user_id` bo'sh. Ilova roli (`playbron_app`) esa
RLS ostida: GUC'siz `SELECT` jimgina 0 qator qaytaradi va eslatma hech
qachon ketmasdi — bu loyihada bir necha marta takrorlangan tuzoq
(`docs/HOLAT.md` §4.1).

Shuning uchun `docs/07-patterns.md` dagi naqsh: `SECURITY DEFINER`
funksiya + NOMLANGAN claim GUC (`app.reminder_job`), funksiyaning O'ZI
uni o'rnatadi va qaytishdan OLDIN tozalaydi. Chaqiruvchi kod uni
o'rnata olmaydi.

## Nega da'vo (claim) UPDATE bilan

`reminder_sent_at` yuborishdan OLDIN, ATOMAR tarzda belgilanadi
(`UPDATE ... RETURNING`). Aks holda ikkita ishlovchi nusxa (yoki qayta
ishga tushirish) bitta bronga ikki marta xabar yuborardi. `FOR UPDATE
SKIP LOCKED` — parallel nusxalar bir-birini kutmasin.

Revision ID: 0038_booking_reminders
Revises: 0037_rooms_tariffs
"""

import sqlalchemy as sa
from alembic import op

revision = "0038_booking_reminders"
down_revision = "0037_rooms_tariffs"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"


def upgrade() -> None:
    _column()
    _claim_gucs()
    _policies()
    _function()
    _grants()
    _self_test()


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")


def _column() -> None:
    op.execute(
        sa.text("ALTER TABLE bookings ADD COLUMN reminder_sent_at timestamptz")
    )
    # Faqat hali eslatilmagan, yaqin bronlar — indeks tor bo'lsin.
    op.execute(
        sa.text(
            "CREATE INDEX bookings_reminder_due_ix ON bookings (lower(period))"
            " WHERE reminder_sent_at IS NULL AND status = 'CONFIRMED'"
        )
    )


def _claim_gucs() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_reminder_job() RETURNS boolean
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(current_setting('app.reminder_job', true), '') = 'true' $$;
            """
        )
    )


def _policies() -> None:
    op.execute(
        sa.text(
            """
            -- Bron: o'qish VA `reminder_sent_at` ni belgilash.
            CREATE POLICY bookings_reminder_job ON bookings FOR ALL
                USING (app_reminder_job())
                WITH CHECK (app_reminder_job());

            -- Xabar matni uchun kerak bo'lgan minimal o'qishlar.
            CREATE POLICY clubs_reminder_job    ON clubs    FOR SELECT USING (app_reminder_job());
            CREATE POLICY stations_reminder_job ON stations FOR SELECT USING (app_reminder_job());
            CREATE POLICY rooms_reminder_job    ON rooms    FOR SELECT USING (app_reminder_job());
            CREATE POLICY users_reminder_job    ON users    FOR SELECT USING (app_reminder_job());
            """
        )
    )


def _function() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION claim_due_booking_reminders(p_lead_min integer)
            RETURNS TABLE (
                booking_id  bigint,
                telegram_id bigint,
                club_name   text,
                room_label  text,
                starts_at   timestamptz,
                hours       integer,
                timezone    text
            )
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            BEGIN
                PERFORM set_config('app.reminder_job', 'true', true);

                RETURN QUERY
                WITH due AS (
                    SELECT b.id
                      FROM bookings b
                     WHERE b.status = 'CONFIRMED'
                       AND b.reminder_sent_at IS NULL
                       AND b.customer_id IS NOT NULL
                       AND lower(b.period) > now()
                       AND lower(b.period) <= now() + make_interval(mins => p_lead_min)
                     FOR UPDATE SKIP LOCKED
                ), claimed AS (
                    UPDATE bookings b SET reminder_sent_at = now()
                      FROM due
                     WHERE b.id = due.id
                    RETURNING b.id, b.club_id, b.station_id, b.customer_id,
                              lower(b.period) AS starts_at, b.hours
                )
                SELECT c.id,
                       u.telegram_id,
                       cl.name::text,
                       COALESCE(r.name, s.room_label)::text,
                       c.starts_at,
                       c.hours,
                       cl.timezone::text
                  FROM claimed c
                  JOIN clubs    cl ON cl.id = c.club_id
                  JOIN stations s  ON s.id  = c.station_id
                  LEFT JOIN rooms r ON r.id = s.room_id
                  JOIN users    u  ON u.id  = c.customer_id
                 WHERE u.telegram_id IS NOT NULL
                   AND u.tg_blocked_at IS NULL;

                -- Claim'ni DARHOL yopamiz: u tranzaksiya oxirigacha ochiq
                -- qolsa, chaqiruvchi kod shu tranzaksiyada boshqa klubning
                -- ma'lumotini ham o'qiy olardi (`0009` dagi bilan bir xil).
                PERFORM set_config('app.reminder_job', '', true);
                RETURN;
            EXCEPTION WHEN OTHERS THEN
                -- Xato ham QAYTISH yo'li. `CLAUDE.md` fon vazifasi naqshi:
                -- funksiya claim'ni qaytishdan OLDIN tozalaydi — istisnosiz.
                PERFORM set_config('app.reminder_job', '', true);
                RAISE;
            END
            $fn$;

            REVOKE ALL ON FUNCTION claim_due_booking_reminders(integer) FROM PUBLIC;
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(f"GRANT EXECUTE ON FUNCTION claim_due_booking_reminders(integer) TO {APP_ROLE}")
    )


def _exempt(conn: sa.Connection) -> bool:
    return bool(
        conn.execute(
            sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).scalar()
    )


def _self_test() -> None:
    """Claim tozalanadimi — ya'ni funksiya chaqirilgandan KEYIN
    `app.reminder_job` orqali hech narsa ochiq qolmaydimi.

    Bu aynan buzilishi mumkin bo'lgan invariant: `set_config(..., true)`
    TRANZAKSIYA doirasida ishlaydi, funksiya doirasida emas. Tozalash
    unutilsa chaqiruvchi o'sha tranzaksiyada butun bazani o'qiy olardi.
    """
    conn = op.get_bind()
    if _exempt(conn):
        return

    # Yetakchi oyna 0 — `lower(period) > now() AND <= now()` hech qachon
    # rost bo'lmaydi, ya'ni birorta qator DA'VO QILINMAYDI. Ilgari bu yerda
    # `20` turardi: funksiya VOLATILE va `UPDATE ... SET reminder_sent_at`
    # bajaradi, demak 19:45 da ketgan deploy 20:00 gacha boshlanadigan
    # bronlarni "eslatilgan" deb belgilab qo'yardi va o'sha mijozlar
    # xabarni HECH QACHON olmasdi. Tekshirilayotgan invariant — claim'ning
    # tozalanishi — ish hajmiga bog'liq emas.
    conn.execute(sa.text("SELECT * FROM claim_due_booking_reminders(0)"))
    leaked = conn.execute(sa.text("SELECT app_reminder_job()")).scalar()
    if leaked:
        raise RuntimeError(
            "claim_due_booking_reminders() `app.reminder_job` ni tozalamadi — "
            "chaqiruvchi tranzaksiyada cross-tenant o'qish ochiq qoladi"
        )
