"""`memberships` policy'sidagi cheksiz rekursiyani yopish.

MUAMMO (prod'da bloklovchi). `memberships_read`, `memberships_write_owner` va
`memberships_write_admin` policy'lari `app_club_role()` ni chaqiradi,
`app_club_role()` esa `memberships` dan o'qiydi. Ya'ni `memberships` ni o'qish
policy'ni ishga soladi → policy funksiyani chaqiradi → funksiya jadvalni o'qiydi
→ policy yana ishga tushadi → `stack depth limit exceeded`.

Nega bu lokal muhitda ko'rinmadi: `SECURITY DEFINER` funksiyalar
`playbron_platform` egaligiga o'tkaziladi va u rol BYPASSRLS bo'lsa policy
umuman baholanmaydi. Lekin `ALTER ROLE ... BYPASSRLS` **superuser** huquqini
talab qiladi. Render'ning boshqariladigan Postgres'ida ilova roli superuser
emas, shuning uchun:

    • `playbron_platform` yaratiladi, lekin BYPASSRLS OLMAYDI;
    • `ALTER FUNCTION ... OWNER TO playbron_platform` ham o'tmaydi;
    • funksiyalar baza EGASI qo'lida qoladi, egaga esa
      `FORCE ROW LEVEL SECURITY` baribir tegishli.

Natijada prod'da `memberships` ni HAR QANDAY o'qish rekursiyaga tushadi —
xodim kirishi (`load_memberships`) ham, xodim qo'shish ham. Bu holat
Render'ga o'xshatib qurilgan lokal bazada (superuser emas, BYPASSRLS yo'q)
takrorlab ko'rilgan.

YECHIM. Rekursiya ildizi bitta: `memberships` ustidagi policy o'sha
`memberships` ni o'qiydigan funksiyaga tayanadi. Boshqa jadvallardagi
policy'lar `app_club_role()` ni chaqirsa muammo yo'q — ular boshqa jadvalni
himoya qiladi va zanjir `memberships_read` da tugaydi. Shuning uchun FAQAT
shu uchta policy o'zgartiriladi: rol endi `app.club_role` GUC'idan olinadi.

Ishonch darajasi pasaymaydi. `app.user_id`, `app.club_id` va
`app.is_super_admin` allaqachon shu yo'l bilan — ilova tomonidan, imzolangan
tokendan — o'rnatiladi. Yangi GUC ham o'sha bitta joyda (`_apply_context`)
to'ldiriladi. Ustiga-ustak muhim yozuv amallari (masalan `auth_create_staff`)
rolni JADVALDAN qayta tekshiradi, ya'ni GUC yolg'on gapirsa ham amal o'tmaydi.

Revision ID: 0007_membership_policy_recursion
Revises: 0006_staff_provisioning
"""

import sqlalchemy as sa
from alembic import op

revision = "0007_membership_policy_recursion"
down_revision = "0006_staff_provisioning"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _claim_functions()
    _rewrite_policies()
    _users_policies()
    _rewrite_create_staff()
    _assert_no_recursive_policy()
    _assert_read_terminates()
    _assert_login_lookup_works()


