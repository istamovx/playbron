"""To'lov cheki — mijoz botga rasm yuborganda `bookings`ni yangilash.

Reja #37 (loyiha egasi, 2026-08-16). Webhook'da odatiy RLS konteksti yo'q
(`app.user_id`/`app.club_id` GUC) — Telegram xom HTTP so'rov yuboradi,
sessiya emas. `bookings`ga oddiy UPDATE jimgina 0 qatorga tegadi
(`[[playbron-grant-vs-rls-blind-spot]]` bilan bir xil sinf muammo,
`0022_bot_menu_context.py`dagi bilan bir xil yechim: `app_bot_lookup_claim()`
GUC'ini `bookings`ga ham SELECT+UPDATE policy sifatida qo'shish).

`bot_submit_payment_proof(p_telegram_id, p_file_id)` SECURITY DEFINER —
shu mijozning eng so'nggi `PENDING` bronini `SUBMITTED`ga o'tkazadi,
xodimlarga bildirishnoma yuborish uchun kerakli kontekstni qaytaradi.

Revision ID: 0025_payment_proof_bot
Revises: 0024_payment_proof
"""

import sqlalchemy as sa
from alembic import op

revision = "0025_payment_proof_bot"
down_revision = "0024_payment_proof"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"


def upgrade() -> None:
    _rls()
    _function()
    _self_test()


def _rls() -> None:
    op.execute(
        sa.text(
            """
            CREATE POLICY bookings_bot_lookup ON bookings FOR SELECT
                USING (app_bot_lookup_claim());
            CREATE POLICY bookings_bot_update ON bookings FOR UPDATE
                USING (app_bot_lookup_claim()) WITH CHECK (app_bot_lookup_claim());

            -- `stations` HAM kerak: pastdagi funksiya `UPDATE ... FROM
            -- stations s, clubs c` qiladi va JOIN uchun SELECT huquqi
            -- talab qilinadi. Bu policy DASTLAB UNUTILGAN edi — natijada
            -- BYPASSRLS'siz bazada (Render) join bo'sh qaytardi, UPDATE
            -- hech qanday qatorga tegmasdi va `_self_test()` "holat
            -- SUBMITTED'ga o'tmadi" bilan yiqilib, DEPLOYNI to'sardi.
            -- Lokal superuser buni yashirgan (`_exempt()` self-testni
            -- o'tkazib yuboradi). `[[playbron-rls-cross-table-subquery-gap]]`.
            CREATE POLICY stations_bot_lookup ON stations FOR SELECT
                USING (app_bot_lookup_claim());
            """
        )
    )


