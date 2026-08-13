"""Seed: tariflar va super adminlar.

Tarif limitlari `docs/03-entitlements.md` bilan bir xil bo'lishi shart.
Super adminlar **faqat shu yerdan** paydo bo'ladi — UI orqali qo'shish yo'q.

Revision ID: 0002_seed
Revises: 0001_core
"""

import json
import os

import sqlalchemy as sa
from alembic import op

revision = "0002_seed"
down_revision = "0001_core"
branch_labels = None
depends_on = None

BASE_FEATURES = [
    "board_live",
    "timeline_day",
    "pos",
    "bar_orders",
    "shift_close",
    "blocklist",
    "inventory_basic",
    "expenses",
    "reports_daily",
    "online_booking",
    "online_payment",
    "reviews",
]

PLANS = [
    {
        "code": "gold",
        "title": "Gold",
        "price_month": 490_000,
        "price_year": 4_900_000,
        "sort": 1,
        "limits": {
            "clubs": 1,
            "rooms_per_club": 10,
            "staff_per_club": 5,
            "products": 50,
            "rate_plans_per_club": 2,
            "devices_per_club": 30,
            "bookings_per_month": 1500,
            "report_history_days": 90,
            "data_export_per_month": 2,
            "notification_recipients": 1,
        },
        "features": [*BASE_FEATURES, "custom_rate_plans", "data_export"],
    },
    {
        "code": "platinium",
        "title": "Platinium",
        "price_month": 990_000,
        "price_year": 9_900_000,
        "sort": 2,
        "limits": {
            "clubs": 3,
            "rooms_per_club": 30,
            "staff_per_club": 20,
            "products": 300,
            "rate_plans_per_club": 6,
            "devices_per_club": 150,
            "bookings_per_month": 8000,
            "report_history_days": 365,
            "data_export_per_month": 20,
            "notification_recipients": 5,
        },
        "features": [
            *BASE_FEATURES,
            "timeline_history",
            "inventory_costing",
            "reports_weekly_monthly",
            "reports_compare",
            "multi_club",
            "staff_roles",
            "custom_rate_plans",
            "notifications_custom",
            "data_export",
            "priority_support",
        ],
    },
    {
        "code": "infinite",
        "title": "Infinite",
        "price_month": 1_890_000,
        "price_year": 18_900_000,
        "sort": 3,
        "limits": {
            "clubs": None,
            "rooms_per_club": None,
            "staff_per_club": None,
            "products": None,
            "rate_plans_per_club": None,
            "devices_per_club": None,
            "bookings_per_month": None,
            "report_history_days": 1095,
            "data_export_per_month": None,
            "notification_recipients": 20,
        },
        "features": [
            *BASE_FEATURES,
            "timeline_history",
            "inventory_costing",
            "reports_weekly_monthly",
            "reports_yearly",
            "reports_compare",
            "multi_club",
            "staff_roles",
            "custom_rate_plans",
            "notifications_custom",
            "data_export",
            "api_access",
            "ai_agent",
            "ai_agent_custom",
            "priority_support",
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()

    for plan in PLANS:
        conn.execute(
            sa.text(
                """
                INSERT INTO plans (code, title, price_month, price_year, limits, features, sort)
                VALUES (:code, :title, :price_month, :price_year,
                        CAST(:limits AS jsonb), CAST(:features AS jsonb), :sort)
                ON CONFLICT (code) DO UPDATE SET
                    title = EXCLUDED.title,
                    price_month = EXCLUDED.price_month,
                    price_year = EXCLUDED.price_year,
                    limits = EXCLUDED.limits,
                    features = EXCLUDED.features,
                    sort = EXCLUDED.sort
                """
            ),
            {
                **plan,
                "limits": json.dumps(plan["limits"]),
                "features": json.dumps(plan["features"]),
            },
        )

    # Super adminlar — env'dagi telegram_id lar bo'yicha
    raw = os.environ.get("SUPER_ADMIN_TELEGRAM_IDS", "").strip()
    if not raw:
        return

    for part in raw.split(","):
        telegram_id = part.strip()
        if not telegram_id:
            continue

        conn.execute(
            sa.text(
                """
                INSERT INTO users (telegram_id, first_name)
                VALUES (:telegram_id, 'Super admin')
                ON CONFLICT (telegram_id) DO NOTHING
                """
            ),
            {"telegram_id": int(telegram_id)},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO super_admins (user_id, note)
                SELECT id, 'seed' FROM users WHERE telegram_id = :telegram_id
                ON CONFLICT (user_id) DO NOTHING
                """
            ),
            {"telegram_id": int(telegram_id)},
        )


def downgrade() -> None:
    raise NotImplementedError("PlayBron migratsiyalari faqat oldinga")
