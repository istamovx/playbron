"""Auth qayta qurilishi — ikki dunyo: Telegram-mijoz va parolli xodim.

Manba: `docs/05-auth-redesign.md` (Ilova C ustuvor).

Qisqacha: `users` bitta jadval bo'lib qoladi, lekin o'zgarmas `kind`
diskriminatori bilan ikkiga bo'linadi. Ajratish uch qatlamda majburlanadi —
CHECK konstreyntlari, kompozit FK va RLS policy'lari; bitta qatlam unutilsa
qolgan ikkitasi ushlab qoladi.

  • mijoz  → `telegram_id` bilan tanaladi, `login` yo'q, paroli yo'q
  • xodim  → `login` bilan tanaladi, `users.telegram_id` NULL,
              Telegram alohida `staff_telegram` jadvalida (yetkazish kanali)

DIQQAT — `SECURITY DEFINER` RLS'ni O'CHIRMAYDI, u faqat `current_user` ni
almashtiradi. `FORCE ROW LEVEL SECURITY` jadval egasiga ham tatbiq etiladi,
shuning uchun bu yerdagi barcha yordamchi funksiyalar BYPASSRLS roliga
(`playbron_platform`) o'tkaziladi. Aks holda prod'da `staff_credentials`
dan 0 qator qaytadi va har bir xodim kirishi 401 bilan tugaydi
(`docs/05-auth-redesign.md` §3.6).

Revision ID: 0005_two_worlds_auth
Revises: 0004_role_passwords
"""

import os
import re

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_two_worlds_auth"
down_revision = "0004_role_passwords"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"

LOGIN_RE = re.compile(r"^[a-z0-9._-]{3,32}$")


# ─────────────────────────── 1. users ───────────────────────────


def _users_columns() -> None:
    """Yangi ustunlar. CHECK'lar backfill'dan KEYIN qo'shiladi."""
    op.add_column(
        "users",
        sa.Column("kind", sa.Text, nullable=False, server_default="customer"),
    )
    op.add_column("users", sa.Column("login", sa.Text))
    op.add_column(
        "users",
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
    )
    op.add_column("users", sa.Column("display_name", sa.String(128)))
    op.add_column("users", sa.Column("phone_reverified_at", sa.DateTime(timezone=True)))

    # Xodimda `telegram_id` NULL bo'lishi shart — eski NOT NULL olib tashlanadi
    op.alter_column("users", "telegram_id", nullable=True)


