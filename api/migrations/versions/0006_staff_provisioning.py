"""Xodim qo'shish — klub egasi hisob yaratadi va boshlang'ich parol beradi.

Manba: `docs/05-auth-redesign.md` Ilova C.1.

Nega funksiya kerak: `users_self` policy'si faqat o'z qatorini ochadi
(`id = app_user_id()`), ya'ni klub egasi ilova roli bilan YANGI xodim
qatorini umuman yarata olmaydi. Policy'ni «OWNER istalgan qator yozsin»
deb kengaytirish esa butun jadvalni ochib yuborardi — bitta klub egasi
boshqa klubning xodimlarini ham tahrirlay olardi.

Shuning uchun yagona tor yo'l: avtorizatsiyani O'Z ICHIDA qiladigan
`SECURITY DEFINER` funksiya.

Revision ID: 0006_staff_provisioning
Revises: 0005_two_worlds_auth
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_staff_provisioning"
down_revision = "0005_two_worlds_auth"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"


def upgrade() -> None:
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
                    -- OWNER bu yerdan yaratilmaydi: klub egasi tashkilot
                    -- yaratilganda belgilanadi va uni ko'chirish alohida amal
                    RAISE EXCEPTION 'ROLE_NOT_ALLOWED';
                END IF;

                SELECT m.role INTO actor_role FROM memberships m
                 WHERE m.club_id = club AND m.user_id = actor AND m.status = 'active';

                IF actor_role IS NULL OR actor_role NOT IN ('OWNER', 'ADMIN') THEN
                    RETURN NULL;
                END IF;

                -- Rol shifti: ADMIN faqat STAFF yaratadi, o'ziga teng rol bera olmaydi
                IF actor_role = 'ADMIN' AND p_role <> 'STAFF' THEN
                    RAISE EXCEPTION 'ROLE_NOT_ALLOWED';
                END IF;

                INSERT INTO users (kind, login, status, first_name, display_name)
                VALUES ('staff', norm_login, 'active', p_first_name, p_first_name)
                RETURNING id INTO new_id;

                INSERT INTO memberships (user_id, club_id, role, invited_by)
                VALUES (new_id, club, p_role, actor);

                RETURN new_id;
            END
            $fn$;

            REVOKE ALL ON FUNCTION auth_create_staff(text, text, text) FROM PUBLIC;
            """
        )
    )

    # Egalik — `0005` dagi bilan bir xil sabab: `SECURITY DEFINER` RLS'ni
    # o'chirmaydi, faqat `current_user` ni almashtiradi.
    #
    # BYPASSRLS policy'larni chetlab o'tadi, GRANT'larni EMAS. `0001` platforma
    # roliga faqat `SELECT ON ALL TABLES` bergan, shuning uchun funksiya o'z
    # egasining huquqi bilan ishlaganda ham `users` ga yoza olmasdi
    # («permission denied for table users»). Ikkala INSERT ham shu funksiya
    # ichidan, tekshiruvlardan KEYIN bo'ladi — huquq kengaymaydi, faqat
    # funksiya ishlaydigan holatga keladi.
    op.execute(
        sa.text(
            f"""
            DO $do$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                    ALTER FUNCTION auth_create_staff(text, text, text)
                        OWNER TO {PLATFORM_ROLE};
                    GRANT INSERT ON users, memberships TO {PLATFORM_ROLE};
                END IF;
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'auth_create_staff egasi o''zgartirilmadi (huquq yo''q)';
            END
            $do$;

            GRANT EXECUTE ON FUNCTION auth_create_staff(text, text, text) TO {APP_ROLE};
            """
        )
    )

    _assert_creation_works()


def _assert_creation_works() -> None:
    """Funksiya EGASI `users` va `memberships` ga yoza olishini tekshiradi.

    Yuqoridagi `DO` bloki `insufficient_privilege` ni yutadi — bu ataylab
    (bepul rejada alohida rol bo'lmasligi mumkin). Lekin egalik o'tib,
    GRANT o'tmagan oraliq holat jimgina qolib ketardi va xato faqat birinchi
    xodim qo'shilganda `permission denied for table users` bo'lib chiqardi.
    """
    conn = op.get_bind()
    owner = conn.execute(
        sa.text("SELECT proowner::regrole::text FROM pg_proc WHERE proname = 'auth_create_staff'")
    ).scalar()

    if owner != PLATFORM_ROLE:
        # Ega — baza egasi: huquqlari to'liq, tekshiradigan narsa yo'q
        return

    missing = (
        conn.execute(
            sa.text(
                "SELECT t FROM unnest(ARRAY['users', 'memberships']) AS t"
                " WHERE NOT has_table_privilege(:role, t, 'INSERT')"
            ),
            {"role": PLATFORM_ROLE},
        )
        .scalars()
        .all()
    )

    if missing:
        raise RuntimeError(
            f"`{PLATFORM_ROLE}` roli {', '.join(missing)} jadvaliga yoza olmaydi — "
            "`auth_create_staff` ishlamaydi. Baza egasi shu rolning a'zosi "
            "bo'lishi kerak (GRANT bajarilishi uchun)."
        )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
