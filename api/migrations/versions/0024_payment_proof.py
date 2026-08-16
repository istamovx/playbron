"""To'lov cheki — o'tkazma tanlanganda mijoz Telegram orqali chek yuboradi.

Loyiha egasining so'rovi (2026-08-16): "Kassa qismida to'lov naqd yoki
o'tkazma bo'lishi mumkin. Bunda agar o'tkazma bo'lsa mijoz o'tkazma qilgan
tranzaksiyasini telegram bot orqali yuboradi... Xodim telegrami va webdagi
kassa qismida ko'rishi mumkin. Tasdiqlasa hisob yopiladi."

Oqim (`pos/service.py::close_bill()`): xodim TRANSFER tanlab yopishga
uringanda, agar mijoz botga ulangan bo'lsa (`customer_id` bor) va chek
hali yuborilmagan bo'lsa — hisob YOPILMAYDI, `payment_proof_status`
`PENDING`ga o'tadi, mijozga bot orqali "chekni yuklang" xabari ketadi.
Mijoz rasm yuborgach `SUBMITTED`. Xodim shu holatda qayta "Yopish"
bossa — bu ENDI tasdiqlash, hisob yopiladi, `CONFIRMED`.

Rasmning o'zi bazada saqlanmaydi — faqat Telegram `file_id` (xavfsiz,
token oshkor bo'lmaydi: ko'rsatish uchun backend proxy qiladi,
`GET .../payment-proof`).

Revision ID: 0024_payment_proof
Revises: 0023_booking_console_type
"""

import sqlalchemy as sa
from alembic import op

revision = "0024_payment_proof"
down_revision = "0023_booking_console_type"
branch_labels = None
depends_on = None

STATUSES = ("PENDING", "SUBMITTED", "CONFIRMED")


def upgrade() -> None:
    op.add_column("bookings", sa.Column("payment_proof_status", sa.String(16), nullable=True))
    op.add_column("bookings", sa.Column("payment_proof_file_id", sa.Text, nullable=True))
    op.add_column(
        "bookings",
        sa.Column("payment_proof_submitted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "bookings_payment_proof_status_ck",
        "bookings",
        f"payment_proof_status IS NULL OR payment_proof_status IN {STATUSES}",
    )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