def _staff_telegram_table() -> None:
    """Xodimning Telegrami — SHAXSNI TASDIQLOVCHI EMAS, faqat yetkazish kanali.

    Backfill shu jadvalga yozgani uchun u boshqa jadvallardan oldin yaratiladi.
    """
    op.create_table(
        "staff_telegram",
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("telegram_id", sa.BigInteger, nullable=False),
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("verified_phone", sa.String(20)),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("linked_by_invite_id", sa.BigInteger),
        sa.Column("blocked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("telegram_id", name="staff_telegram_tg_uk"),
    )


# ─────────────────────────── 2. backfill ───────────────────────────


def _super_admin_logins() -> dict[int, str]:
    """`SUPER_ADMIN_TELEGRAM_IDS` bilan pozitsiya bo'yicha juftlanadi.

    `0002_seed` ga TEGILMAYDI: bo'sh bazada u 0005 dan oldin yuradi va `kind`/
    `login` ustunlari hali mavjud emas; prod'da esa allaqachon stamp qilingan
    va hech qachon qayta yurmaydi (`docs/05-auth-redesign.md` §12.5).
    """
    ids = [p.strip() for p in os.environ.get("SUPER_ADMIN_TELEGRAM_IDS", "").split(",") if p.strip()]
    logins = [p.strip().lower() for p in os.environ.get("SUPER_ADMIN_LOGINS", "").split(",") if p.strip()]

    pairs: dict[int, str] = {}
    for index, raw_id in enumerate(ids):
        if index >= len(logins):
            break
        login = logins[index]
        if not LOGIN_RE.match(login):
            raise ValueError(
                f"SUPER_ADMIN_LOGINS[{index}] = {login!r} — "
                "faqat a-z, 0-9, nuqta, pastki chiziq va defis, 3..32 belgi"
            )
        pairs[int(raw_id)] = login
    return pairs


def _backfill() -> None:
    """Imtiyozli foydalanuvchilarni xodim dunyosiga o'tkazish.

    Manba UCHALASI ham olinadi — `super_admins`, `memberships` va
    `organizations.owner_user_id`. Bittasi tushib qolsa kompozit FK
    validatsiyada yiqiladi va migratsiya to'xtaydi (§12.5).
    """
    conn = op.get_bind()

    # `users` va `staff_telegram` FORCE RLS ostida; migratsiyada `app.*` GUC'lari
    # yo'q, ya'ni policy sharti bajarilmaydi. Superuser buni sezmaydi, oddiy ega
    # esa bloklanadi — `0002_seed` bilan bir xil kelishuv.
    conn.execute(sa.text("ALTER TABLE users NO FORCE ROW LEVEL SECURITY"))

    privileged = sa.text(
        """
        SELECT DISTINCT u.id, u.telegram_id
        FROM users u
        WHERE u.id IN (SELECT user_id FROM super_admins)
           OR u.id IN (SELECT user_id FROM memberships)
           OR u.id IN (SELECT owner_user_id FROM organizations)
        """
    )
    rows = conn.execute(privileged).fetchall()

    sa_logins = _super_admin_logins()

    for user_id, telegram_id in rows:
        # Telegram xodim uchun yetkazish kanaliga ko'chadi. Shaxsiy chatda
        # `chat_id` foydalanuvchi id'siga teng — backfill uchun yagona manba.
        if telegram_id is not None:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO staff_telegram (user_id, telegram_id, chat_id)
                    VALUES (:uid, :tg, :tg)
                    ON CONFLICT (user_id) DO NOTHING
                    """
                ),
                {"uid": user_id, "tg": telegram_id},
            )

        login = sa_logins.get(telegram_id) if telegram_id is not None else None
        if login is None:
            # Parolsiz, ya'ni bu login bilan kirib bo'lmaydi
            # (`staff_credentials` yozuvi yo'q). Parol keyin
            # `scripts/set_staff_password.py` orqali qo'yiladi.
            login = f"staff{user_id}"

        conn.execute(
            sa.text(
                """
                UPDATE users
                   SET kind = 'staff',
                       status = 'active',
                       login = :login,
                       telegram_id = NULL
                 WHERE id = :uid
                """
            ),
            {"uid": user_id, "login": login},
        )

    conn.execute(sa.text("ALTER TABLE users FORCE ROW LEVEL SECURITY"))


# ─────────────────────────── 3. konstreynt va indeks ───────────────────────────


def _users_constraints() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE users
                ADD CONSTRAINT users_kind_ck CHECK (kind IN ('customer','staff')),
                ADD CONSTRAINT users_status_ck
                    CHECK (status IN ('invited','active','disabled')),
                ADD CONSTRAINT users_kind_customer_ck
                    CHECK (kind <> 'customer'
                           OR (telegram_id IS NOT NULL AND login IS NULL)),
                ADD CONSTRAINT users_kind_staff_ck
                    CHECK (kind <> 'staff'
                           OR (login IS NOT NULL AND telegram_id IS NULL)),
                ADD CONSTRAINT users_login_shape_ck
                    CHECK (login IS NULL OR login ~ '^[a-z0-9._-]{3,32}$');

            -- Kompozit FK uchun: mijoz qatoriga a'zolik yozib bo'lmaydi
            ALTER TABLE users ADD CONSTRAINT users_id_kind_uk UNIQUE (id, kind);

            -- 0001 da bu TABLE CONSTRAINT sifatida yaratilgan, ya'ni uni
            -- `DROP INDEX` bilan olib bo'lmaydi: Postgres «konstreynt talab
            -- qiladi» deb rad etadi va `IF EXISTS` yordam bermaydi.
            ALTER TABLE users DROP CONSTRAINT IF EXISTS users_telegram_id_uk;

            CREATE UNIQUE INDEX users_tg_customer_uk ON users (telegram_id)
                WHERE kind = 'customer';
            CREATE UNIQUE INDEX users_login_staff_uk ON users (lower(login))
                WHERE kind = 'staff';
            CREATE INDEX users_phone_customer_ix ON users (phone)
                WHERE kind = 'customer';
            """
        )
    )


