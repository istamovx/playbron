"""Platforma paneli — super admin uchun cross-tenant statistika.

Manba: `api/migrations/versions/0015_platform_stats.py`. Sessiya
`deps.py::platform_db` orqali keladi — `SET LOCAL app.platform='true'`
allaqachon o'rnatilgan, shu yerda qo'shimcha GUC kerak emas.

**Ikki tushum aralashmaydi** (`docs/06-super-admin.md` §5.1): bu yerdagi
"tushum" — klublarning bron summasi, PLATFORMANING o'zi hali obuna/to'lov
tizimiga ega emas (`subscriptions`/`platform_payments` jadvallari yo'q).
Shuning uchun frontend'da bu maydon albatta "Klublar aylanmasi — platforma
tushumi emas" deb yorliqlanishi kerak.
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

TREND_DAYS = 14
TOP_CLUBS_LIMIT = 5
TOP_CLUBS_WINDOW_DAYS = 30
TZ = "Asia/Tashkent"


async def get_dashboard(session: AsyncSession) -> dict[str, Any]:
    orgs_total = await session.scalar(text("SELECT count(*) FROM organizations"))
    clubs_active = await session.scalar(
        text("SELECT count(*) FROM clubs WHERE status = 'active'")
    )
    clubs_draft = await session.scalar(text("SELECT count(*) FROM clubs WHERE status = 'draft'"))

    today = (
        await session.execute(
            text(
                "SELECT count(*), COALESCE(SUM(rate_snapshot * hours), 0)"
                " FROM bookings"
                " WHERE status = 'CONFIRMED'"
                "   AND (lower(period) AT TIME ZONE :tz)::date = (now() AT TIME ZONE :tz)::date"
            ),
            {"tz": TZ},
        )
    ).one()

    month = (
        await session.execute(
            text(
                "SELECT count(*), COALESCE(SUM(rate_snapshot * hours), 0)"
                " FROM bookings"
                " WHERE status = 'CONFIRMED'"
                "   AND date_trunc('month', lower(period) AT TIME ZONE :tz)"
                "     = date_trunc('month', now() AT TIME ZONE :tz)"
            ),
            {"tz": TZ},
        )
    ).one()

    trend_rows = (
        await session.execute(
            text(
                "SELECT (lower(period) AT TIME ZONE :tz)::date AS day, count(*) AS n"
                " FROM bookings"
                " WHERE status = 'CONFIRMED'"
                "   AND lower(period) >= now() - (:days * interval '1 day')"
                " GROUP BY 1 ORDER BY 1"
            ),
            {"tz": TZ, "days": TREND_DAYS},
        )
    ).all()
    trend_by_day = {row.day.isoformat(): row.n for row in trend_rows}

    top_rows = (
        await session.execute(
            text(
                "SELECT c.id, c.name, o.name AS org_name, count(b.id) AS bookings"
                " FROM bookings b"
                " JOIN clubs c ON c.id = b.club_id"
                " JOIN organizations o ON o.id = c.org_id"
                " WHERE b.status = 'CONFIRMED'"
                "   AND lower(b.period) >= now() - (:days * interval '1 day')"
                " GROUP BY c.id, c.name, o.name"
                " ORDER BY bookings DESC, c.name"
                " LIMIT :limit"
            ),
            {"days": TOP_CLUBS_WINDOW_DAYS, "limit": TOP_CLUBS_LIMIT},
        )
    ).all()

    return {
        "organizations_total": int(orgs_total or 0),
        "clubs_active": int(clubs_active or 0),
        "clubs_draft": int(clubs_draft or 0),
        "bookings_today": int(today[0] or 0),
        "revenue_today": int(today[1] or 0),
        "bookings_this_month": int(month[0] or 0),
        "revenue_this_month": int(month[1] or 0),
        "daily_trend": trend_by_day,
        "top_clubs": [
            {
                "club_id": row.id,
                "club_name": row.name,
                "org_name": row.org_name,
                "bookings": row.bookings,
            }
            for row in top_rows
        ],
    }
