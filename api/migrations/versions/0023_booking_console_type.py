"""Konsol turi — xonadan bron/hisob darajasiga ko'chirildi.

Loyiha egasining so'rovi (2026-08-16): "Xona qo'shganda konsolni tanlash
kerak emas. Qaysi konsol ekanligini mijozning bron qilishi vaqtida
belgilash imkonini berish kerak va xodim bron qilsa yoki hisob ochsa
o'shanda tanlasin. Xonaga konsol biriktirmaslik kerak."

Orqaga moslik — hech qanday ma'lumot yo'qolmaydi:
  * Mavjud xonalarning `console_type`i SAQLANADI, faqat `NOT NULL`
    cheklovi olib tashlanadi — mini-app'ning eski konsol-filtr oqimi
    o'zgarishsiz ishlayveradi (`slots.ts::consoleTypes()`).
  * `bookings.console_type` YANGI ustun — backfill orqali mavjud har bir
    bronga o'zining xonasidagi (o'sha lahzadagi) konsol turi yoziladi,
    keyin NOT NULL qilinadi.
  * Yangi xona endi konsolsiz yaratiladi (`console_type IS NULL`) —
    shunday xonaga bron/hisob ochilganda `console_type` endi MAJBURIY
    (`bookings/service.py`dagi orqaga moslik qatlami).

Revision ID: 0023_booking_console_type
Revises: 0022_bot_menu_context
"""

import sqlalchemy as sa
from alembic import op

revision = "0023_booking_console_type"
down_revision = "0022_bot_menu_context"
branch_labels = None
depends_on = None

# `0009_bookings.py`dagi bilan bir xil — bitta manba bo'lishi kerak edi,
# lekin loyihada hali umumiy konstanta fayli yo'q (Explore topilmasi,
# 2026-08-16).
CONSOLE_TYPES = ("ps3", "ps4", "ps4pro", "ps5", "ps5pro")


def upgrade() -> None:
    _add_column()
    _backfill()
    _finalize()
    _self_test()


def _add_column() -> None:
    op.add_column("bookings", sa.Column("console_type", sa.String(16), nullable=True))


def _force_rls(conn: sa.Connection, tables: tuple[str, ...], *, enabled: bool) -> None:
    """`0005_two_worlds_auth.py::_force_rls()` bilan bir xil naqsh — Render
    bepul rejasida migratsiya roli ham BYPASSRLS emas (`[[render-free-tier-
    no-bypassrls]]`), lokal superuser buni yashiradi. `ENABLE`ga TEGILMAYDI."""
    state = "FORCE" if enabled else "NO FORCE"
    for table in tables:
        conn.execute(sa.text(f"ALTER TABLE {table} {state} ROW LEVEL SECURITY"))


def _backfill() -> None:
    conn = op.get_bind()
    # `stations` — JOIN orqali FAQAT o'qiladi, lekin RLS SELECT policy'si
    # GUC talab qilsa bu ham 0 qator "ko'rar" edi — ikkalasi ham himoyalanadi.
    _force_rls(conn, ("bookings", "stations"), enabled=False)
    conn.execute(
        sa.text(
            "UPDATE bookings SET console_type = stations.console_type"
            " FROM stations WHERE stations.id = bookings.station_id"
        )
    )
    _force_rls(conn, ("bookings", "stations"), enabled=True)


def _finalize() -> None:
    op.alter_column("bookings", "console_type", nullable=False)
    op.create_check_constraint(
        "bookings_console_type_ck", "bookings", f"console_type IN {CONSOLE_TYPES}"
    )
    # Xona endi konsolga MAJBURIY bog'lanmaydi — mavjud qiymatlar
    # o'zgarmaydi, faqat NOT NULL cheklovi olib tashlanadi.
    op.alter_column("stations", "console_type", nullable=True)


def _self_test() -> None:
    conn = op.get_bind()
    null_count = conn.execute(
        sa.text("SELECT count(*) FROM bookings WHERE console_type IS NULL")
    ).scalar_one()
    if null_count != 0:
        raise RuntimeError(f"backfill to'liq emas — {null_count} bron console_type'siz qoldi")


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
