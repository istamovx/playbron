"""Xodim ma'lumotini tahrirlash — ism va rol.

Production-readiness audit (2026-08-16, reja #14): `staff/router.py`da
Create bor edi, Edit yo'q edi — `auth_create_staff()`ning O'ZIDAGI rol
shifti mantig'ini (`0007_membership_policy_recursion.py`) TAKRORLAMAY,
xuddi shu qoidalarni ikkinchi SECURITY DEFINER funksiyaga o'tkazadi —
ikkita alohida joyda bir xil xavfsizlik mantig'ini yozib, ularni
sinxron ushlab turish xavfidan qochish uchun.

Qoidalar (auth_create_staff bilan AYNAN bir xil ruh):
  - Faqat aktiv OWNER/ADMIN a'zosi chaqira oladi.
  - OWNER roli bu funksiya orqali HECH QACHON berilmaydi va HECH QACHON
    o'zgartirilmaydi (nishon OWNER bo'lsa — rad).
  - ADMIN faqat STAFF'ni tahrirlay oladi va faqat STAFF rolini bera oladi
    (o'zini yoki boshqa ADMIN'ni emas — o'z-o'zini imtiyoz oshirish yo'q).
"""

import sqlalchemy as sa
from alembic import op

revision = "0019_staff_update"
down_revision = "0018_platform_log_read"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"


def upgrade() -> None:
    _function()
    _self_test()