def _composite_fks() -> None:
    """`kind` + kompozit FK. `NOT VALID` — backfill allaqachon bajarilgan,
    lekin validatsiya alohida qadamda aniq xato beradi."""
    op.execute(
        sa.text(
            """
            ALTER TABLE memberships
                ADD COLUMN kind text NOT NULL DEFAULT 'staff',
                ADD CONSTRAINT memberships_kind_ck CHECK (kind = 'staff'),
                ADD CONSTRAINT memberships_user_kind_fk
                    FOREIGN KEY (user_id, kind) REFERENCES users (id, kind)
                    ON DELETE CASCADE NOT VALID;

            ALTER TABLE super_admins
                ADD COLUMN kind text NOT NULL DEFAULT 'staff',
                ADD CONSTRAINT super_admins_kind_ck CHECK (kind = 'staff'),
                ADD CONSTRAINT super_admins_user_kind_fk
                    FOREIGN KEY (user_id, kind) REFERENCES users (id, kind)
                    ON DELETE CASCADE NOT VALID;

            ALTER TABLE memberships VALIDATE CONSTRAINT memberships_user_kind_fk;
            ALTER TABLE super_admins VALIDATE CONSTRAINT super_admins_user_kind_fk;
            """
        )
    )


# ─────────────────────────── 4. yangi jadvallar ───────────────────────────


