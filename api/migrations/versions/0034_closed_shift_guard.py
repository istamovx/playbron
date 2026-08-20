"""Yopilgan smenaga pul yozuvi DB darajasida rad etiladi.

CLAUDE.md §Pul: «Yopilgan smenaning hisobiga ta'sir qiladigan yozuv keyin
o'zgartirilmaydi». Bu qoidani shu paytgacha faqat matn ushlab turardi —
`payments` yoki `expenses` ga yopilgan smenaning `shift_id`si bilan qator
kiritilsa, o'sha smenaning `variance`i retroaktiv o'zgarardi (u har
o'qishda qayta hisoblanadi, `finance/shifts.py`).

Trigger `BEFORE INSERT` ikkala jadvalda: `shift_id` ko'rsatgan smena
`closed` bo'lsa `RAISE EXCEPTION 'SHIFT_CLOSED'` (P0001). Ilova qatlamida
`core/errors.py` uni `409 SHIFT_CLOSED` ga aylantiradi.

Smena holatini o'qish — nomlangan GUC claim naqshi bilan
(`docs/07-patterns.md` §2): trigger chaqiruvchining RLS konteksti ostida
yuradi, `shifts` esa FORCE ostida. Oddiy SELECT ko'rinmagan qatorda NULL
qaytarib qo'riqchini JIMGINA o'chirib qo'ygan bo'lardi (masalan STAFF
boshqa xodimning smenasini ko'rmaydi). Claim policy'si aynan bitta
qatorning FAQAT holatini ochadi va qiymat trigger ichida o'rnatiladi —
tashqaridan berib bo'lmaydi.

Muqobil (yopishda `expected_cash`ni `shifts`ga muzlatish) TANLANMAGAN:
u hisobni ikki joyda saqlaydi va «hisob bitta manbadan» qoidasiga zid.

Revision ID: 0034_closed_shift_guard
Revises: 0033_shift_per_club_uk
"""

import sqlalchemy as sa
from alembic import op