def _function() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION auth_update_staff(
                p_target_user_id bigint,
                p_first_name     text,
                p_role           text
            )
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

                IF p_role NOT IN ('ADMIN', 'STAFF') THEN
                    RAISE EXCEPTION 'ROLE_NOT_ALLOWED';
                END IF;

                SELECT m.role INTO actor_role FROM memberships m
                 WHERE m.club_id = club AND m.user_id = actor AND m.status = 'active';

                IF actor_role IS NULL OR actor_role NOT IN ('OWNER', 'ADMIN') THEN
                    RETURN false;
                END IF;

                SELECT m.role INTO target_role FROM memberships m
                 WHERE m.club_id = club AND m.user_id = p_target_user_id
                   AND m.status = 'active';

                IF target_role IS NULL THEN
                    RETURN false;
                END IF;

                IF target_role = 'OWNER' THEN
                    RAISE EXCEPTION 'ROLE_NOT_ALLOWED';
                END IF;

                IF actor_role = 'ADMIN' AND (target_role <> 'STAFF' OR p_role <> 'STAFF') THEN
                    RAISE EXCEPTION 'ROLE_NOT_ALLOWED';
                END IF;

                UPDATE users SET first_name = p_first_name, display_name = p_first_name
                 WHERE id = p_target_user_id;

                UPDATE memberships SET role = p_role
                 WHERE club_id = club AND user_id = p_target_user_id AND status = 'active';

                RETURN true;
            END
            $fn$;

            GRANT EXECUTE ON FUNCTION auth_update_staff(bigint, text, text) TO {APP_ROLE};
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
    """`auth_update_staff()`ning o'zi SECURITY DEFINER — RLS'ga bog'liq
    emas (jadval ichida to'g'ridan-to'g'ri UPDATE qiladi). Lekin PROBE
    o'rnatish (users/organizations/clubs/memberships'ga xom INSERT)
    RLS ostida — Render shaklidagi (superuser emas, BYPASSRLS yo'q)
    muhitda `0016`/`0017`/`0018`dagi bilan bir xil `_force_rls` naqshi
    shart, aks holda probe o'zi RLS tomonidan rad etiladi."""
    conn = op.get_bind()
    exempt = _exempt(conn)

    scoped = ("users", "organizations", "clubs", "memberships")
    if not exempt:
        _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'staff.update.probe.owner', 'active', 'Owner')"
                " RETURNING id"
            )
        ).scalar_one()
        admin_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'staff.update.probe.admin', 'active', 'Admin')"
                " RETURNING id"
            )
        ).scalar_one()
        staff_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'staff.update.probe.staff', 'active', 'Staff')"
                " RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Staff Update Probe Org', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'Staff Update Probe Club', 'active') RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
        for uid, role in ((owner_id, "OWNER"), (admin_id, "ADMIN"), (staff_id, "STAFF")):
            conn.execute(
                sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, :r)"),
                {"u": uid, "c": club_id, "r": role},
            )
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=True)

    try:
        # `memberships_read` (`0007`) boshqa a'zoning qatorini FAQAT
        # `app_club_role_claim()` (GUC `app.club_role`, JWT da'vosidan —
        # jadvaldan EMAS, `core/db.py::_apply_context()`dagi bilan bir xil)
        # OWNER/ADMIN bo'lsa ochadi — funksiya ICHIDAGI nishon qidiruvi
        # ham shu policy ostida, shuning uchun probe buni ham qo'yishi shart.
        # ADMIN o'z STAFF'ini STAFF sifatida tahrirlashi mumkin
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(admin_id)})
        conn.execute(sa.text("SELECT set_config('app.club_id', :c, true)"), {"c": str(club_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'ADMIN', true)"))
        ok = conn.execute(
            sa.text("SELECT auth_update_staff(:t, 'Staff Renamed', 'STAFF')"),
            {"t": staff_id},
        ).scalar_one()
        if not ok:
            raise RuntimeError("auth_update_staff: ADMIN o'z STAFF'ini tahrirlay olmadi")

        # ADMIN boshqa ADMIN'ni tahrirlay OLMASLIGI kerak. `RAISE EXCEPTION`
        # butun tranzaksiyani "aborted" holatga o'tkazadi — try/except
        # YOLG'IZ O'ZI yetarli emas, SAVEPOINT bilan izolyatsiya qilinadi
        # (`core/audit.py::log_action`dagi bilan bir xil saboq).
        blocked = False
        conn.execute(sa.text("SAVEPOINT admin_ceiling_probe"))
        try:
            conn.execute(
                sa.text("SELECT auth_update_staff(:t, 'Admin Renamed', 'STAFF')"),
                {"t": admin_id},
            )
        except Exception as exc:  # noqa: BLE001
            blocked = "ROLE_NOT_ALLOWED" in str(exc)
        finally:
            conn.execute(sa.text("ROLLBACK TO SAVEPOINT admin_ceiling_probe"))
        if not blocked:
            raise RuntimeError("auth_update_staff: ADMIN boshqa ADMIN'ni tahrirlay oldi — xavfli")

        # OWNER'ni HECH KIM tahrirlay olmasligi kerak (o'zi OWNER bo'lsa ham)
        conn.execute(sa.text("SELECT set_config('app.user_id', :u, true)"), {"u": str(owner_id)})
        conn.execute(sa.text("SELECT set_config('app.club_role', 'OWNER', true)"))
        owner_blocked = False
        conn.execute(sa.text("SAVEPOINT owner_immutable_probe"))
        try:
            conn.execute(
                sa.text("SELECT auth_update_staff(:t, 'Owner Renamed', 'ADMIN')"),
                {"t": owner_id},
            )
        except Exception as exc:  # noqa: BLE001
            owner_blocked = "ROLE_NOT_ALLOWED" in str(exc)
        finally:
            conn.execute(sa.text("ROLLBACK TO SAVEPOINT owner_immutable_probe"))
        if not owner_blocked:
            raise RuntimeError("auth_update_staff: OWNER roli o'zgartirilishi mumkin bo'ldi — xavfli")

        conn.execute(sa.text("SELECT set_config('app.user_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_id', '0', true)"))
        conn.execute(sa.text("SELECT set_config('app.club_role', '', true)"))
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM memberships WHERE club_id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:o, :a, :s)"),
            {"o": owner_id, "a": admin_id, "s": staff_id},
        )
        if not exempt:
            _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