def _auth_tables() -> None:
    op.create_table(
        "staff_credentials",
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("password_set_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # Birov bergan parol bir martalik — Ilova C.2
        sa.Column("must_change", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        # Telemetriya. Hisobni QULFLASH uchun EMAS: qulf smena vaqtidagi
        # maqsadli DoS ga aylanadi (§10.2)
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_failed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "staff_invites",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "club_id",
            sa.BigInteger,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expected_phone", sa.String(20), nullable=False),
        sa.Column("target_role", sa.String(16), nullable=False),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("opened_by_telegram_id", sa.BigInteger),
        sa.CheckConstraint(
            "target_role IN ('OWNER','ADMIN','STAFF')", name="staff_invites_role_ck"
        ),
    )
    op.create_index("staff_invites_club_ix", "staff_invites", ["club_id", "created_at"])

    op.create_table(
        "staff_devices",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("device_hash", sa.String(64), nullable=False),
        sa.Column("label", sa.String(64)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "device_hash", name="staff_devices_uk"),
    )

    op.create_table(
        "staff_recovery_codes",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("user_id", "code_hash", name="staff_recovery_codes_uk"),
    )

    # `audit_log` emas: muvaffaqiyatsiz kirishda aktor YO'Q, `audit_log_insert`
    # esa `actor_user_id = app_user_id()` talab qiladi — eng kerakli xavfsizlik
    # signali jimgina yo'qolardi (§3.4).
    op.create_table(
        "auth_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("event", sa.String(48), nullable=False),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="SET NULL")),
        # Loginning o'zi emas, xeshi — jurnal hisob sanash manbaiga aylanmasin
        sa.Column("login_hash", sa.String(64)),
        sa.Column("ip", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.Column("request_id", sa.String(64)),
        sa.Column("club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="SET NULL")),
        sa.Column("detail", postgresql.JSONB, nullable=False, server_default="{}"),
    )
    op.create_index("auth_events_at_ix", "auth_events", ["at"])
    op.create_index("auth_events_user_ix", "auth_events", ["user_id", "at"])


def _other_columns() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE refresh_tokens
                -- Dunyo SAQLANGAN qatordan olinadi, `users` dan qayta
                -- hisoblanmaydi: mijoz refresh'i xodim access'iga aylanmasin
                ADD COLUMN kind text NOT NULL DEFAULT 'customer',
                -- Mutlaq sessiya chegarasi. Rotatsiya bu vaqtni KO'CHIRMAYDI
                ADD COLUMN chain_started_at timestamptz NOT NULL DEFAULT now(),
                ADD COLUMN device_hash char(64),
                ADD CONSTRAINT refresh_tokens_kind_ck
                    CHECK (kind IN ('customer','staff'));

            ALTER TABLE audit_log
                ADD COLUMN club_id bigint REFERENCES clubs (id) ON DELETE SET NULL;
            CREATE INDEX audit_log_club_at_ix ON audit_log (club_id, at);
            """
        )
    )


# ─────────────────────────── 5. RLS ───────────────────────────


def _rls_new_tables() -> None:
    """Har bir yangi jadval uchun ENABLE + FORCE va aniq policy.

    `0003` `ALTER DEFAULT PRIVILEGES` ni revoke qilgan — GRANT yozilmasa
    jadval ilova roliga umuman ko'rinmaydi (fail-closed, ataylab).
    """
    op.execute(
        sa.text(
            """
            ALTER TABLE staff_telegram       ENABLE ROW LEVEL SECURITY;
            ALTER TABLE staff_telegram       FORCE  ROW LEVEL SECURITY;
            ALTER TABLE staff_credentials    ENABLE ROW LEVEL SECURITY;
            ALTER TABLE staff_credentials    FORCE  ROW LEVEL SECURITY;
            ALTER TABLE staff_invites        ENABLE ROW LEVEL SECURITY;
            ALTER TABLE staff_invites        FORCE  ROW LEVEL SECURITY;
            ALTER TABLE staff_devices        ENABLE ROW LEVEL SECURITY;
            ALTER TABLE staff_devices        FORCE  ROW LEVEL SECURITY;
            ALTER TABLE staff_recovery_codes ENABLE ROW LEVEL SECURITY;
            ALTER TABLE staff_recovery_codes FORCE  ROW LEVEL SECURITY;
            ALTER TABLE auth_events          ENABLE ROW LEVEL SECURITY;
            ALTER TABLE auth_events          FORCE  ROW LEVEL SECURITY;

            -- Xodim o'z Telegram bog'lanishini ko'radi. Yozish faqat
            -- SECURITY DEFINER orqali: bog'lash webhook kontekstida sodir
            -- bo'ladi, u yerda `app.user_id` yo'q.
            CREATE POLICY staff_telegram_self ON staff_telegram
                FOR SELECT USING (user_id = app_user_id());

            -- `staff_credentials` va `staff_recovery_codes`: POLICY YOZILMAYDI.
            -- FORCE + policy yo'qligi = ilova roli uchun butunlay yopiq.
            -- Yagona kirish yo'li — quyidagi SECURITY DEFINER funksiyalari.

            -- Invayt: faqat o'z klubi va faqat OWNER/ADMIN. Maqsad rolini
            -- tekshirish `auth_consume_invite()` ICHIDA (§9.2).
            CREATE POLICY staff_invites_manage ON staff_invites
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER','ADMIN'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER','ADMIN')
                            -- ADMIN faqat STAFF taklif qiladi, o'ziga teng yoki
                            -- yuqori rol yozolmaydi
                            AND (app_club_role(app_club_id()) = 'OWNER'
                                 OR target_role = 'STAFF'));

            CREATE POLICY staff_devices_self ON staff_devices
                USING (user_id = app_user_id())
                WITH CHECK (user_id = app_user_id());

            -- Append-only. Aktorsiz yozuv ham qabul qilinadi: muvaffaqiyatsiz
            -- kirishda `app.user_id` = 0 bo'ladi va aynan o'sha yozuv eng
            -- kerakli signal.
            CREATE POLICY auth_events_insert ON auth_events
                FOR INSERT WITH CHECK (true);

            CREATE POLICY auth_events_read ON auth_events
                FOR SELECT USING (
                    user_id = app_user_id()
                    OR (club_id = app_club_id()
                        AND app_club_role(app_club_id()) IN ('OWNER','ADMIN'))
                );
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            GRANT SELECT ON staff_telegram TO {APP_ROLE};
            GRANT SELECT, INSERT, UPDATE, DELETE ON staff_invites TO {APP_ROLE};
            GRANT SELECT, INSERT, UPDATE, DELETE ON staff_devices TO {APP_ROLE};
            GRANT SELECT, INSERT ON auth_events TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE staff_invites_id_seq TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE staff_devices_id_seq TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE auth_events_id_seq TO {APP_ROLE};

            GRANT SELECT ON staff_telegram, staff_invites, staff_devices,
                            auth_events TO {PLATFORM_ROLE};

            -- `staff_credentials` va `staff_recovery_codes` ilova rolidan
            -- yopiq, lekin SECURITY DEFINER funksiyalari aynan shu rol ostida
            -- yuradi — grant berilmasa ular «permission denied» bilan yiqiladi
            -- va prod'da HAR BIR xodim kirishi 500 qaytaradi.
            -- BYPASSRLS policy'ni chetlab o'tadi, GRANT ni emas.
            GRANT SELECT, INSERT, UPDATE ON staff_credentials    TO {PLATFORM_ROLE};
            GRANT SELECT, INSERT, UPDATE ON staff_recovery_codes TO {PLATFORM_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE staff_recovery_codes_id_seq TO {PLATFORM_ROLE};

            -- Ikkinchi qatlam: policy yo'qligi yetarli, lekin grant'ni ham
            -- olib tashlash xatolikka joy qoldirmaydi
            REVOKE ALL ON staff_credentials    FROM {APP_ROLE};
            REVOKE ALL ON staff_recovery_codes FROM {APP_ROLE};

            -- Jurnalni tahrirlab bo'lmaydi
            REVOKE UPDATE, DELETE ON auth_events FROM {APP_ROLE};

            -- `kind` ilova roli uchun O'ZGARMAS: mijozni xodimga aylantirib
            -- bo'lmaydi, hech qanday kod xatosi buni chetlab o'tolmaydi
            REVOKE UPDATE (kind) ON users FROM {APP_ROLE};
            """
        )
    )


def _rewrite_policies() -> None:
    op.execute(
        sa.text(
            """
            -- Mijoz o'zini `telegram_id` bilan topadi — endi FAQAT mijoz
            DROP POLICY IF EXISTS users_self ON users;
            CREATE POLICY users_self ON users
                USING (id = app_user_id()
                       OR (app_telegram_id() <> 0
                           AND kind = 'customer'
                           AND telegram_id = app_telegram_id()))
                WITH CHECK (id = app_user_id()
                            OR (app_telegram_id() <> 0
                                AND kind = 'customer'
                                AND telegram_id = app_telegram_id()));

            -- Rol shifti: eski `memberships_write` yoziladigan `role` qiymatini
            -- umuman tekshirmasdi, ya'ni ADMIN o'zini OWNER qilib, klubning
            -- to'lov kalitlarini olardi.
            DROP POLICY IF EXISTS memberships_write ON memberships;

            CREATE POLICY memberships_write_owner ON memberships
                FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) = 'OWNER')
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) = 'OWNER');

            CREATE POLICY memberships_write_admin ON memberships
                FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) = 'ADMIN'
                       AND role = 'STAFF')
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) = 'ADMIN'
                            AND role = 'STAFF');

            -- Ko'p klubli tashkilotda A klubning STAFF'i B klubning izlarini
            -- o'qiy olmasin
            DROP POLICY IF EXISTS audit_log_read ON audit_log;
            CREATE POLICY audit_log_read ON audit_log
                FOR SELECT USING (
                    actor_user_id = app_user_id()
                    OR (club_id = app_club_id()
                        AND app_club_role(app_club_id()) IN ('OWNER','ADMIN'))
                    OR (club_id IS NULL AND org_id = app_org_id()
                        AND EXISTS (SELECT 1 FROM organizations o
                                    WHERE o.id = audit_log.org_id
                                      AND o.owner_user_id = app_user_id()))
                );
            """
        )
    )


# ─────────────────────────── 6. SECURITY DEFINER ───────────────────────────


def _functions() -> None:
    """`staff_credentials` ga yagona kirish yo'li.

    Jadvalda policy yo'q va `REVOKE ALL` qilingan, ya'ni ilova roli unga
    to'g'ridan-to'g'ri tegolmaydi. Funksiyalar esa BYPASSRLS roliga tegishli
    bo'lgani uchun ishlaydi (§3.6).
    """
    op.execute(
        sa.text(
            """
            -- Kirish uchun TOR tuple: parol xeshidan boshqa hech narsa
            -- chiqmaydi va hisob sanash uchun ma'lumot bermaydi.
            CREATE OR REPLACE FUNCTION auth_lookup_staff(p_login text)
                RETURNS TABLE (user_id bigint, password_hash text,
                               status text, must_change boolean)
                LANGUAGE sql STABLE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
                SELECT u.id, c.password_hash, u.status, c.must_change
                FROM users u
                JOIN staff_credentials c ON c.user_id = u.id
                WHERE u.kind = 'staff'
                  AND lower(u.login) = lower(p_login)
                LIMIT 1
            $fn$;

            -- Telemetriya. `user_id` parametr sifatida keladi, lekin funksiya
            -- FAQAT hisoblagich ustunlarini yozadi — parolga ham, rolga ham
            -- tegmaydi, ya'ni imtiyoz oshirish primitivi emas.
            CREATE OR REPLACE FUNCTION auth_touch_login(p_user_id bigint, p_ok boolean)
                RETURNS void
                LANGUAGE sql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
                UPDATE staff_credentials
                   SET last_login_at  = CASE WHEN p_ok THEN now() ELSE last_login_at END,
                       failed_count   = CASE WHEN p_ok THEN 0 ELSE failed_count + 1 END,
                       last_failed_at = CASE WHEN p_ok THEN last_failed_at ELSE now() END
                 WHERE user_id = p_user_id
            $fn$;

            -- O'z parolini almashtirish. `user_id` PARAMETRI YO'Q — u
            -- kontekstdan olinadi, ya'ni boshqa hisobga yozib bo'lmaydi.
            CREATE OR REPLACE FUNCTION auth_change_password(p_new_hash text)
                RETURNS boolean
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                actor bigint := app_user_id();
            BEGIN
                IF actor IS NULL OR actor = 0 THEN
                    RETURN false;
                END IF;

                UPDATE staff_credentials
                   SET password_hash   = p_new_hash,
                       password_set_at = now(),
                       must_change     = false
                 WHERE user_id = actor;

                RETURN FOUND;
            END
            $fn$;
            """
        )
    )

    # ── Ilova C: parolni klub egasi tayinlaydi ────────────────────────────
    #
    # DIZAYNDAN CHEKINISH. `docs/05-auth-redesign.md` §3.6 «hech bir yozuvchi
    # funksiya `user_id` ni parametr sifatida qabul qilmaydi» deydi, sababi —
    # bunday funksiya SQL injeksiya uchun tayyor imtiyoz oshirish primitivi.
    #
    # Ilova C (biznes qarori) parolni xodimga klub egasi berishini talab qiladi,
    # ya'ni maqsad `user_id` baribir kerak. Xavf uch chora bilan cheklanadi:
    #   1. Avtorizatsiya funksiya ICHIDA — chaqiruvchining o'sha klubdagi roli
    #      va maqsadning o'sha klubda a'zoligi tekshiriladi. Injeksiya yolg'iz
    #      o'zida yetarli emas: hujumchida maqsad klubning OWNER konteksti ham
    #      bo'lishi shart.
    #   2. Rol shifti: ADMIN faqat STAFF parolini qo'yadi, OWNER ga tegolmaydi.
    #   3. Natija doim `must_change = true` — parolni bilgan odam undan faqat
    #      birinchi kirishgacha foydalana oladi (Ilova C.2).
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION auth_assign_password(p_user_id bigint,
                                                            p_new_hash text)
                RETURNS boolean
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                actor       bigint := app_user_id();
                club        bigint := app_club_id();
                actor_role  text;
                target_role text;
            BEGIN
                IF actor IS NULL OR actor = 0 OR club IS NULL OR club = 0 THEN
                    RETURN false;
                END IF;

                SELECT m.role INTO actor_role FROM memberships m
                 WHERE m.club_id = club AND m.user_id = actor AND m.status = 'active';

                SELECT m.role INTO target_role FROM memberships m
                 WHERE m.club_id = club AND m.user_id = p_user_id AND m.status = 'active';

                -- Birov o'sha klubda emas
                IF actor_role IS NULL OR target_role IS NULL THEN
                    RETURN false;
                END IF;

                IF actor_role NOT IN ('OWNER', 'ADMIN') THEN
                    RETURN false;
                END IF;

                -- Rol shifti: ADMIN o'ziga teng yoki yuqori rolga tegolmaydi
                IF actor_role = 'ADMIN' AND target_role <> 'STAFF' THEN
                    RETURN false;
                END IF;

                INSERT INTO staff_credentials (user_id, password_hash,
                                               password_set_at, must_change)
                VALUES (p_user_id, p_new_hash, now(), true)
                ON CONFLICT (user_id) DO UPDATE
                    SET password_hash   = excluded.password_hash,
                        password_set_at = now(),
                        must_change     = true,
                        failed_count    = 0;

                RETURN true;
            END
            $fn$;
            """
        )
    )

    # Egalikni BYPASSRLS roliga o'tkazish. Mavjud `app_club_role()` ham shu
    # tuzoqda: u `memberships` (FORCE RLS) ni o'qiydi va prod'da bo'sh natija
    # qaytarardi. Rol yo'q bo'lsa (bepul hosting) jimgina o'tkazib yuboriladi —
    # u yerda ilova baza EGASI bilan ulanadi va funksiya baribir ishlaydi.
    op.execute(
        sa.text(
            """
            DO $do$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'playbron_platform') THEN
                    ALTER FUNCTION app_club_role(bigint)              OWNER TO playbron_platform;
                    ALTER FUNCTION auth_lookup_staff(text)            OWNER TO playbron_platform;
                    ALTER FUNCTION auth_touch_login(bigint, boolean)  OWNER TO playbron_platform;
                    ALTER FUNCTION auth_change_password(text)         OWNER TO playbron_platform;
                    ALTER FUNCTION auth_assign_password(bigint, text) OWNER TO playbron_platform;
                END IF;
            END
            $do$;

            REVOKE ALL ON FUNCTION auth_lookup_staff(text)            FROM PUBLIC;
            REVOKE ALL ON FUNCTION auth_touch_login(bigint, boolean)  FROM PUBLIC;
            REVOKE ALL ON FUNCTION auth_change_password(text)         FROM PUBLIC;
            REVOKE ALL ON FUNCTION auth_assign_password(bigint, text) FROM PUBLIC;
            """
        )
    )

    op.execute(
        sa.text(
            f"""
            GRANT EXECUTE ON FUNCTION auth_lookup_staff(text)            TO {APP_ROLE};
            GRANT EXECUTE ON FUNCTION auth_touch_login(bigint, boolean)  TO {APP_ROLE};
            GRANT EXECUTE ON FUNCTION auth_change_password(text)         TO {APP_ROLE};
            GRANT EXECUTE ON FUNCTION auth_assign_password(bigint, text) TO {APP_ROLE};
            """
        )
    )