revision = "0034_closed_shift_guard"
down_revision = "0033_shift_per_club_uk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            -- Claim: trigger o'qiyotgan bitta smenani ochadi. Qiymat faqat
            -- funksiya ichida o'rnatiladi (set_config ... true = LOCAL).
            CREATE OR REPLACE FUNCTION app_shift_guard_claim() RETURNS bigint
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT NULLIF(current_setting('app.shift_guard_claim', true), '')::bigint $$;

            CREATE POLICY shifts_guard_read ON shifts FOR SELECT
                USING (id = app_shift_guard_claim());

            CREATE OR REPLACE FUNCTION reject_write_to_closed_shift() RETURNS trigger
                LANGUAGE plpgsql
                SET search_path = public, pg_temp
            AS $$
            DECLARE
                shift_status text;
            BEGIN
                IF NEW.shift_id IS NULL THEN
                    RETURN NEW;  -- smenasiz yozuv (masalan TRANSFER xarajat)
                END IF;

                PERFORM set_config('app.shift_guard_claim', NEW.shift_id::text, true);
                SELECT status INTO shift_status FROM shifts WHERE id = NEW.shift_id;
                PERFORM set_config('app.shift_guard_claim', '', true);

                IF shift_status IS NULL THEN
                    -- FK baribir yiqitadi, lekin qo'riqchi jim qolmasin
                    RAISE EXCEPTION 'SHIFT_NOT_FOUND';
                END IF;
                IF shift_status = 'closed' THEN
                    RAISE EXCEPTION 'SHIFT_CLOSED';
                END IF;
                RETURN NEW;
            END $$;

            CREATE TRIGGER payments_closed_shift_guard
                BEFORE INSERT ON payments
                FOR EACH ROW EXECUTE FUNCTION reject_write_to_closed_shift();

            CREATE TRIGGER expenses_closed_shift_guard
                BEFORE INSERT ON expenses
                FOR EACH ROW EXECUTE FUNCTION reject_write_to_closed_shift();
            """
        )
    )
    _self_test()


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
    """Qo'riqchini haqiqiy STAFF konteksti ostida buzishga urinadi.

    Superuser RLS'ni butunlay chetlab o'tadi va claim yo'li sinalmaydi —
    shuning uchun `_exempt()` bo'lsa chiqib ketiladi; haqiqiy tekshiruv
    `check_render_shape.py` va CI'ning `api-render-shape` job'ida.
    Kutilgan buzilishlar SAVEPOINT ichida.
    """
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations", "clubs", "memberships", "shifts", "expenses", "payments")
    _force_rls(conn, scoped, enabled=False)
    try:
        admin_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'shiftguard.probe.admin', 'active', 'Probe Admin') RETURNING id"
            )
        ).scalar_one()
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'shiftguard.probe.staff', 'active', 'Probe Staff') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'ShiftGuard Probe Org', 'active') RETURNING id"
            ),
            {"o": admin_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'ShiftGuard Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        for uid, role in ((admin_id, "ADMIN"), (staff_id, "STAFF")):
            conn.execute(
                sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, :r)"),
                {"u": uid, "c": club_id, "r": role},
            )
        # Smenalar ADMIN'niki: 4-probe'da STAFF ularni KO'RMAYDI (shifts
        # policy'si egasi-yoki-admin) — claim yo'li aynan shunda sinaladi
        open_shift = conn.execute(
            sa.text(
                "INSERT INTO shifts (club_id, staff_id, opening_cash)"
                " VALUES (:c, :s, 0) RETURNING id"
            ),
            {"c": club_id, "s": admin_id},
        ).scalar_one()
        closed_shift = conn.execute(
            sa.text(
                "INSERT INTO shifts (club_id, staff_id, opening_cash, status, closed_at)"
                " VALUES (:c, :s, 0, 'closed', now()) RETURNING id"
            ),
            {"c": club_id, "s": admin_id},
        ).scalar_one()
    finally:
        _force_rls(conn, scoped, enabled=True)

    def _expense_probe(shift_id: int) -> None:
        conn.execute(
            sa.text(
                "INSERT INTO expenses"
                " (club_id, spent_on, category, amount, status, created_by, shift_id, method)"
                " VALUES (:c, current_date, 'probe', 1000, 'active', :u, :s, 'CASH')"
            ),
            {"c": club_id, "u": admin_id, "s": shift_id},
        )

    try:
        # Haqiqiy ADMIN konteksti — trigger RLS ostida yuradi
        # (`expenses_owner_admin_all` STAFF'ga INSERT bermaydi)
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(admin_id)})
        conn.execute(sa.text("SELECT set_config('app.club_id', :c, true)"), {"c": str(club_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'ADMIN', true)"))

        # 1. Ochiq smenaga xarajat — O'TISHI kerak (qo'riqchi halal bermaydi)
        savepoint = conn.begin_nested()
        try:
            _expense_probe(open_shift)
        except sa.exc.DBAPIError as exc:
            savepoint.rollback()
            raise RuntimeError(
                f"closed_shift_guard: ochiq smenaga xarajat ham bloklandi — {exc.orig}"
            ) from exc
        else:
            savepoint.commit()

        # 2. Yopilgan smenaga xarajat — SHIFT_CLOSED bilan RAD ETILISHI kerak
        savepoint = conn.begin_nested()
        try:
            _expense_probe(closed_shift)
        except sa.exc.DBAPIError as exc:
            savepoint.rollback()
            if "SHIFT_CLOSED" not in str(exc.orig):
                raise RuntimeError(
                    f"closed_shift_guard: kutilgan SHIFT_CLOSED emas — {exc.orig}"
                ) from exc
        else:
            savepoint.commit()
            raise RuntimeError("closed_shift_guard: yopilgan smenaga xarajat o'tib ketdi")

        # 3. Yopilgan smenaga to'lov — SHIFT_CLOSED (trigger CHECK'lardan
        #    OLDIN ishlaydi, shuning uchun booking/order shart emas)
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                sa.text(
                    "INSERT INTO payments (club_id, shift_id, kind, method, amount, created_by)"
                    " VALUES (:c, :s, 'FINAL', 'CASH', 1000, :u)"
                ),
                {"c": club_id, "s": closed_shift, "u": admin_id},
            )
        except sa.exc.DBAPIError as exc:
            savepoint.rollback()
            if "SHIFT_CLOSED" not in str(exc.orig):
                raise RuntimeError(
                    f"closed_shift_guard: payments'da kutilgan SHIFT_CLOSED emas — {exc.orig}"
                ) from exc
        else:
            savepoint.commit()
            raise RuntimeError("closed_shift_guard: yopilgan smenaga to'lov o'tib ketdi")

        # 4. Claim yo'li: STAFF o'ziga KO'RINMAYDIGAN (adminning) yopiq
        #    smenasiga to'lov yozmoqchi. `payments_staff_all` klub+rol bilan
        #    o'tkazadi; `shifts_guard_read` claim'i bo'lmasa trigger smenani
        #    topolmay SHIFT_NOT_FOUND derdi va qo'riqchi ko'r bo'lardi.
        #    Kutilgan javob — aynan SHIFT_CLOSED.
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(staff_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'STAFF', true)"))
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                sa.text(
                    "INSERT INTO payments (club_id, shift_id, kind, method, amount, created_by)"
                    " VALUES (:c, :s, 'FINAL', 'CASH', 1000, :u)"
                ),
                {"c": club_id, "s": closed_shift, "u": staff_id},
            )
        except sa.exc.DBAPIError as exc:
            savepoint.rollback()
            if "SHIFT_CLOSED" not in str(exc.orig):
                raise RuntimeError(
                    "closed_shift_guard: claim yo'lida kutilgan SHIFT_CLOSED emas"
                    f" — {exc.orig}"
                ) from exc
        else:
            savepoint.commit()
            raise RuntimeError(
                "closed_shift_guard: ko'rinmas yopiq smenaga to'lov o'tib ketdi (claim ishlamadi)"
            )

        conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_role', '', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM expenses WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM payments WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM shifts WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM memberships WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:a, :s)"), {"a": admin_id, "s": staff_id}
        )
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")
