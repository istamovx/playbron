"""Tashkilot to'xtatilganda ochiq sessiyalar ham bekor qilinadi.

Audit topilmasi (2026-08-16). `0026_org_suspend_login.py` KIRISHNI
bloklaydi, lekin ALLAQACHON kirgan xodim ishini davom ettiraverardi va
refresh token rotatsiyasi orqali sessiyani cheksiz uzaytirardi — faqat
qaytadan login qilsa 403 `ORG_SUSPENDED` olardi. Ya'ni "to'xtatish"
amalda faqat YANGI kirishlarni to'sardi.

Bu yanglish va'da bo'lgan: `platform-clubs.tsx`dagi ogohlantirish
(o'sha kuni yozilgan) "Tashkilotning barcha xodimlari kira olmaydi,
saqlangach darhol amal qiladi" deydi.

`platform_revoke_org_sessions()` — SECURITY DEFINER, chunki
`refresh_tokens` uchun `app_platform()` policy'si YO'Q va uni KENG
qilib qo'shish super adminga istalgan tokenni tahrirlash imkonini
berardi. Funksiya esa ANIQ bitta ish qiladi: berilgan tashkilot
klublariga a'zo foydalanuvchilarning bekor qilinmagan tokenlarini
`revoked_at = now()` bilan yopadi.

Revision ID: 0030_suspend_revoke
Revises: 0029_platform_read_gaps
"""

import sqlalchemy as sa
from alembic import op

revision = "0030_suspend_revoke"
down_revision = "0029_platform_read_gaps"
branch_labels = None
depends_on = None

