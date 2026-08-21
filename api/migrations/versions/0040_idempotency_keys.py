"""Idempotency-Key — takroriy pul/bron so'rovi ikki marta bajarilmasin.

Xodim offline navbatining poydevori (`docs/HOLAT.md`): tarmoq sekin bo'lsa
yoki tugma ikki marta bosilsa, `POST` takrorlansa ham amal bir marta
bajarilishi kerak. `core/idempotency.py` shu jadvalni ishlatadi.

Stage 1 — faqat 4 endpoint himoyalanadi (`bookings/router.py::create_staff_booking`,
`pos/router.py::create_order/close_bill/cancel_order`); jadval va modul
qolgan endpoint'lar uchun ham qayta ishlatiladi (keyingi PR).

Revision ID: 0040_idempotency_keys
Revises: 0039_discount_policy
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0040_idempotency_keys"
down_revision = "0039_discount_policy"
branch_labels = None
depends_on = None

APP_ROLE = "playbron_app"


def upgrade() -> None:
    _tables()
    _rls()
    _grants()
    _self_test()


def downgrade() -> None:
    raise NotImplementedError("Migratsiyalar faqat oldinga")


def _tables() -> None:
    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "club_id", sa.BigInteger, sa.ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False
        ),
        # Mijoz (frontend) generatsiya qiladigan UUID — DB darajasida
        # formatga majburlanmaydi, faqat uzunlik cheklanadi.
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        # Sobit satr-konstanta, masalan "POST /bookings/staff" — xom yo'l
        # emas, shuning uchun bitta kalit ikki xil endpoint'ga tasodifan
        # mos kelib qolmaydi.
        sa.Column("route", sa.String(80), nullable=False),
        # sha256(yo'l parametrlari + body) — bir xil kalit BOSHQA so'rov
        # bilan qayta ishlatilganini aniqlash uchun (`IDEMPOTENCY_KEY_REUSED`).
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        # NULL = hali bajarilmoqda. Committed qator doim to'ldirilgan
        # bo'ladi (`core/idempotency.py::finish()` javob qaytishdan OLDIN
        # chaqiriladi, bitta so'rov-tranzaksiyasi ichida).
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_status", sa.SmallInteger, nullable=True),
        sa.Column("response_body", JSONB, nullable=True),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 128", name="idempotency_keys_key_len_ck"
        ),
        sa.CheckConstraint(
            "response_status IS NULL OR response_status BETWEEN 100 AND 599",
            name="idempotency_keys_status_ck",
        ),
        sa.UniqueConstraint(
            "club_id", "idempotency_key", "route", name="idempotency_keys_club_key_route_uk"
        ),
    )
    op.create_index(
        "idempotency_keys_club_created_ix", "idempotency_keys", ["club_id", "created_at"]
    )


def _rls() -> None:
    op.execute(
        sa.text(
            """
            ALTER TABLE idempotency_keys ENABLE ROW LEVEL SECURITY;
            ALTER TABLE idempotency_keys FORCE  ROW LEVEL SECURITY;

            -- `payments`dagi bilan bir xil shakl: butun xodim yozadi va
            -- o'qiydi, faqat o'z klubida. Platform o'qish policy'si
            -- ATAYLAB yo'q — bu jadval faqat `playbron_app` uchun
            -- (loyiha egasi, Stage 1 qamrovi).
            CREATE POLICY idempotency_keys_staff_all ON idempotency_keys FOR ALL
                USING (club_id = app_club_id()
                       AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'))
                WITH CHECK (club_id = app_club_id()
                            AND app_club_role(app_club_id()) IN ('OWNER', 'ADMIN', 'STAFF'));
            """
        )
    )


def _grants() -> None:
    op.execute(
        sa.text(
            f"""
            -- `payments`dan farqli — UPDATE ham kerak, `finish()` qatorni
            -- yakunlaganda `completed_at`/`response_*`ni to'ldiradi.
            GRANT SELECT, INSERT, UPDATE ON idempotency_keys TO {APP_ROLE};
            GRANT USAGE, SELECT ON SEQUENCE idempotency_keys_id_seq TO {APP_ROLE};
            """
        )
    )


def _scoped_force(conn: sa.Connection, tables: tuple[str, ...], *, enabled: bool) -> None:
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
    """Ikki narsa tekshiriladi (`0035` naqshi — bo'sh jadval, backfill yo'q):

    1. `(club_id, idempotency_key, route)` UNIQUE haqiqatan to'sadimi.
    2. `idempotency_keys` tenant bo'yicha izolyatsiyalanganmi (GUC'siz bo'sh).

    Lokal superuser/`BYPASSRLS` — `_exempt()` `True`, RLS'ning o'zi
    tekshirilmaydi (superuser uni har doim chetlab o'tadi). Shuning uchun
    migratsiya qo'shilgach `check_render_shape.py` ALOHIDA yuritiladi.
    """
    conn = op.get_bind()
    if _exempt(conn):
        return

    setup = ("users", "organizations", "clubs")
    _scoped_force(conn, setup, enabled=False)
    owner_id = org_id = club_id = None
    try:
        owner_id = conn.execute(
            sa.text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', 'idem.probe', 'active', 'P') RETURNING id"
            )
        ).scalar_one()
        org_id = conn.execute(
            sa.text(
                "INSERT INTO organizations (owner_user_id, name, status)"
                " VALUES (:u, 'Idem Probe Org', 'active') RETURNING id"
            ),
            {"u": owner_id},
        ).scalar_one()
        club_id = conn.execute(
            sa.text(
                "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'Idem Probe Club', 'draft')"
                " RETURNING id"
            ),
            {"o": org_id},
        ).scalar_one()
    finally:
        _scoped_force(conn, setup, enabled=True)

    # `idempotency_keys` FORCE faqat qatorni yozish uchun vaqtincha olinadi
    # (migratsiya egasida mos GUC yo'q — `WITH CHECK` yiqilardi). Yozilgach
    # DARHOL qaytariladi, chunki 2-tekshiruv aynan FORCE YOQILGAN holatda
    # izolyatsiya ishlashini isbotlashi kerak.
    row_id = None
    _scoped_force(conn, ("idempotency_keys",), enabled=False)
    try:
        row_id = conn.execute(
            sa.text(
                "INSERT INTO idempotency_keys"
                " (club_id, idempotency_key, route, request_hash, created_by)"
                " VALUES (:c, 'probe-key', 'POST /probe', 'hash1', :u) RETURNING id"
            ),
            {"c": club_id, "u": owner_id},
        ).scalar_one()

        # 1. Bir xil (club_id, key, route) ikkinchi marta — 23505 kutiladi.
        savepoint = conn.begin_nested()
        try:
            conn.execute(
                sa.text(
                    "INSERT INTO idempotency_keys"
                    " (club_id, idempotency_key, route, request_hash, created_by)"
                    " VALUES (:c, 'probe-key', 'POST /probe', 'hash2', :u)"
                ),
                {"c": club_id, "u": owner_id},
            )
        except sa.exc.DBAPIError as exc:
            savepoint.rollback()
            if getattr(exc.orig, "sqlstate", None) != "23505":
                raise
        else:
            savepoint.rollback()
            raise RuntimeError(
                "idempotency_keys_club_key_route_uk takroriy kalitni o'tkazib yubordi"
            )
    finally:
        _scoped_force(conn, ("idempotency_keys",), enabled=True)

    try:
        # 2. FORCE qayta yoqilgan, GUC yo'q — izolyatsiya ishlayotgan bo'lsa
        # hech nima ko'rinmasligi kerak (qator hali o'chirilmagan).
        blind = conn.execute(sa.text("SELECT count(*) FROM idempotency_keys")).scalar_one()
        if blind != 0:
            raise RuntimeError(
                f"idempotency_keys_staff_all izolyatsiya qilmadi — GUC'siz {blind} qator ko'rindi"
            )
    finally:
        _scoped_force(conn, ("users", "organizations", "clubs", "idempotency_keys"), enabled=False)
        try:
            if row_id is not None:
                conn.execute(sa.text("DELETE FROM idempotency_keys WHERE id = :i"), {"i": row_id})
            if club_id is not None:
                conn.execute(sa.text("DELETE FROM clubs WHERE id = :c"), {"c": club_id})
            if org_id is not None:
                conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})
            if owner_id is not None:
                conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": owner_id})
        finally:
            _scoped_force(
                conn, ("users", "organizations", "clubs", "idempotency_keys"), enabled=True
            )
