"""Fon vazifalari infratuzilmasi: `jobs` jurnali va `notifications`.

B-bosqich (`tasks/B-fon-vazifalari.md` B1-B2). Ikki jadval:

- `jobs` — worker bajarilishlari jurnali: qaysi vazifa, qaysi klub, natija.
  `/platform/jobs` (B4) shu yerdan o'qiydi.
- `notifications` — Telegram'ga yuboriladigan har bir xabar avval shu
  yerga yoziladi, yuborilgach `sent_at`/`error` qaytib yoziladi. Takror
  yuborishning oldini `(club_id, template, entity_id, chat_id)` unikal
  indeksi oladi — masalan bitta bron uchun «2 soat qoldi» bir marta.

Kirish modeli: bu jadvallar TENANT ma'lumoti emas, worker'ning texnik
yozuvlari. Klub policy'si o'rniga `app.job_writer` claim'i (worker har
tranzaksiyada o'zi qo'yadi) va superadmin uchun `app_platform()` o'qishi.
Claim'ni SQL darajasida qo'lda qo'yish mumkin — bu mavjud kontekst-GUC
modelidan kuchli emas (0034 docstring'idagi muhokama bilan bir xil).

`owner_notify_targets(p_club_id)` — klub EGALARINING chat ro'yxati
(daily_summary, variance_alert uchun). `booking_notify_targets` (0009)
bilan BIR XIL claim (`app.booking_notify_club`) ishlatiladi — o'sha
claim'ga yozilgan `staff_telegram` policy'si shu yerga ham xizmat qiladi,
farqi faqat `m.role = 'OWNER'` filtri.

Revision ID: 0035_jobs_notifications
Revises: 0034_closed_shift_guard
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0035_jobs_notifications"
down_revision = "0034_closed_shift_guard"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"
PLATFORM_ROLE = "playbron_platform"


def upgrade() -> None:
    _tables()
    _rls()
    _owner_targets()
    _grants()
    _self_test()


def _tables() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(64), nullable=False),
        # NULL — klubga bog'lanmagan (platforma darajasidagi) bajarilish
        sa.Column(
            "club_id",
            sa.BigInteger,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column(
            "run_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.CheckConstraint("status IN ('running', 'done', 'error')", name="jobs_status_ck"),
        sa.CheckConstraint("attempts >= 0", name="jobs_attempts_nonneg_ck"),
    )
    op.create_index("jobs_kind_run_ix", "jobs", ["kind", "run_at"])
    op.create_index("jobs_club_ix", "jobs", ["club_id"])

    op.create_table(
        "notifications",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id",
            sa.BigInteger,
            sa.ForeignKey("clubs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recipient_kind", sa.String(16), nullable=False),
        # Audit uchun: users.id (mijoz yoki xodim). Yuborish chat_id bo'yicha.
        sa.Column("recipient_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=True),
        # Chat NAVBATGA QO'YISH paytida hal qilinadi — yuborish bosqichida
        # RLS o'qishlari kerak bo'lmaydi (fon vazifasining eng tuzoqli joyi)
        sa.Column("chat_id", sa.BigInteger, nullable=False),
        sa.Column("channel", sa.String(16), nullable=False, server_default="TELEGRAM"),
        sa.Column("template", sa.String(64), nullable=False),
        # Nimaga tegishli: booking_id, shift_id yoki sana (YYYYMMDD butun son)
        sa.Column("entity_id", sa.BigInteger, nullable=False),
        sa.Column(
            "payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "recipient_kind IN ('OWNER', 'STAFF', 'CUSTOMER')",
            name="notifications_recipient_kind_ck",
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'SENT', 'ERROR')", name="notifications_status_ck"
        ),
        sa.CheckConstraint("attempts >= 0", name="notifications_attempts_nonneg_ck"),
    )
    op.create_index("notifications_club_ix", "notifications", ["club_id"])
    op.create_index(
        "notifications_pending_ix",
        "notifications",
        ["status", "created_at"],
    )
    # Takror yuborishga qarshi ikkinchi qatlam (birinchisi — Redis emas!
    # skill §2: faqat Redis qulfiga tayanilmaydi)
    op.execute(
        sa.text(
            "CREATE UNIQUE INDEX notifications_dedup_uk ON notifications"
            " (club_id, template, entity_id, chat_id)"
        )
    )


def _rls() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_job_writer() RETURNS boolean
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(current_setting('app.job_writer', true), '') = 'true' $$;

            ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
            ALTER TABLE jobs FORCE ROW LEVEL SECURITY;
            ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
            ALTER TABLE notifications FORCE ROW LEVEL SECURITY;

            -- Worker yozadi/o'qiydi (claim bilan); superadmin faqat o'qiydi.
            -- Klub rollari uchun policy ATAYLAB yo'q: bu ops-jurnal, klub
            -- ma'lumoti emas — konsolga kerak bo'lsa alohida bosqichda
            -- ochiladi.
            CREATE POLICY jobs_worker_all ON jobs FOR ALL
                USING (app_job_writer()) WITH CHECK (app_job_writer());
            CREATE POLICY jobs_platform_read ON jobs FOR SELECT USING (app_platform());

            CREATE POLICY notifications_worker_all ON notifications FOR ALL
                USING (app_job_writer()) WITH CHECK (app_job_writer());
            CREATE POLICY notifications_platform_read ON notifications
                FOR SELECT USING (app_platform());
            """
        )
    )


