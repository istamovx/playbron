"""Optimistik konkurrensiya (`bookings.version`) va offline command audit izi
(`audit_log.command_id`).

Manba: `playbron-security-offline-10-10-audit.md` §15 ("Optimistic
concurrency / versioning") va §18 ("Audit logni offline command bilan
bog'lash").

**`bookings.version`.** Faqat `extend_booking()` uchun: `confirm`/`reject`/
`cancel` allaqachon `status` state-machine tekshiruvi bilan himoyalangan
(masalan ikki xodim bir bronni parallel `cancel`/`extend` qilsa, ikkinchisi
`status != CONFIRMED` bilan tabiiy ravishda 409 oladi — `bookings/service.py`).
Lekin ikki xodim BIR VAQTDA ikkalasi ham `CONFIRMED` bronni uzaytirsa,
holat o'zgarmagani uchun bu tabiiy g'ov ishlamaydi va soatlar sukutan
ustma-ust tushib ketishi mumkin. `version` — har `UPDATE`da trigger bilan
avtomatik oshadigan hisoblagich; klient `expected_version` yuborsa va u
joriy qiymatga mos kelmasa, servis `409 VERSION_CONFLICT` qaytaradi
(`bookings/service.py::extend_booking`). Qolgan amallar uchun alohida
tekshiruv QO'SHILMAYDI — mavjud status-guard yetarli, dublyaj emas.

**`audit_log.command_id`.** Oddiy `text`, FK EMAS: `core/audit.py::log_action()`
o'zining ALOHIDA, chaqiruvchi tranzaksiyasidan mustaqil ulanishida yozadi
(fayl boshidagi izoh) — agar `idempotency_keys.id`ga FK qo'yilsa, u hali
COMMIT bo'lmagan chaqiruvchi tranzaksiyasida yaratilgani uchun alohida
ulanishdan hech qachon ko'rinmaydi va HAR BIR audit yozuvi FK buzilishi
bilan yiqilardi. Shu sabab bu yerda mijoz yuborgan xom `Idempotency-Key`
qiymati (bor bo'lsa) saqlanadi — referensial yaxlitlik emas, faqat qo'lda
korrelyatsiya uchun ("bu amal qaysi offline buyruqdan kelgan?").

Revision ID: 0041_booking_version_command_id
Revises: 0040_idempotency_keys
"""

import sqlalchemy as sa
from alembic import op

revision = "0041_booking_version_command_id"
down_revision = "0040_idempotency_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _bookings_version()
    _audit_command_id()
    _self_test()


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")


def _bookings_version() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE bookings ADD COLUMN version bigint NOT NULL DEFAULT 1;

            CREATE FUNCTION bookings_bump_version() RETURNS trigger AS $$
            BEGIN
                NEW.version := OLD.version + 1;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            -- Ilova qatlami `version`ni HECH QACHON qo'lda yozmaydi — trigger
            -- har qanday UPDATE'da (extend, confirm, reject, cancel, close,
            -- kelajakdagi yangi mutatsiyalar) avtomatik oshiradi. Shu sabab
            -- yangi mutatsiya qo'shilganda versiyalashni "unutib qo'yish"
            -- imkonsiz.
            CREATE TRIGGER bookings_bump_version_trg
                BEFORE UPDATE ON bookings
                FOR EACH ROW
                EXECUTE FUNCTION bookings_bump_version();
            """
        )
    )


def _audit_command_id() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE audit_log ADD COLUMN command_id text NULL;
            ALTER TABLE audit_log ADD CONSTRAINT audit_log_command_id_len_ck
                CHECK (command_id IS NULL OR length(command_id) BETWEEN 1 AND 128);
            CREATE INDEX audit_log_command_id_ix ON audit_log (command_id)
                WHERE command_id IS NOT NULL;
            """
        )
    )


def _self_test() -> None:
    """1. `version` trigger haqiqatan oshadimi va mos kelmagan
    `expected_version` konfliktni ANIQLASH imkonini beradimi (bu yerda
    faqat trigger sinaladi — `409 VERSION_CONFLICT` javobi
    `tests/test_bookings.py`da, HTTP qatlamida).
    2. `audit_log.command_id` yoziladi/o'qiladi va uzunlik CHECK ishlaydi.
    """
    conn = op.get_bind()
    scoped = ("clubs", "organizations", "users", "stations", "bookings", "audit_log")
    for table in scoped:
        conn.execute(sa.text(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY"))

    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'migration.verprobe', 'active', 'probe') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                " VALUES (:o, 'verprobe', 'active', NULL) RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'verprobe', 'active')"
                " RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        station_id = conn.execute(
            sa.text(
                "INSERT INTO stations (club_id, code, console_type, rate)"
                " VALUES (:c, 'VERPROBE', 'ps5', 30000) RETURNING id"
            ),
            {"c": club_id},
        ).scalar_one()
        booking_id, initial_version = conn.execute(
            sa.text(
                "INSERT INTO bookings (club_id, station_id, customer_id, source, status,"
                " period, hours, rate_snapshot, console_type)"
                " VALUES (:c, :s, :u, 'MINIAPP', 'CONFIRMED',"
                " tstzrange(now(), now() + interval '1 hour'), 1, 30000, 'ps5')"
                " RETURNING id, version"
            ),
            {"c": club_id, "s": station_id, "u": owner_id},
        ).one()

        if initial_version != 1:
            raise RuntimeError(f"bookings.version sukut qiymati 1 emas — {initial_version}")

        new_version = conn.execute(
            sa.text("UPDATE bookings SET hours = 2 WHERE id = :b RETURNING version"),
            {"b": booking_id},
        ).scalar_one()
        if new_version != 2:
            raise RuntimeError(
                f"bookings_bump_version_trg ishlamadi — kutilgan 2, olindi {new_version}"
            )

        # `audit_log.command_id` — yozish va uzunlik CHECK.
        conn.execute(
            sa.text(
                "INSERT INTO audit_log (actor_user_id, club_id, action, command_id)"
                " VALUES (:u, :c, 'probe_action', 'cmd-probe-1')"
            ),
            {"u": owner_id, "c": club_id},
        )
        stored = conn.execute(
            sa.text("SELECT command_id FROM audit_log WHERE action = 'probe_action'")
        ).scalar_one()
        if stored != "cmd-probe-1":
            raise RuntimeError("audit_log.command_id kutilgan qiymatni saqlamadi")

        raised = False
        try:
            with conn.begin_nested():
                conn.execute(
                    sa.text(
                        "INSERT INTO audit_log (actor_user_id, club_id, action, command_id)"
                        " VALUES (:u, :c, 'probe_action_bad', '')"
                    ),
                    {"u": owner_id, "c": club_id},
                )
        except sa.exc.DBAPIError as exc:
            raised = getattr(getattr(exc, "orig", None), "sqlstate", None) == "23514"
        if not raised:
            raise RuntimeError("audit_log_command_id_len_ck bo'sh satrni o'tkazib yubordi")
    finally:
        conn.execute(sa.text("DELETE FROM audit_log WHERE action LIKE 'probe_action%'"))
        conn.execute(sa.text("DELETE FROM organizations WHERE name = 'verprobe'"))
        conn.execute(
            sa.text("DELETE FROM users WHERE login = 'migration.verprobe' AND kind = 'staff'")
        )
        for table in scoped:
            conn.execute(sa.text(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY"))