def _claim_functions() -> None:
    """GUC'dan o'qiydigan yordamchilar.

    `app_club_role(bigint)` ATAYLAB o'zgarishsiz qoladi: u jadvalga tayangan
    va boshqa jadvallarning policy'lari uchun haqiqiy manba bo'lib qolaveradi.
    """
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_club_role_claim() RETURNS text
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT NULLIF(current_setting('app.club_role', true), '') $$;

            CREATE OR REPLACE FUNCTION app_login_claim() RETURNS text
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT NULLIF(current_setting('app.login', true), '') $$;
            """
        )
    )


def _rewrite_policies() -> None:
    op.execute(
        sa.text(
            """
            DROP POLICY IF EXISTS memberships_read         ON memberships;
            DROP POLICY IF EXISTS memberships_write_owner  ON memberships;
            DROP POLICY IF EXISTS memberships_write_admin  ON memberships;

            -- O'z a'zoligini har kim ko'radi. Klubning butun ro'yxatini esa
            -- faqat OWNER/ADMIN — rol GUC'dan, jadvaldan emas.
            CREATE POLICY memberships_read ON memberships FOR SELECT
                USING (
                    (user_id = app_user_id() AND status = 'active')
                    OR (
                        club_id = app_club_id()
                        AND app_club_role_claim() = ANY (ARRAY['OWNER', 'ADMIN'])
                    )
                );

            CREATE POLICY memberships_write_owner ON memberships FOR ALL
                USING (club_id = app_club_id() AND app_club_role_claim() = 'OWNER')
                WITH CHECK (club_id = app_club_id() AND app_club_role_claim() = 'OWNER');

            -- ADMIN faqat STAFF qatorini yozadi: o'ziga teng yoki undan yuqori
            -- rol bera olmaydi (rol shifti).
            CREATE POLICY memberships_write_admin ON memberships FOR ALL
                USING (
                    club_id = app_club_id()
                    AND app_club_role_claim() = 'ADMIN'
                    AND role = 'STAFF'
                )
                WITH CHECK (
                    club_id = app_club_id()
                    AND app_club_role_claim() = 'ADMIN'
                    AND role = 'STAFF'
                );
            """
        )
    )


def _users_policies() -> None:
    """`users` — kirish va xodim yaratish uchun ikkita tor policy.

    Ikkalasi ham BYPASSRLS yo'q muhit uchun. Ilgari bu amallar
    `SECURITY DEFINER` funksiya `playbron_platform` egaligiga o'tadi va u rol
    RLS'ni chetlab o'tadi degan taxminga tayangan edi — Render'da bu taxmin
    ishlamaydi (`ALTER ROLE ... BYPASSRLS` superuser talab qiladi).

    `users_login_probe` — kirish paytida `app.user_id` hali 0, ya'ni
    `users_self` hech qanday qatorni ochmaydi va `auth_lookup_staff` BO'SH
    qaytaradi: prod'da har bir kirish 401 bilan tugardi. Policy aynan
    `app.login` GUC'iga teng loginli bitta xodim qatorini ochadi. Bu
    `app.telegram_id` (mijoz kirishi) va `app.refresh_hash` (token
    almashtirish) uchun allaqachon ishlatilgan naqsh: sirni bilgan
    chaqiruvchiga faqat o'sha bitta qator ochiladi.

    `users_staff_provision` — faqat INSERT. `USING` YO'Q, ya'ni bu policy
    hech qanday qatorni O'QISHGA ochmaydi: klub egasi boshqa klubning
    xodimlarini ko'ra olmaydi. Shuning uchun `auth_create_staff` da
    `RETURNING` ishlatib bo'lmaydi (`INSERT ... RETURNING` SELECT policy'sini
    ham talab qiladi) — id `currval` orqali olinadi.
    """
    op.execute(
        sa.text(
            """
            DROP POLICY IF EXISTS users_login_probe     ON users;
            DROP POLICY IF EXISTS users_staff_provision ON users;

            CREATE POLICY users_login_probe ON users FOR SELECT
                USING (
                    kind = 'staff'
                    AND app_login_claim() IS NOT NULL
                    AND lower(login) = app_login_claim()
                );

            CREATE POLICY users_staff_provision ON users FOR INSERT
                WITH CHECK (
                    kind = 'staff'
                    AND app_club_id() <> 0
                    AND app_club_role_claim() = ANY (ARRAY['OWNER', 'ADMIN'])
                );
            """
        )
    )


def _rewrite_create_staff() -> None:
    """`auth_create_staff` — `RETURNING` o'rniga `currval`.

    Sabab yuqorida: `INSERT ... RETURNING` qaytariladigan qatorga SELECT
    policy'sini ham qo'llaydi. Yangi xodim qatorini ochadigan SELECT
    policy'si esa ATAYLAB yo'q — bo'lganda klub egasi butun `users`
    jadvalini ko'rib qolardi.
    """
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION auth_create_staff(
                p_login      text,
                p_first_name text,
                p_role       text
            )
                RETURNS bigint
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                actor      bigint := app_user_id();
                club       bigint := app_club_id();
                actor_role text;
                new_id     bigint;
                norm_login text := lower(btrim(p_login));
            BEGIN
                IF actor IS NULL OR actor = 0 OR club IS NULL OR club = 0 THEN
                    RETURN NULL;
                END IF;

                IF p_role NOT IN ('ADMIN', 'STAFF') THEN
                    RAISE EXCEPTION 'ROLE_NOT_ALLOWED';
                END IF;

                -- Avtorizatsiya JADVALDAN o'qiladi, GUC'dan emas: `app.club_role`
                -- policy'ni qanoatlantiradi, lekin qaror manbai bo'lolmaydi.
                SELECT m.role INTO actor_role FROM memberships m
                 WHERE m.club_id = club AND m.user_id = actor AND m.status = 'active';

                IF actor_role IS NULL OR actor_role NOT IN ('OWNER', 'ADMIN') THEN
                    RETURN NULL;
                END IF;

                IF actor_role = 'ADMIN' AND p_role <> 'STAFF' THEN
                    RAISE EXCEPTION 'ROLE_NOT_ALLOWED';
                END IF;

                INSERT INTO users (kind, login, status, first_name, display_name)
                VALUES ('staff', norm_login, 'active', p_first_name, p_first_name);

                new_id := currval(pg_get_serial_sequence('users', 'id'));

                INSERT INTO memberships (user_id, club_id, role, invited_by)
                VALUES (new_id, club, p_role, actor);

                RETURN new_id;
            END
            $fn$;
            """
        )
    )