def _owner_targets() -> None:
    op.execute(
        sa.text(
            """
            -- Klub EGALARINING chat ro'yxati. 0009::booking_notify_targets
            -- bilan bir xil claim — staff_telegram'dagi mavjud
            -- `staff_telegram_booking_notify` policy'si shunga xizmat qiladi.
            CREATE OR REPLACE FUNCTION owner_notify_targets(p_club_id bigint)
                RETURNS TABLE(chat_id bigint)
                LANGUAGE plpgsql STABLE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            BEGIN
                PERFORM set_config('app.booking_notify_club', p_club_id::text, true);

                RETURN QUERY
                SELECT st.chat_id FROM staff_telegram st
                WHERE st.chat_id IS NOT NULL AND st.blocked_at IS NULL
                  AND EXISTS (
                      SELECT 1 FROM memberships m
                      WHERE m.user_id = st.user_id AND m.club_id = p_club_id
                        AND m.status = 'active' AND m.role = 'OWNER'
                  );

                PERFORM set_config('app.booking_notify_club', '', true);
            END
            $fn$;

            REVOKE ALL ON FUNCTION owner_notify_targets(bigint) FROM PUBLIC;
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            GRANT SELECT, INSERT, UPDATE ON jobs, notifications TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE jobs_id_seq TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE notifications_id_seq TO {APP_ROLE};
            GRANT SELECT ON jobs, notifications TO {PLATFORM_ROLE};

            DO $do$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ROLE}') THEN
                    ALTER FUNCTION owner_notify_targets(bigint) OWNER TO {PLATFORM_ROLE};
                END IF;
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'owner_notify_targets egasi o''zgartirilmadi (huquq yo''q)';
            END
            $do$;

            GRANT EXECUTE ON FUNCTION owner_notify_targets(bigint) TO {APP_ROLE};
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
    """Claim'siz yozuv yopiq, claim bilan ochiq, dedup ishlaydi,
    `owner_notify_targets` faqat egani qaytaradi."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = (
        "users",
        "organizations",
        "clubs",
        "memberships",
        "staff_telegram",
        "jobs",
        "notifications",
    )
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'jobs.probe.owner', 'active', 'Owner') RETURNING id"
            )
        ).scalar_one()
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'jobs.probe.staff', 'active', 'Staff') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Jobs Probe Org', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Jobs Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        for uid, role in ((owner_id, "OWNER"), (staff_id, "STAFF")):
            conn.execute(
                sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, :r)"),
                {"u": uid, "c": club_id, "r": role},
            )
        for uid, chat in ((owner_id, 111_001), (staff_id, 111_002)):
            conn.execute(
                sa.text(
                    "INSERT INTO staff_telegram (user_id, telegram_id, chat_id)"
                    " VALUES (:u, :t, :c)"
                ),
                {"u": uid, "t": chat, "c": chat},
            )
    finally:
        _force_rls(conn, scoped, enabled=True)

    try:
        # 1. Claim'siz jurnal yozuvi RAD ETILISHI kerak
        savepoint = conn.begin_nested()
        try:
            conn.execute(sa.text("INSERT INTO jobs (kind) VALUES ('probe')"))
        except sa.exc.ProgrammingError:
            savepoint.rollback()  # kutilgan — policy yopiq
        else:
            savepoint.commit()
            raise RuntimeError("jobs_worker_all: claim'siz INSERT o'tib ketdi")

        # 2. Claim bilan jurnal va bildirishnoma yoziladi
        conn.execute(sa.text("SELECT set_config('app.job_writer', 'true', true)"))
        job_id = conn.execute(
            sa.text("INSERT INTO jobs (kind, club_id) VALUES ('probe', :c) RETURNING id"),
            {"c": club_id},
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE jobs SET status = 'done', finished_at = now() WHERE id = :id"),
            {"id": job_id},
        )
        conn.execute(
            sa.text(
                "INSERT INTO notifications"
                " (club_id, recipient_kind, recipient_id, chat_id, template, entity_id)"
                " VALUES (:c, 'OWNER', :u, 111001, 'probe_template', 20260820)"
            ),
            {"c": club_id, "u": owner_id},
        )

        # 3. Dedup: xuddi shu (club, template, entity, chat) IKKINCHI marta
        #    kirmasligi kerak
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                sa.text(
                    "INSERT INTO notifications"
                    " (club_id, recipient_kind, recipient_id, chat_id, template, entity_id)"
                    " VALUES (:c, 'OWNER', :u, 111001, 'probe_template', 20260820)"
                ),
                {"c": club_id, "u": owner_id},
            )
        except sa.exc.IntegrityError:
            savepoint.rollback()  # kutilgan — notifications_dedup_uk
        else:
            savepoint.commit()
            raise RuntimeError("notifications_dedup_uk: takror bildirishnoma o'tib ketdi")

        # 4. owner_notify_targets FAQAT egani qaytaradi (STAFF chati emas)
        chats = [
            int(r.chat_id)
            for r in conn.execute(
                sa.text("SELECT chat_id FROM owner_notify_targets(:c)"), {"c": club_id}
            ).all()
        ]
        if chats != [111_001]:
            raise RuntimeError(
                f"owner_notify_targets: kutilgan [111001], kelgani {chats} —"
                " rol filtri yoki claim policy'si buzilgan"
            )

        conn.execute(sa.text("SELECT set_config('app.job_writer', '', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM notifications WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM jobs WHERE club_id = :c"), {"c": club_id})
        conn.execute(
            sa.text("DELETE FROM staff_telegram WHERE user_id IN (:o, :s)"),
            {"o": owner_id, "s": staff_id},
        )
        conn.execute(sa.text("DELETE FROM memberships WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:o, :s)"), {"o": owner_id, "s": staff_id}
        )
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")
