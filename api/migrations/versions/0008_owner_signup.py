"""Klub egasi o'zi ro'yxatdan o'tadi — landing formasidan.

Manba: `docs/05-auth-redesign.md` §5.5 va **Ilova C.1** (loyiha egasining
qarori: klub admini o'zi ro'yxatdan o'tadi va parolni O'ZI qo'yadi, super
admin qatnashmaydi).

§5.5 dan ATAYLAB CHETLANISH. Dastlabki dizayn ro'yxatdan o'tishni Telegram
orqali tasdiqlatgan (`/start` → `requestContact` → OTP) va «login band»
javobini faqat shundan keyin bergan. Ilova C.3 esa Telegram bog'lashni
kirish sharti bo'lishdan chiqargan, ya'ni o'sha darvoza endi yo'q.

Shuning uchun bandlik SAQLASHDA aytiladi, hisob sanash orakuli esa boshqa
chora bilan yopiladi: endpoint IP bo'yicha **3/soat va 10/kun** bilan
cheklangan (§10.1 dagi qiymat). Bu tezlikda global login makonini sanab
chiqib bo'lmaydi, foydalanuvchi esa nima uchun ro'yxatdan o'ta olmaganini
biladi.

Nega funksiya kerak. Ro'yxatdan o'tishda `app.user_id` hali 0 — ya'ni
`organizations_insert` (`owner_user_id = app_user_id()`) va `clubs_insert`
policy'lari qanoatlantirilmaydi. Beshta jadvalga ketma-ket yozish kerak va
ularning har biri o'zidan oldingisining natijasiga tayanadi. Funksiya
foydalanuvchini yaratgach uning kimligini O'ZIGA oladi (`set_config`) va
qolgan yozuvlarni o'sha kimlik ostida bajaradi — ya'ni policy'lar
chetlab o'tilmaydi, ular haqiqatan qanoatlantiriladi.

BYPASSRLS yo'q muhitda (Render — `[[render-free-tier-no-bypassrls]]`) bu
yagona ishlaydigan yo'l: `SECURITY DEFINER` RLS'ni o'chirmaydi.

Revision ID: 0008_owner_signup
Revises: 0007_membership_policy_recursion
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_owner_signup"
down_revision = "0007_membership_policy_recursion"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"


def upgrade() -> None:
    _claim_function()
    _signup_policy()
    _signup_function()
    _grants()
    _assert_signup_works()


def _claim_function() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_signup_claim() RETURNS text
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT NULLIF(current_setting('app.signup_login', true), '') $$;
            """
        )
    )


def _signup_policy() -> None:
    """`users` ga yozishning uchinchi va oxirgi tor yo'li.

    `users_self` — o'z qatori, `users_staff_provision` — klub egasi xodim
    qo'shganda, `users_owner_signup` — ro'yxatdan o'tish. Uchalasi ham
    `WITH CHECK` bilan cheklangan va hech biri O'QISHNI kengaytirmaydi.

    Policy qatorni AYNAN `app.signup_login` dagi loginga bog'laydi: GUC
    o'rnatilgan bo'lsa ham, boshqa loginli qator yozib bo'lmaydi. GUC'ni
    faqat `POST /auth/owner/signup` marshruti qo'yadi va darhol tozalaydi.
    """
    op.execute(
        sa.text(
            """
            DROP POLICY IF EXISTS users_owner_signup ON users;

            CREATE POLICY users_owner_signup ON users FOR INSERT
                WITH CHECK (
                    kind = 'staff'
                    AND app_signup_claim() IS NOT NULL
                    AND lower(login) = app_signup_claim()
                );
            """
        )
    )