# ─────────────────────────── 7. yakuniy tekshiruv ───────────────────────────


def _assert_super_admins_usable() -> None:
    """Platformani o'zi-o'zi qulflashdan saqlaydi (§12.5).

    Super admin `kind='staff'` va `login` bilan chiqmasa — deploy YIQILSIN.
    Aks holda `/platform/*` ga kirish yo'li butunlay yopilardi va uni tuzatish
    uchun bazaga qo'lda kirish kerak bo'lardi.
    """
    conn = op.get_bind()

    # DIQQAT: `users` va `super_admins` FORCE RLS ostida va migratsiyada
    # `app.*` GUC'lari o'rnatilmagan. FORCE olib turilmasa so'rov Render'da
    # (ilova oddiy EGA) 0 qator qaytaradi — ya'ni tekshiruv aynan muhim joyda
    # jimgina bo'sh o'tib ketardi. Lokalda superuser buni sezmaydi.
    conn.execute(sa.text("ALTER TABLE users NO FORCE ROW LEVEL SECURITY"))
    conn.execute(sa.text("ALTER TABLE super_admins NO FORCE ROW LEVEL SECURITY"))
    try:
        broken = conn.execute(
            sa.text(
                """
                SELECT count(*) FROM super_admins sa
                JOIN users u ON u.id = sa.user_id
                WHERE u.kind <> 'staff' OR u.login IS NULL
                """
            )
        ).scalar_one()
    finally:
        conn.execute(sa.text("ALTER TABLE users FORCE ROW LEVEL SECURITY"))
        conn.execute(sa.text("ALTER TABLE super_admins FORCE ROW LEVEL SECURITY"))

    if broken:
        raise RuntimeError(
            f"{broken} ta super admin xodim dunyosiga o'tmadi — migratsiya "
            "to'xtatildi, aks holda platformaga kirish yopilardi"
        )


def upgrade() -> None:
    _users_columns()
    _staff_telegram_table()
    _backfill()
    _users_constraints()
    _composite_fks()
    _auth_tables()
    _other_columns()
    _rls_new_tables()
    _rewrite_policies()
    _functions()
    _assert_super_admins_usable()


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