def _function() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION bot_submit_payment_proof(
                p_telegram_id bigint, p_file_id text
            )
                RETURNS TABLE(booking_id bigint, club_id bigint, club_name text,
                              station_code text)
                LANGUAGE plpgsql SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                v_user_id bigint;
            BEGIN
                PERFORM set_config('app.bot_lookup', 'true', true);

                SELECT u.id INTO v_user_id FROM users u
                 WHERE u.kind = 'customer' AND u.telegram_id = p_telegram_id;
                IF v_user_id IS NULL THEN
                    PERFORM set_config('app.bot_lookup', '', true);
                    RETURN;
                END IF;

                RETURN QUERY
                UPDATE bookings b SET
                    payment_proof_file_id = p_file_id,
                    payment_proof_status = 'SUBMITTED',
                    payment_proof_submitted_at = now()
                FROM stations s, clubs c
                WHERE b.id = (
                        SELECT id FROM bookings
                         WHERE customer_id = v_user_id AND payment_proof_status = 'PENDING'
                         ORDER BY created_at DESC LIMIT 1
                      )
                  AND s.id = b.station_id AND c.id = b.club_id
                RETURNING b.id, b.club_id, c.name::text, s.code::text;

                PERFORM set_config('app.bot_lookup', '', true);
            END
            $fn$;

            GRANT EXECUTE ON FUNCTION bot_submit_payment_proof(bigint, text) TO {APP_ROLE};
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
    """Mijoz PENDING bronga rasm yuborsa — SUBMITTED bo'lishi, kontekst
    to'g'ri qaytishi; PENDING bron yo'q mijoz uchun bo'sh bo'lishi kerak."""
    conn = op.get_bind()
    exempt = _exempt(conn)

    scoped = ("users", "organizations", "clubs", "stations", "memberships", "bookings")
    if not exempt:
        _force_rls(conn, scoped, enabled=False)
    try:
        customer_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, telegram_id, status, first_name)"
                " VALUES ('customer', 900000201, 'active', 'Sinov')"
                " RETURNING id"
            )
        ).scalar_one()
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'proof.probe.owner', 'active', 'Owner') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Proof Probe Org', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Proof Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        station_id = conn.execute(
            sa.text(
                "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                " VALUES (:c, 'PRF-1', 'Standart', 'ps5', 30000) RETURNING id"
            ),
            {"c": club_id},
        ).scalar_one()
        booking_id = conn.execute(
            sa.text(
                "INSERT INTO bookings"
                " (club_id, station_id, customer_id, source, status, period, hours,"
                "  rate_snapshot, console_type, payment_proof_status)"
                " VALUES (:c, :s, :u, 'MINIAPP', 'CONFIRMED',"
                "         tstzrange(now() - interval '1 hour', now()), 1, 30000, 'ps5',"
                "         'PENDING') RETURNING id"
            ),
            {"c": club_id, "s": station_id, "u": customer_id},
        ).scalar_one()
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=True)

    try:
        row = conn.execute(
            sa.text("SELECT * FROM bot_submit_payment_proof(900000201, 'file-abc')")
        ).first()
        if row is None or row.booking_id != booking_id or row.club_id != club_id:
            raise RuntimeError("bot_submit_payment_proof: PENDING bron topilmadi/yangilanmadi")

        empty = conn.execute(
            sa.text("SELECT * FROM bot_submit_payment_proof(999999999, 'file-xyz')")
        ).first()
        if empty is not None:
            raise RuntimeError("bot_submit_payment_proof: noma'lum telegram_id uchun natija qaytdi")
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=False)

        # Natijani QAYTA O'QISH — FORCE RLS o'chirilgandan KEYIN. Migratsiya
        # sessiyasida `app.bot_lookup` GUC'i yo'q (uni funksiya o'z ichida,
        # o'z tranzaksiyasida qo'yadi), shuning uchun FORCE RLS ostida
        # `bookings` bu yerda KO'RINMAYDI va o'qish 0 qator qaytaradi.
        # Avval bu tekshiruv yuqorida, RLS yoqilgan holda turardi va
        # "holat SUBMITTED'ga o'tmadi" deb YOLG'ON yiqilardi — funksiyaning
        # o'zi to'g'ri ishlagan bo'lsa ham. Buni faqat BYPASSRLS'siz muhit
        # ko'rsatadi (Render), lokal superuser self-testni umuman
        # o'tkazib yuboradi (`_exempt()`).
        status = conn.execute(
            sa.text(
                "SELECT payment_proof_status, payment_proof_file_id FROM bookings WHERE id = :i"
            ),
            {"i": booking_id},
        ).first()
        submitted = (
            status is not None
            and status.payment_proof_status == "SUBMITTED"
            and status.payment_proof_file_id == "file-abc"
        )

        conn.execute(sa.text("DELETE FROM bookings WHERE id = :i"), {"i": booking_id})
        conn.execute(sa.text("DELETE FROM stations WHERE id = :i"), {"i": station_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :i"), {"i": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :i"), {"i": org_id})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:c, :o)"), {"c": customer_id, "o": owner_id}
        )
        if not exempt:
            _force_rls(conn, scoped, enabled=True)

        # Tozalashdan KEYIN — aks holda xato tashlansa sinov qatorlari
        # bazada qolib ketardi.
        if not submitted:
            raise RuntimeError(
                "bot_submit_payment_proof: holat SUBMITTED'ga o'tmadi"
                f" (o'qilgan: {status})"
            )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