def _assert_no_recursive_policy() -> None:
    """Invariant: `memberships` policy'lari `app_club_role()` ni CHAQIRMAYDI.

    Bu tekshiruv har qanday muhitda ma'noli — u policy MATNIGA qaraydi, ya'ni
    superuser ostida ham «bekorga o'tib ketmaydi». Aynan shunday soxta
    xotirjamlik `0005` da bir marta bo'lgan edi.
    """
    conn = op.get_bind()
    guilty = (
        conn.execute(
            sa.text(
                "SELECT p.polname FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid"
                " WHERE c.relname = 'memberships'"
                "   AND (COALESCE(pg_get_expr(p.polqual, p.polrelid), '') LIKE '%app_club_role(%'"
                "     OR COALESCE(pg_get_expr(p.polwithcheck, p.polrelid), '') LIKE '%app_club_role(%')"
            )
        )
        .scalars()
        .all()
    )

    if guilty:
        raise RuntimeError(
            f"`memberships` policy'lari hali ham app_club_role() ni chaqiradi: "
            f"{', '.join(guilty)}. Bu prod'da cheksiz rekursiya beradi."
        )


def _force_rls(conn: sa.Connection, tables: tuple[str, ...], *, enabled: bool) -> None:
    verb = "FORCE" if enabled else "NO FORCE"
    for table in tables:
        conn.execute(sa.text(f"ALTER TABLE {table} {verb} ROW LEVEL SECURITY"))


def _assert_login_lookup_works() -> None:
    """Kirish HAQIQATAN ishlaydimi — `app.user_id = 0` sharoitida.

    `0005` dagi shunga o'xshash tekshiruv yashil chiroq bergan, lekin bekorga:
    u butun migratsiya davomida `users` uchun `FORCE` o'chirilgan holatda
    ishlagan, ya'ni policy umuman baholanmagan. Bu yerda `FORCE` o'qishdan
    OLDIN qaytariladi va `app.user_id` ataylab 0 qilinadi — aynan kirish
    payti shunday bo'ladi.
    """
    conn = op.get_bind()

    exists = conn.execute(
        sa.text("SELECT count(*) FROM pg_policy WHERE polname = 'users_login_probe'")
    ).scalar()
    if not exists:
        raise RuntimeError("users_login_probe policy'si yaratilmadi")

    exempt = conn.execute(
        sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if exempt:
        # Policy bu rol uchun umuman qo'llanmaydi — funksional sinov bu yerda
        # hech narsani isbotlamaydi va soxta xotirjamlik bermasligi uchun
        # o'tkazib yuboriladi.
        return

    probe = "migration.probe0007"
    scoped = ("users", "staff_credentials")

    _force_rls(conn, scoped, enabled=False)
    user_id = conn.execute(
        sa.text(
            "INSERT INTO users (kind, login, status, first_name)"
            " VALUES ('staff', :login, 'active', 'probe') RETURNING id"
        ),
        {"login": probe},
    ).scalar_one()
    conn.execute(
        sa.text(
            "INSERT INTO staff_credentials (user_id, password_hash)"
            " VALUES (:uid, 'probe-hash-0007')"
        ),
        {"uid": user_id},
    )
    _force_rls(conn, scoped, enabled=True)

    conn.execute(
        sa.text(
            "SELECT set_config('app.user_id', '0', true),"
            "       set_config('app.telegram_id', '0', true),"
            "       set_config('app.login', :login, true)"
        ),
        {"login": probe},
    )
    seen = conn.execute(
        sa.text("SELECT password_hash FROM auth_lookup_staff(:login)"),
        {"login": probe},
    ).scalar_one_or_none()

    _force_rls(conn, scoped, enabled=False)
    conn.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
    _force_rls(conn, scoped, enabled=True)
    conn.execute(sa.text("SELECT set_config('app.login', '', true)"))

    if seen != "probe-hash-0007":
        raise RuntimeError(
            "auth_lookup_staff kirish sharoitida (app.user_id = 0) parol xeshini "
            "ko'ra olmadi — HAR BIR xodim kirishi 401 qaytarardi. "
            "users_login_probe policy'si va `app.login` GUC'i tekshirilsin."
        )


def _assert_read_terminates() -> None:
    """Haqiqiy o'qish — policy baholanadigan muhitda.

    Superuser yoki BYPASSRLS ostida policy umuman qo'llanmaydi, ya'ni bu
    tekshiruv o'sha yerda hech narsani isbotlamaydi va ATAYLAB o'tkazib
    yuboriladi (yolg'on «yashil» bermasligi uchun). Render'da esa deploy roli
    aynan policy ostida ishlaydi va rekursiya bo'lsa migratsiya shu yerda
    to'xtaydi.
    """
    conn = op.get_bind()
    exempt = conn.execute(
        sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()

    if exempt:
        return

    conn.execute(
        sa.text(
            "SELECT set_config('app.user_id', '0', true),"
            "       set_config('app.club_id', '0', true),"
            "       set_config('app.club_role', '', true)"
        )
    )
    conn.execute(sa.text("SELECT count(*) FROM memberships"))


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
