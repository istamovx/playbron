"""`club_publish()` — klub egasi o'zi klubni faollashtiradi.

**Muhim aniqlik** (`0008_owner_signup.py` izohidan): klub `draft'da yaratiladi
va **egasining o'zi** uni to'ldirib faollashtira oladi — bu super admin
tasdig'iga BOG'LIQ EMAS. `organizations.status='pending'` (tarifsiz) alohida
o'q: u `load_entitlements()`da faqat bo'sh limit qaytaradi (Faza 1, hali hech
narsa majburlanmaydi), bron yoki kirishni bloklamaydi — shuning uchun bu
migratsiya FAQAT `clubs.status`ga tegadi, `organizations.status`ga emas.

Nega hozirgacha yo'q edi: `clubs.status` ustuni `playbron_app`dan ATAYLAB
column-level REVOKE qilingan (`0003_rls_hardening.py`) — xodim/egasi
o'zini o'zi to'g'ridan-to'g'ri UPDATE bilan faollashtirib qo'ymasin
(tekshiruvsiz "active" yozib qo'yish xavfi). Ya'ni yagona yo'l — shu
funksiya: OWNER/ADMIN ekanini VA kamida bitta faol xona borligini
(mijozga bo'sh klub ko'rsatilmasin) ICHKARIDA tekshiradi.

`[[render-free-tier-no-bypassrls]]`: `playbron_platform` ALTER ROLE
BYPASSRLS Render'da o'tmaydi (faqat superuser), shuning uchun bu funksiya
ham har doimgidek — o'z ichida GUC o'rnatib, o'sha GUC'ga qaragan tor
policy orqali yozadi, PLATFORM_ROLE'ning "avtomatik bypass" degan
noto'g'ri taxminiga tayanmaydi.

Revision ID: 0012_club_publish
Revises: 0011_staff_roster
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_club_publish"
down_revision = "0011_staff_roster"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"


def upgrade() -> None:
    _add_publish_support()
    _grants()
    _assert_owner_can_publish_with_station()
    _assert_publish_without_station_is_rejected()


def _add_publish_support() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_club_publish_claim() RETURNS bigint
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT NULLIF(current_setting('app.club_publish_target', true), '')::bigint $$;

            -- Yagona yozish yo'li `clubs.status`ga (ustun `0003`da APP_ROLE'dan
            -- REVOKE qilingan). SELECT'ga tegmaydi.
            CREATE POLICY clubs_publish ON clubs FOR UPDATE
                USING (id = app_club_publish_claim())
                WITH CHECK (id = app_club_publish_claim());

            -- Funksiya ICHIDA stansiyalarni ham tekshiradi (kamida bitta
            -- faol xona bormi) — `stations_read` (`0009`) klub HALI 'active'
            -- emasligi sabab bu bosqichda hech narsa ochmaydi
            -- (`[[playbron-rls-cross-table-subquery-gap]]`), shuning uchun
            -- bir xil GUC bilan gated qo'shimcha o'qish policy'si kerak.
            CREATE POLICY stations_publish_read ON stations FOR SELECT
                USING (club_id = app_club_publish_claim());

            CREATE OR REPLACE FUNCTION club_publish(p_club_id bigint) RETURNS text
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                actor      bigint := app_user_id();
                actor_role text;
                cur_status text;
                has_station boolean;
            BEGIN
                IF actor IS NULL OR actor = 0 THEN
                    RETURN 'NOT_AUTHENTICATED';
                END IF;

                -- Avtorizatsiya JADVALDAN, GUC'dan emas — `auth_create_staff`
                -- (`0006`) bilan bir xil naqsh. Chaqiruvchining O'Z qatori
                -- `memberships_read`ning `user_id = app_user_id()` tarmog'i
                -- bilan har doim o'qiladi, boshqa GUC shart emas.
                SELECT m.role INTO actor_role FROM memberships m
                 WHERE m.club_id = p_club_id AND m.user_id = actor AND m.status = 'active';

                IF actor_role IS NULL OR actor_role NOT IN ('OWNER', 'ADMIN') THEN
                    RETURN 'NOT_ALLOWED';
                END IF;

                -- Qolgan tekshiruvlar shu GUC ostida — `clubs` (UPDATE) va
                -- `stations` (SELECT) uchun ikkalasi ham shu bitta claim'ga
                -- qaraydi (yuqoridagi ikki policy).
                PERFORM set_config('app.club_publish_target', p_club_id::text, true);

                SELECT status INTO cur_status FROM clubs WHERE id = p_club_id;
                IF cur_status IS NULL THEN
                    PERFORM set_config('app.club_publish_target', '', true);
                    RETURN 'NOT_FOUND';
                END IF;
                IF cur_status = 'active' THEN
                    PERFORM set_config('app.club_publish_target', '', true);
                    RETURN 'ALREADY_ACTIVE';
                END IF;

                SELECT EXISTS(
                    SELECT 1 FROM stations WHERE club_id = p_club_id AND status = 'active'
                ) INTO has_station;
                IF NOT has_station THEN
                    PERFORM set_config('app.club_publish_target', '', true);
                    RETURN 'NO_STATIONS';
                END IF;

                UPDATE clubs SET status = 'active' WHERE id = p_club_id;
                PERFORM set_config('app.club_publish_target', '', true);

                RETURN 'OK';
            END
            $fn$;

            REVOKE ALL ON FUNCTION club_publish(bigint) FROM PUBLIC;
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            -- `0008` faqat INSERT bergan edi (ro'yxatdan o'tish uchun) —
            -- UPDATE endi kerak, faqat `clubs_publish` tor policy ochadigan
            -- qatorga tegadi.
            GRANT UPDATE ON clubs TO {PLATFORM_ROLE};

            -- `0009_bookings.py` `stations`/`bookings`ga PLATFORM_ROLE uchun
            -- GRANT yozishni unutgan edi (`0003`dan beri sukut imtiyoz
            -- o'chirilgan — har bir migratsiya o'zi yozishi kerak). Shu
            -- sabab `club_publish()` ichidagi `stations` o'qishi "permission
            -- denied" berardi (RLS emas, oddiy GRANT yetishmasligi).
            GRANT SELECT ON stations TO {PLATFORM_ROLE};

            DO $do$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                    ALTER FUNCTION club_publish(bigint) OWNER TO {PLATFORM_ROLE};
                END IF;
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'club_publish egasi o''zgartirilmadi (huquq yo''q)';
            END
            $do$;

            GRANT EXECUTE ON FUNCTION club_publish(bigint) TO {APP_ROLE};
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


def _build_probe_club(conn: sa.Connection, *, with_station: bool) -> tuple[int, int]:
    scoped = ("users", "organizations", "clubs", "memberships", "stations")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', :login, 'active', 'P') RETURNING id"
            ),
            {"login": f"migration.pubprobe{'1' if with_station else '2'}"},
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                " VALUES (:o, 'pubprobe', 'pending', NULL) RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'pubprobe', 'draft')"
                " RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        conn.execute(
            sa.text(
                "INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"
            ),
            {"u": owner_id, "c": club_id},
        )
        if with_station:
            conn.execute(
                sa.text(
                    "INSERT INTO stations (club_id, code, console_type, rate, status)"
                    " VALUES (:c, 'PROBE', 'ps5', 30000, 'active')"
                ),
                {"c": club_id},
            )
    finally:
        _force_rls(conn, scoped, enabled=True)
    return owner_id, club_id


def _cleanup_probe_club(conn: sa.Connection, owner_id: int) -> None:
    scoped = ("users", "organizations", "clubs", "memberships", "stations")
    _force_rls(conn, scoped, enabled=False)
    try:
        conn.execute(
            sa.text(
                "DELETE FROM organizations WHERE owner_user_id = :u"
            ),
            {"u": owner_id},
        )
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
    finally:
        _force_rls(conn, scoped, enabled=True)


def _assert_owner_can_publish_with_station() -> None:
    conn = op.get_bind()
    if _exempt(conn):
        return

    owner_id, club_id = _build_probe_club(conn, with_station=True)
    conn.execute(
        sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(owner_id)}
    )
    result = conn.execute(sa.text("SELECT club_publish(:c)"), {"c": club_id}).scalar_one()
    conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))

    status = conn.execute(
        sa.text("SELECT status FROM clubs WHERE id = :c"), {"c": club_id}
    )
    _force_rls(conn, ("clubs",), enabled=False)
    live_status = conn.execute(
        sa.text("SELECT status FROM clubs WHERE id = :c"), {"c": club_id}
    ).scalar_one()
    _force_rls(conn, ("clubs",), enabled=True)
    status.close()

    _cleanup_probe_club(conn, owner_id)

    if result != "OK" or live_status != "active":
        raise RuntimeError(
            f"club_publish() xona bor klubni faollashtira olmadi (natija={result},"
            f" holat={live_status})"
        )


def _assert_publish_without_station_is_rejected() -> None:
    conn = op.get_bind()
    if _exempt(conn):
        return

    owner_id, club_id = _build_probe_club(conn, with_station=False)
    conn.execute(
        sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(owner_id)}
    )
    result = conn.execute(sa.text("SELECT club_publish(:c)"), {"c": club_id}).scalar_one()
    conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))

    _cleanup_probe_club(conn, owner_id)

    if result != "NO_STATIONS":
        raise RuntimeError(
            f"club_publish() xonasiz klubni rad etmadi (kutilgan NO_STATIONS, natija={result})"
        )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
