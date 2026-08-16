"""Tashkilot to'xtatilsa — a'zolarining kirishi bloklanadi.

Loyiha egasining so'rovi (2026-08-16): "Super admin rolida klublar
qismida ish bor. Klubni o'chirish yoki faoliyatini to'xtatib qo'yish
mumkin bo'lsin." `organizations.status='suspended'` (`0016_platform_
org_admin.py`) ALLAQACHON mavjud edi, lekin faqat KO'RSATISH uchun —
`staff/settings.tsx`dagi ogohlantirish buni ANIQ aytadi: "Hozircha
faqat ko'rsatish maqsadida, kirish/bron avtomatik bloklanmaydi".

`org_active_for_user()` SECURITY DEFINER — `0022`/`0025`dagi bilan bir
xil naqsh (`app_org_check_claim()` GUC): foydalanuvchining faol
a'zoliklari orqali bog'langan tashkilotlardan KAMIDA BITTASI
`suspended` BO'LMASA `true`; a'zolik UMUMAN yo'q bo'lsa ham `true`
(masalan hali membershipsiz OWNER — bu funksiya faqat "suspended
tashkilot" holatini bloklaydi, "a'zolik yo'qligini" emas).

MUHIM: `status <> 'active'` EMAS, `status <> 'suspended'` tekshiriladi —
yangi ro'yxatdan o'tgan tashkilot `ORG_PENDING` ("pending") holatida
tug'iladi (`models.py::Organization.status` default), va bu OWNER
ro'yxatdan o'tgach DARHOL kira olishi kerak (`signup.py` oqimi). Faqat
super admin ANIQ `suspended` deb belgilagan tashkilot bloklanadi.

Revision ID: 0026_org_suspend_login
Revises: 0025_payment_proof_bot
"""

import sqlalchemy as sa
from alembic import op

revision = "0026_org_suspend_login"
down_revision = "0025_payment_proof_bot"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"


def upgrade() -> None:
    _claim_function()
    _rls()
    _function()
    _self_test()


