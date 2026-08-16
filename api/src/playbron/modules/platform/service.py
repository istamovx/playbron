"""Platforma paneli — super admin uchun cross-tenant statistika.

Manba: `api/migrations/versions/0015_platform_stats.py`,
`0016_platform_org_admin.py`. O'qish sessiyasi `deps.py::platform_db`
orqali keladi — `SET LOCAL app.platform='true'` allaqachon o'rnatilgan;
yozish (`platform_payments`) — `platform_write_db` orqali.

**Ikki tushum aralashmaydi** (`docs/06-super-admin.md` §5.1): "Boshqaruv
paneli"dagi (`get_dashboard`) tushum — klublarning bron summasi.
"Hisobot"dagi (`get_financial_report`) tushum esa `platform_payments` —
PLATFORMANING o'zi qo'lda kiritgan to'lovlari. Ikkalasi frontend'da
alohida bo'lim, alohida yorliq bilan qoladi.
"""

from datetime import datetime
from typing import Any, Literal

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.errors import AppError, NotFound
from playbron.core.http import client_ip
from playbron.modules.auth import signup

TREND_DAYS = 14
TOP_CLUBS_LIMIT = 5
TOP_CLUBS_WINDOW_DAYS = 30
TZ = "Asia/Tashkent"

Period = Literal["day", "week", "month", "year"]

# davr -> (date_trunc birligi, interval birligi, orqaga qarash soni)
PERIOD_UNITS: dict[Period, tuple[str, str, int]] = {
    "day": ("day", "day", 30),
    "week": ("week", "week", 12),
    "month": ("month", "month", 12),
    "year": ("year", "year", 5),
}


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


async def list_organizations(session: AsyncSession) -> list[dict[str, Any]]:
    """Barcha klublar, tashkiloti va egasi bilan — "Klublar" bo'limi.

    `LEFT JOIN clubs`: yangi ro'yxatdan o'tgan tashkilotda hali klub
    bo'lmasligi mumkin emas aslida (`auth_owner_signup` ikkalasini birga
    yaratadi), lekin himoya sifatida qoldiriladi — bittasi buzilib
    qolsa butun ro'yxat yo'qolmaydi.

    `LEFT JOIN LATERAL platform_payments` — so'nggi to'lov qatori.
    "Amal qilish muddati" alohida ustun sifatida saqlanmaydi, shu
    yerda `paid_at + period_months` sifatida hisoblanadi (`0017`).
    """
    rows = (
        await session.execute(
            text(
                "SELECT o.id AS org_id, o.name AS org_name, o.status AS org_status,"
                "       o.plan_code, o.created_at,"
                "       u.first_name AS owner_name, u.login AS owner_login,"
                "       c.id AS club_id, c.name AS club_name, c.status AS club_status,"
                "       (SELECT count(*) FROM stations s WHERE s.club_id = c.id) AS stations_count,"
                "       (SELECT count(*) FROM bookings b"
                "          WHERE b.club_id = c.id AND b.status = 'CONFIRMED'"
                "            AND lower(b.period) >= now() - interval '30 days') AS bookings_30d,"
                "       lp.amount AS last_payment_amount, lp.paid_at AS last_payment_at,"
                "       CASE WHEN lp.period_months IS NOT NULL"
                "            THEN lp.paid_at + (lp.period_months * interval '1 month')"
                "            ELSE NULL END AS plan_expires_at"
                " FROM organizations o"
                " JOIN users u ON u.id = o.owner_user_id"
                " LEFT JOIN clubs c ON c.org_id = o.id"
                " LEFT JOIN LATERAL ("
                "     SELECT amount, paid_at, period_months FROM platform_payments pp"
                "      WHERE pp.org_id = o.id ORDER BY pp.paid_at DESC LIMIT 1"
                " ) lp ON true"
                " ORDER BY o.created_at DESC"
            )
        )
    ).all()
    return [
        {
            "org_id": row.org_id,
            "org_name": row.org_name,
            "org_status": row.org_status,
            "plan_code": row.plan_code,
            "created_at": row.created_at.isoformat(),
            "owner_name": row.owner_name,
            "owner_login": row.owner_login,
            "club_id": row.club_id,
            "club_name": row.club_name,
            "club_status": row.club_status,
            "stations_count": int(row.stations_count or 0),
            "bookings_30d": int(row.bookings_30d or 0),
            "last_payment_amount": row.last_payment_amount,
            "last_payment_at": row.last_payment_at.isoformat() if row.last_payment_at else None,
            "plan_expires_at": row.plan_expires_at.isoformat() if row.plan_expires_at else None,
        }
        for row in rows
    ]