PLATFORM_ROLE = "playbron_platform"
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
            CREATE OR REPLACE FUNCTION app_org_revoke_claim() RETURNS boolean
                LANGUAGE sql STABLE PARALLEL SAFE AS
            $$ SELECT COALESCE(NULLIF(current_setting('app.org_revoke', true), ''), 'false')::boolean $$;
            """
        )
    )


def _rls() -> None:
    op.execute(
        sa.text(
            """
            -- SECURITY DEFINER YETARLI EMAS: funksiya egasi ham
            -- `FORCE ROW LEVEL SECURITY` ostida qoladi va Render bepul
            -- rejasida BYPASSRLS olib bo'lmaydi
            -- (`[[render-free-tier-no-bypassrls]]`). Mavjud
            -- `refresh_tokens_scope` policy'si `user_id = app_user_id()`
            -- talab qiladi — platforma sessiyasida u 0, ya'ni UPDATE
            -- hech qanday qatorga tegmasdi.
            --
            -- GUC-claim naqshi (`0022`/`0025`/`0026` bilan bir xil): tor
            -- policy, kalitni faqat quyidagi funksiya o'z tranzaksiyasida
            -- qo'yadi. Butun jadvalga keng platform policy berilmaydi.
            -- SELECT ham KERAK, faqat UPDATE yetarli emas: Postgres UPDATE
            -- uchun qatorni TOPISH bosqichida SELECT policy'larini ham
            -- qo'llaydi (WHERE sharti bo'lsa). Faqat `FOR UPDATE` bo'lganda
            -- UPDATE 0 qatorga tegardi va sinov "token yopilmadi" berardi.
            CREATE POLICY refresh_tokens_org_revoke_read ON refresh_tokens FOR SELECT
                USING (app_org_revoke_claim());
            CREATE POLICY refresh_tokens_org_revoke ON refresh_tokens FOR UPDATE
                USING (app_org_revoke_claim()) WITH CHECK (app_org_revoke_claim());

            CREATE POLICY memberships_org_revoke ON memberships FOR SELECT
                USING (app_org_revoke_claim());
            CREATE POLICY clubs_org_revoke ON clubs FOR SELECT
                USING (app_org_revoke_claim());
            """
        )
    )


def _function() -> None:
    op.execute(
        sa.text(
            f"""
            CREATE OR REPLACE FUNCTION platform_revoke_org_sessions(p_org_id bigint)
                RETURNS integer
                LANGUAGE plpgsql VOLATILE SECURITY DEFINER
                SET search_path = pg_catalog, public, pg_temp
            AS $fn$
            DECLARE
                v_count integer;
            BEGIN
                -- Faqat platforma konteksti chaqira oladi. Tekshiruv
                -- funksiya ICHIDA, chunki quyidagi GUC RLS'ni ochadi.
                IF NOT app_platform() THEN
                    RETURN 0;
                END IF;

                PERFORM set_config('app.org_revoke', 'true', true);

                UPDATE refresh_tokens rt
                   SET revoked_at = now()
                 WHERE rt.revoked_at IS NULL
                   AND rt.user_id IN (
                       SELECT m.user_id
                         FROM memberships m
                         JOIN clubs c ON c.id = m.club_id
                        WHERE c.org_id = p_org_id AND m.status = 'active'
                   );

                GET DIAGNOSTICS v_count = ROW_COUNT;
                PERFORM set_config('app.org_revoke', '', true);
                RETURN v_count;
            END
            $fn$;

            GRANT EXECUTE ON FUNCTION platform_revoke_org_sessions(bigint) TO {PLATFORM_ROLE};
            GRANT EXECUTE ON FUNCTION platform_revoke_org_sessions(bigint) TO {APP_ROLE};
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
    """Platforma konteksti bo'lmasa 0; bo'lsa a'zolar tokenlari yopiladi.
    Boshqa tashkilotning tokeniga TEGILMAYDI."""
    conn = op.get_bind()
    exempt = _exempt(conn)

    scoped = ("users", "organizations", "clubs", "memberships", "refresh_tokens")
    if not exempt:
        _force_rls(conn, scoped, enabled=False)
    ids: dict[str, int] = {}
    try:
        for tag in ("target", "other"):
            ids[f"user_{tag}"] = conn.execute(
                sa.text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    f" VALUES ('staff', 'revoke.probe.{tag}', 'active', 'P') RETURNING id"
                )
            ).scalar_one()
            ids[f"org_{tag}"] = conn.execute(
                sa.text(
                    "INSERT INTO organizations (owner_user_id, name, status)"
                    f" VALUES (:u, 'Revoke Org {tag}', 'active') RETURNING id"
                ),
                {"u": ids[f"user_{tag}"]},
            ).scalar_one()
            ids[f"club_{tag}"] = conn.execute(
                sa.text(
                    "INSERT INTO clubs (org_id, name, status)"
                    f" VALUES (:o, 'Revoke Club {tag}', 'active') RETURNING id"
                ),
                {"o": ids[f"org_{tag}"]},
            ).scalar_one()
            conn.execute(
                sa.text(
                    "INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"
                ),
                {"u": ids[f"user_{tag}"], "c": ids[f"club_{tag}"]},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO refresh_tokens"
                    " (user_id, token_hash, kind, chain_started_at, expires_at)"
                    f" VALUES (:u, 'revokeprobe{tag}', 'staff', now(), now() + interval '30 days')"
                ),
                {"u": ids[f"user_{tag}"]},
            )
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=True)

    try:
        # Platforma konteksti YO'Q — hech narsa qilmasligi kerak
        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
        blocked = conn.execute(
            sa.text("SELECT platform_revoke_org_sessions(:o)"), {"o": ids["org_target"]}
        ).scalar_one()
        if blocked != 0:
            raise RuntimeError(
                f"platform_revoke_org_sessions: platforma kontekstisiz ham ishladi ({blocked})"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'true', true)"))
        revoked = conn.execute(
            sa.text("SELECT platform_revoke_org_sessions(:o)"), {"o": ids["org_target"]}
        ).scalar_one()
        if revoked != 1:
            raise RuntimeError(
                f"platform_revoke_org_sessions: 1 ta token kutilgan edi, {revoked} yopildi"
            )

        conn.execute(sa.text("SELECT set_config('app.platform', 'false', true)"))
    finally:
        if not exempt:
            _force_rls(conn, scoped, enabled=False)

        # Nishon yopilgan, begona TEGILMAGAN bo'lishi kerak
        target_open = conn.execute(
            sa.text(
                "SELECT count(*) FROM refresh_tokens"
                " WHERE user_id = :u AND revoked_at IS NULL"
            ),
            {"u": ids["user_target"]},
        ).scalar_one()
        other_open = conn.execute(
            sa.text(
                "SELECT count(*) FROM refresh_tokens"
                " WHERE user_id = :u AND revoked_at IS NULL"
            ),
            {"u": ids["user_other"]},
        ).scalar_one()

        for tag in ("target", "other"):
            conn.execute(
                sa.text("DELETE FROM refresh_tokens WHERE user_id = :u"),
                {"u": ids[f"user_{tag}"]},
            )
            conn.execute(
                sa.text("DELETE FROM memberships WHERE club_id = :c"), {"c": ids[f"club_{tag}"]}
            )
            conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": ids[f"club_{tag}"]})
            conn.execute(
                sa.text("DELETE FROM organizations WHERE id = :o"), {"o": ids[f"org_{tag}"]}
            )
            conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": ids[f"user_{tag}"]})

        if not exempt:
            _force_rls(conn, scoped, enabled=True)

        if target_open != 0:
            raise RuntimeError("nishon tashkilot tokeni yopilmadi")
        if other_open != 1:
            raise RuntimeError("BEGONA tashkilot tokeni ham yopildi — funksiya juda keng")


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
