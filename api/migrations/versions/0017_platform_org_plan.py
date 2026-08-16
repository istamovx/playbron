"""Platforma — to'lov qayd etilganda tashkilot tarifini yangilash.

Loyiha egasining topilmasi (2026-08-16): "Klublar" jadvalida to'lov
qo'shilgandan keyin ham TARIF/AMAL QILISH MUDDATI ustunlari bo'sh qolar
edi. Sabab — `record_payment()` faqat `platform_payments`ga yozadi,
`organizations.plan_code`ni hech qachon yangilamas edi (ustun `0001`dan
bor, lekin `app_platform()` uchun UPDATE policy yo'q edi — faqat
`organizations_tenant` (`owner_user_id = app_user_id() OR id =
app_org_id()`) bor, bu platforma sessiyasida hech qachon rost bo'lmaydi).

`playbron_platform` GRANT INSERT, UPDATE ON organizations`si `0001`dan
buyon bor edi — bu yerda YETISHMAYOTGANI faqat RLS qatlami
(`[[playbron-grant-vs-rls-blind-spot]]`): GRANT yozishga ruxsat beradi,
lekin policy yo'q bo'lsa RLS baribir HAR BIR qatorni suzib tashlaydi —
xato chiqmaydi, shunchaki 0 qator yangilanadi.

Amal qilish muddati alohida ustun sifatida SAQLANMAYDI — hisoblanadigan
qiymat (`so'nggi to'lov paid_at + period_months`), har safar
`list_organizations()` so'nggi `platform_payments` qatoridan hosil
qiladi. Yangi ustun kerak emas, faqat o'qish policy'si allaqachon bor
(`platform_payments_platform_all`, `0016`).

Revision ID: 0017_platform_org_plan
Revises: 0016_platform_org_admin
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_platform_org_plan"
down_revision = "0016_platform_org_admin"
branch_labels = None
depends_on = None

PLATFORM_ROLE = "playbron_platform"


def upgrade() -> None:
    _rls()
    _self_test()


def _rls() -> None:
    op.execute(
        sa.text(
            """
            -- `organizations_tenant` (0001) bilan OR bo'lib qo'shiladi —
            -- klub egasining o'z yo'li tegilmaydi, faqat platforma sessiyasi
            -- uchun qo'shimcha yo'l ochiladi. GRANT allaqachon bor (0001).
            CREATE POLICY organizations_platform_write ON organizations
                FOR UPDATE USING (app_platform()) WITH CHECK (app_platform());
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
    """GUC'siz UPDATE 0 qator o'zgartiradi (xato emas — RLS jimgina suzadi),
    `app.platform=true` bilan esa ishlaydi (`0015`/`0016`dagi bilan bir xil
    naqsh)."""
    conn = op.get_bind()
    if _exempt(conn):
        return

    scoped = ("users", "organizations")
    _force_rls(conn, scoped, enabled=False)
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'platform.plan.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:o, 'Platform Plan Probe Org', 'active') RETURNING id"
            ),
            {"o": owner_id},
        ).scalar_one()
    finally:
        _force_rls(conn, scoped, enabled=True)

    try:
        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
        blocked = conn.execute(
            sa.text("UPDATE organizations SET plan_code = NULL WHERE id = :o"), {"o": org_id}
        )
        if blocked.rowcount != 0:
            raise RuntimeError(
                "organizations_platform_write: app.platform o'rnatilmasa ham UPDATE o'tdi"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'true', true)"))
        allowed = conn.execute(
            sa.text("UPDATE organizations SET plan_code = 'gold' WHERE id = :o"), {"o": org_id}
        )
        if allowed.rowcount != 1:
            raise RuntimeError(
                "organizations_platform_write: app.platform=true bo'lsa ham UPDATE o'tmadi"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
    finally:
        _force_rls(conn, scoped, enabled=False)
        conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
        conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        _force_rls(conn, scoped, enabled=True)


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