async def create_manual_org(
    session: AsyncSession, *, body: dict[str, Any], request: Request, actor_user_id: int
) -> str:
    """Super admin klubni qo'lda qo'shadi — to'lov tizimida muammo bo'lganda

    yoki mijoz o'zi ro'yxatdan o'tolmasa. **YANGI yo'l emas** — xuddi ochiq
    `POST /auth/owner/signup` ishlatgan `signup.owner_signup()`ning o'zi
    (`0008_owner_signup.py`): parol tekshiruvi, login band tekshiruvi,
    IP chegarasi — hammasi bir xil. Farqi — bu yerga faqat super admin
    yetadi (`require_super_admin`), ochiq emas.
    """
    login = await signup.owner_signup(session, body=body, ip=client_ip(request))
    await session.execute(
        text(
            "INSERT INTO auth_events (event, user_id, detail)"
            " VALUES ('platform_manual_org_create', :uid,"
            "         jsonb_build_object('login', CAST(:login AS text)))"
        ),
        {"uid": actor_user_id, "login": login},
    )
    return login


async def record_payment(
    session: AsyncSession,
    *,
    org_id: int,
    amount: int,
    plan_code: str | None,
    period_months: int | None,
    note: str | None,
    entered_by: int,
) -> dict[str, Any]:
    if amount <= 0:
        raise AppError("Summa musbat bo'lsin", code="AMOUNT_INVALID")

    org_exists = await session.scalar(
        text("SELECT 1 FROM organizations WHERE id = :o"), {"o": org_id}
    )
    if not org_exists:
        raise NotFound("Tashkilot topilmadi")

    row = (
        await session.execute(
            text(
                "INSERT INTO platform_payments"
                " (org_id, amount, plan_code, period_months, note, entered_by)"
                " VALUES (:org, :amount, :plan, :months, :note, :by)"
                " RETURNING id, org_id, amount, plan_code, period_months, paid_at, note"
            ),
            {
                "org": org_id,
                "amount": amount,
                "plan": plan_code,
                "months": period_months,
                "note": note,
                "by": entered_by,
            },
        )
    ).one()

    # Tarif tanlangan bo'lsa — tashkilotning joriy tarifi ham yangilanadi
    # ("Klublar" jadvalidagi TARIF ustuni). `organizations_platform_write`
    # policy'si (`0017`) shu yozuvga ruxsat beradi — GRANT `0001`dan bor edi,
    # RLS yetishmayotgan edi.
    if plan_code is not None:
        await session.execute(
            text("UPDATE organizations SET plan_code = :plan WHERE id = :org"),
            {"plan": plan_code, "org": org_id},
        )

    return {
        "id": row.id,
        "org_id": row.org_id,
        "amount": row.amount,
        "plan_code": row.plan_code,
        "period_months": row.period_months,
        "paid_at": row.paid_at.isoformat(),
        "note": row.note,
    }


def _bucket_key(value: datetime) -> str:
    return value.date().isoformat()


async def get_financial_report(session: AsyncSession, *, period: Period) -> dict[str, Any]:
    """"Hisobot" — kunlik/haftalik/oylik/yillik kesim.

    Ikki qator: `platform_payments`dan yig'ilgan tushum (bizning pulimiz)
    va `organizations`ga qo'shilgan yangi klublar soni ("kelgan klublar").
    Ikkalasi ham `date_trunc(:unit, ...)` bilan bir xil chelaklarga
    yig'iladi — grafik ikkalasini yonma-yon ko'rsatishi mumkin.
    """
    unit, interval_unit, lookback = PERIOD_UNITS[period]
    # `interval` birligi ham parametr — `f"interval '1 {unit}'"` string
    # qo'shish orqali SQL matniga tikilmaydi (S608): son va birlik matn
    # sifatida ulanadi, keyin `::interval`ga o'giriladi. `interval_unit`
    # o'zi `PERIOD_UNITS` dagi qat'iy to'rtta qiymatdan biri — foydalanuvchi
    # kiritmaydi, lekin baribir tikilgan f-string emas, parametr.
    since = {"unit": unit, "tz": TZ, "lookback_expr": f"{lookback} {interval_unit}"}

    revenue_rows = (
        await session.execute(
            text(
                """
                SELECT date_trunc(:unit, paid_at AT TIME ZONE :tz) AS bucket,
                       COALESCE(SUM(amount), 0) AS amount
                FROM platform_payments
                WHERE paid_at >= now() - CAST(:lookback_expr AS text)::interval
                GROUP BY 1 ORDER BY 1
                """
            ),
            since,
        )
    ).all()

    orgs_rows = (
        await session.execute(
            text(
                """
                SELECT date_trunc(:unit, created_at AT TIME ZONE :tz) AS bucket,
                       count(*) AS n
                FROM organizations
                WHERE created_at >= now() - CAST(:lookback_expr AS text)::interval
                GROUP BY 1 ORDER BY 1
                """
            ),
            since,
        )
    ).all()

    total_revenue = await session.scalar(
        text("SELECT COALESCE(SUM(amount), 0) FROM platform_payments")
    )
    total_orgs = await session.scalar(text("SELECT count(*) FROM organizations"))

    return {
        "period": period,
        "revenue_by_bucket": {_bucket_key(row.bucket): int(row.amount) for row in revenue_rows},
        "new_orgs_by_bucket": {_bucket_key(row.bucket): int(row.n) for row in orgs_rows},
        "total_revenue": int(total_revenue or 0),
        "total_organizations": int(total_orgs or 0),
    }