def _claim_function() -> None:
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION app_org_check_claim() RETURNS boolean
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(NULLIF(current_setting('app.org_check', true), ''), 'false')::boolean $$;
            """
        )
    )


def _rls() -> None:
    op.execute(
        sa.text(
            """
            CREATE POLICY memberships_org_check ON memberships FOR SELECT
                USING (app_org_check_claim());
            CREATE POLICY clubs_org_check ON clubs FOR SELECT
                USING (app_org_check_claim());
            CREATE POLICY organizations_org_check ON organizations FOR SELECT
                USING (app_org_check_claim());
            """
        )
    )


def _function() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION org_active_for_user(p_user_id bigint)
                RETURNS boolean
                LANGUAGE plpgsql STABLE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                v_total int;
                v_not_suspended int;
            BEGIN
                PERFORM set_config('app.org_check', 'true', true);

                SELECT count(*), count(*) FILTER (WHERE o.status <> 'suspended')
                  INTO v_total, v_not_suspended
                  FROM memberships m
                  JOIN clubs c ON c.id = m.club_id
                  JOIN organizations o ON o.id = c.org_id
                 WHERE m.user_id = p_user_id AND m.status = 'active';

                PERFORM set_config('app.org_check', '', true);
                RETURN v_total = 0 OR v_not_suspended > 0;
            END
            $fn$;

            GRANT EXECUTE ON FUNCTION org_active_for_user(bigint) TO {APP_ROLE};
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
    """Faol tashkilot a'zosi — true. Suspended tashkilot a'zosi — false.
    A'zolik yo'q — true. Pending tashkilot a'zosi — true (yangi ro'yxatdan
    o'tgan OWNER darhol kira olishi kerak, faqat ANIQ suspended bloklanadi;
    bu SO'NGGI holat ATAYLAB tekshiriladi — birinchi versiyada
    `status <> 'active'` yozilgan edi va bu barcha yangi signup'larni
    bloklardi, `test_owner_signup.py` shu regressiyani ushladi)."""
    conn = op.get_bind()
    exempt = _exempt(conn)

    scoped = ("users", "organizations", "clubs", "memberships")
    if not exempt:
        _force_rls(conn, scoped, enabled=False)
    try:
        active_owner = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'orgcheck.probe.active', 'active', 'Active')"
                " RETURNING id"
            )
        ).scalar_one()
        suspended_owner = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'orgcheck.probe.suspended', 'active', 'Suspended')"
                " RETURNING id"
            )
        ).scalar_one()
        lonely = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'orgcheck.probe.lonely', 'active', 'Lonely')"
                " RETURNING id"
            )
        ).scalar_one()
        pending_owner = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'orgcheck.probe.pending', 'active', 'Pending')"
                " RETURNING id"
            )
        ).scalar_one()

        active_org = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'OrgCheck Active Org', 'active') RETURNING id"
            ),
            {"o": active_owner},
        ).scalar_one()
        suspended_org = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'OrgCheck Suspended Org', 'suspended') RETURNING id"
            ),
            {"o": suspended_owner},
        ).scalar_one()
        pending_org = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'OrgCheck Pending Org', 'pending') RETURNING id"
            ),
            {"o": pending_owner},
        ).scalar_one()

        active_club = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'OrgCheck Active Club', 'active') RETURNING id"
            ),
            {"o": active_org},
        ).scalar_one()
        suspended_club = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'OrgCheck Suspended Club', 'active') RETURNING id"
            ),
            {"o": suspended_org},
        ).scalar_one()
        pending_club = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status)"
                " VALUES (:o, 'OrgCheck Pending Club', 'active') RETURNING id"
            ),
            {"o": pending_org},
        ).scalar_one()

        conn.execute(
            sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"),
            {"u": active_owner, "c": active_club},
        )
        conn.execute(
            sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"),
            {"u": suspended_owner, "c": suspended_club},
        )
        conn.execute(
            sa.text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"),
            {"u": pending_owner, "c": pending_club},
        )
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=True)

    try:
        active_ok = conn.execute(
            sa.text("SELECT org_active_for_user(:u)"), {"u": active_owner}
        ).scalar_one()
        if active_ok is not True:
            raise RuntimeError("org_active_for_user: faol tashkilot a'zosi bloklandi")

        suspended_ok = conn.execute(
            sa.text("SELECT org_active_for_user(:u)"), {"u": suspended_owner}
        ).scalar_one()
        if suspended_ok is not False:
            raise RuntimeError("org_active_for_user: to'xtatilgan tashkilot a'zosi bloklanmadi")

        lonely_ok = conn.execute(
            sa.text("SELECT org_active_for_user(:u)"), {"u": lonely}
        ).scalar_one()
        if lonely_ok is not True:
            raise RuntimeError("org_active_for_user: a'zoligi yo'q foydalanuvchi bloklandi")

        pending_ok = conn.execute(
            sa.text("SELECT org_active_for_user(:u)"), {"u": pending_owner}
        ).scalar_one()
        if pending_ok is not True:
            raise RuntimeError(
                "org_active_for_user: yangi ro'yxatdan o'tgan (pending) tashkilot bloklandi"
            )
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=False)
        conn.execute(
            sa.text("DELETE FROM memberships WHERE club_id IN (:a, :s, :p)"),
            {"a": active_club, "s": suspended_club, "p": pending_club},
        )
        conn.execute(
            sa.text("DELETE FROM clubs WHERE id IN (:a, :s, :p)"),
            {"a": active_club, "s": suspended_club, "p": pending_club},
        )
        conn.execute(
            sa.text("DELETE FROM organizations WHERE id IN (:a, :s, :p)"),
            {"a": active_org, "s": suspended_org, "p": pending_org},
        )
        conn.execute(
            sa.text("DELETE FROM users WHERE id IN (:a, :s, :l, :p)"),
            {"a": active_owner, "s": suspended_owner, "l": lonely, "p": pending_owner},
        )
        if not exempt:
            _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