def _signup_function() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION auth_owner_signup(
                p_login      text,
                p_first_name text,
                p_org_name   text,
                p_club_name  text,
                p_phone      text,
                p_address    text,
                p_password   text
            )
                RETURNS bigint
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                norm_login text := lower(btrim(p_login));
                new_user   bigint;
                new_org    bigint;
                new_club   bigint;
            BEGIN
                -- Marshrut GUC'ni qo'ymagan bo'lsa hech narsa yaratilmaydi.
                -- Bu policy bilan IKKI KARRA himoya emas: policy `users` ni
                -- himoya qiladi, bu tekshiruv esa qolgan to'rtta jadvalga
                -- yozishni ham darvozadan o'tkazadi.
                IF app_signup_claim() IS DISTINCT FROM norm_login THEN
                    RAISE EXCEPTION 'SIGNUP_SCOPE_MISSING';
                END IF;

                INSERT INTO users (kind, login, status, first_name, display_name)
                VALUES ('staff', norm_login, 'active', p_first_name, p_first_name);
                new_user := currval(pg_get_serial_sequence('users', 'id'));

                -- Endi funksiya yangi foydalanuvchining kimligini oladi.
                -- `set_config(..., true)` — tranzaksiya doirasida, commit yoki
                -- rollback bilan o'zi bekor bo'ladi.
                PERFORM set_config('app.user_id', new_user::text, true);

                -- `pending` va tarifsiz: `organizations_insert` policy'si
                -- (0003) aynan shuni majburlaydi. Tarifni super admin yoki
                -- to'lov oqimi qo'yadi — o'zini o'zi faollashtirish yo'q.
                INSERT INTO organizations (owner_user_id, name, status, plan_code)
                VALUES (new_user, p_org_name, 'pending', NULL);
                new_org := currval(pg_get_serial_sequence('organizations', 'id'));

                PERFORM set_config('app.org_id', new_org::text, true);

                -- Klub `draft`: mijozlarga ko'rinmaydi (`clubs_read` faqat
                -- `active` ni ochadi), lekin egasi uni to'ldirib faollashtira
                -- oladi.
                INSERT INTO clubs (org_id, name, address, phone, status)
                VALUES (new_org, p_club_name, p_address, p_phone, 'draft');
                new_club := currval(pg_get_serial_sequence('clubs', 'id'));

                PERFORM set_config('app.club_id', new_club::text, true);
                PERFORM set_config('app.club_role', 'OWNER', true);

                INSERT INTO memberships (user_id, club_id, role)
                VALUES (new_user, new_club, 'OWNER');

                -- `must_change = false`: parolni EGASINING O'ZI tanladi.
                -- Ilova C.2 dagi majburiy almashtirish faqat BIROV bergan
                -- parolga tegishli.
                INSERT INTO staff_credentials (user_id, password_hash,
                                               password_set_at, must_change)
                VALUES (new_user, p_password, now(), false);

                RETURN new_user;
            END
            $fn$;

            REVOKE ALL ON FUNCTION
                auth_owner_signup(text, text, text, text, text, text, text)
                FROM PUBLIC;
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            DO $do$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                    ALTER FUNCTION
                        auth_owner_signup(text, text, text, text, text, text, text)
                        OWNER TO {PLATFORM_ROLE};
                    GRANT INSERT ON organizations, clubs, staff_credentials
                        TO {PLATFORM_ROLE};
                END IF;
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'auth_owner_signup egasi o''zgartirilmadi (huquq yo''q)';
            END
            $do$;

            GRANT EXECUTE ON FUNCTION
                auth_owner_signup(text, text, text, text, text, text, text)
                TO {APP_ROLE};
            """
        )
    )


def _assert_signup_works() -> None:
    """Haqiqiy ro'yxatdan o'tish — policy baholanadigan muhitda.

    Superuser/BYPASSRLS ostida policy umuman qo'llanmaydi, ya'ni bu yerda
    tekshiruv hech narsani isbotlamaydi va ATAYLAB o'tkazib yuboriladi:
    yolg'on «yashil» eng xavfli natija (`0005` da aynan shu bo'lgan).
    Render'da esa deploy roli policy ostida ishlaydi va nosozlik shu yerda
    ko'rinadi — prod'dagi birinchi ro'yxatdan o'tishda emas.
    """
    conn = op.get_bind()

    exempt = conn.execute(
        sa.text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")
    ).scalar()
    if exempt:
        return

    probe = "migration.signup0008"
    conn.execute(sa.text("SELECT set_config('app.signup_login', :login, true)"), {"login": probe})
    user_id = conn.execute(
        sa.text(
            "SELECT auth_owner_signup(:login, 'probe', 'Probe Org', 'Probe Club',"
            " '+998900000000', 'probe manzil', 'probe-hash-0008')"
        ),
        {"login": probe},
    ).scalar()

    if not user_id:
        raise RuntimeError("auth_owner_signup foydalanuvchi yaratmadi")

    # Kontekst funksiya ichida o'zgargan — tozalaymiz, aks holda keyingi
    # bayonotlar yangi egasining kimligi bilan ishlardi.
    conn.execute(
        sa.text(
            "SELECT set_config('app.signup_login', '', true),"
            "       set_config('app.user_id', '0', true),"
            "       set_config('app.org_id', '0', true),"
            "       set_config('app.club_id', '0', true),"
            "       set_config('app.club_role', '', true)"
        )
    )

    # Tozalash egasi huquqi bilan: `users_self` o'chirishga yo'l bermaydi.
    scoped = ("users", "organizations", "clubs", "memberships", "staff_credentials")
    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))

    # Tartib muhim: `organizations.owner_user_id` — CASCADE'siz FK, ya'ni
    # foydalanuvchini oldin o'chirib bo'lmaydi. Klub tashkilotdan CASCADE
    # bilan ketadi, a'zolik va parol esa foydalanuvchidan.
    conn.execute(sa.text("DELETE FROM organizations WHERE owner_user_id = :uid"), {"uid": user_id})
    conn.execute(sa.text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})

    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
