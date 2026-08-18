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

from playbron.core.audit import log_action
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
                "SELECT count(*), COALESCE(SUM(play_amount), 0)"
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
                "SELECT count(*), COALESCE(SUM(play_amount), 0)"
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


async def get_organization_detail(session: AsyncSession, *, org_id: int) -> dict[str, Any]:
    """Bitta tashkilot — "Ko'rish" (Preview): klublar ro'yxati (bittadan
    ko'p bo'lishi mumkin), TO'LIQ to'lov tarixi (`list_organizations`dagi
    kabi faqat so'nggisi emas) va xodimlar ro'yxati (`memberships`,
    barcha klublari bo'yicha birlashtirilgan).

    `users.phone`/`telegram_id` `playbron_platform`ga REVOKE qilingan
    (`0016_platform_org_admin.py`) — ega/xodim uchun faqat ism/login
    qaytariladi, telefon YO'Q.
    """
    org = (
        await session.execute(
            text(
                "SELECT o.id, o.name, o.status, o.plan_code, o.created_at,"
                "       u.first_name AS owner_name, u.login AS owner_login"
                " FROM organizations o JOIN users u ON u.id = o.owner_user_id"
                " WHERE o.id = :org"
            ),
            {"org": org_id},
        )
    ).first()
    if org is None:
        raise NotFound("Tashkilot topilmadi")

    clubs = (
        await session.execute(
            text(
                "SELECT c.id, c.name, c.status, c.address, c.phone,"
                "       (SELECT count(*) FROM stations s WHERE s.club_id = c.id) AS stations_count,"
                "       (SELECT count(*) FROM bookings b"
                "          WHERE b.club_id = c.id AND b.status = 'CONFIRMED'"
                "            AND lower(b.period) >= now() - interval '30 days') AS bookings_30d"
                " FROM clubs c WHERE c.org_id = :org ORDER BY c.created_at"
            ),
            {"org": org_id},
        )
    ).all()

    payments = (
        await session.execute(
            text(
                "SELECT pp.id, pp.amount, pp.plan_code, pp.period_months, pp.paid_at, pp.note,"
                "       u.first_name AS entered_by_name"
                " FROM platform_payments pp LEFT JOIN users u ON u.id = pp.entered_by"
                " WHERE pp.org_id = :org ORDER BY pp.paid_at DESC"
            ),
            {"org": org_id},
        )
    ).all()

    staff = (
        await session.execute(
            text(
                "SELECT m.user_id, u.first_name, u.login, m.role, m.club_id, c.name AS club_name"
                " FROM memberships m"
                " JOIN users u ON u.id = m.user_id"
                " JOIN clubs c ON c.id = m.club_id"
                " WHERE c.org_id = :org AND m.status = 'active'"
                " ORDER BY c.name, m.role, u.first_name"
            ),
            {"org": org_id},
        )
    ).all()

    return {
        "org_id": org.id,
        "org_name": org.name,
        "org_status": org.status,
        "plan_code": org.plan_code,
        "created_at": org.created_at.isoformat(),
        "owner_name": org.owner_name,
        "owner_login": org.owner_login,
        "clubs": [
            {
                "club_id": row.id,
                "club_name": row.name,
                "club_status": row.status,
                "address": row.address,
                "phone": row.phone,
                "stations_count": int(row.stations_count or 0),
                "bookings_30d": int(row.bookings_30d or 0),
            }
            for row in clubs
        ],
        "payments": [
            {
                "id": row.id,
                "amount": row.amount,
                "plan_code": row.plan_code,
                "period_months": row.period_months,
                "paid_at": row.paid_at.isoformat(),
                "note": row.note,
                "entered_by_name": row.entered_by_name,
            }
            for row in payments
        ],
        "staff": [
            {
                "user_id": row.user_id,
                "first_name": row.first_name,
                "login": row.login,
                "role": row.role,
                "club_id": row.club_id,
                "club_name": row.club_name,
            }
            for row in staff
        ],
    }


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
    await log_action(
        action="platform_manual_org_create",
        target=login,
        after={"login": login, "club_name": body.get("club_name")},
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

    await log_action(
        action="platform_payment_record",
        target=str(org_id),
        org_id=org_id,
        after={"amount": amount, "plan_code": plan_code, "period_months": period_months},
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


async def update_organization(
    session: AsyncSession, *, org_id: int, name: str | None, status: str | None
) -> dict[str, Any]:
    """Tashkilot nomi/holatini tahrirlash — `record_payment()`dagi
    `plan_code` yozuvidan ATAYLAB alohida yo'l (audit topilmasi,
    2026-08-16, reja #16): to'lov qayd etilganda tarif yangilanishi bilan
    super adminning qo'lda nom/holat tahriri bir joyda aralashmasin — ikki
    mustaqil sabab bitta UPDATE ichida yashirinmasin.

    `organizations_platform_write` policy'si (`0017_platform_org_plan.py`)
    ustunga xos EMAS — `app_platform()` bo'lsa istalgan ustunni yangilashga
    ruxsat beradi, shuning uchun bu yerga yangi migratsiya kerak emas.

    `status='suspended'` — real ta'sirga ega (reja #43, 2026-08-16):
    `auth/staff.py::staff_login()` `org_active_for_user()` (`0026`) orqali
    tekshiradi — foydalanuvchining BARCHA tashkilotlari to'xtatilgan bo'lsa
    kirish `403 ORG_SUSPENDED` bilan rad etiladi (super admin va a'zoligi
    yo'q hisoblar bundan mustasno). `plan_code` limitlari hali cheklanmaydi
    (spec §4.3dagi to'liq TOTP+`subscriptions`+`glass_sessions` oqimi hali
    qurilmagan).
    """
    if name is None and status is None:
        raise AppError("Kamida bitta maydon kiritilsin", code="NO_FIELDS")

    row = (
        await session.execute(
            text(
                "UPDATE organizations"
                " SET name = COALESCE(:name, name), status = COALESCE(:status, status)"
                " WHERE id = :org"
                " RETURNING id, name, status"
            ),
            {"name": name, "status": status, "org": org_id},
        )
    ).first()
    if row is None:
        raise NotFound("Tashkilot topilmadi")

    # To'xtatish DARHOL amal qilishi kerak. `0026` faqat YANGI kirishni
    # bloklaydi — allaqachon kirgan xodim refresh rotatsiyasi bilan
    # sessiyani cheksiz uzaytirardi (audit topilmasi, 2026-08-16), ya'ni
    # UI'dagi "saqlangach darhol amal qiladi" va'dasi yolg'on edi.
    revoked = 0
    if status == "suspended":
        revoked = int(
            await session.scalar(
                text("SELECT platform_revoke_org_sessions(:org)"), {"org": org_id}
            )
            or 0
        )

    await log_action(
        action="platform_org_update",
        target=row.name,
        org_id=org_id,
        after={"name": row.name, "status": row.status, "revoked_sessions": revoked},
    )

    return {
        "org_id": row.id,
        "org_name": row.name,
        "org_status": row.status,
        "revoked_sessions": revoked,
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


async def list_platform_logs(session: AsyncSession, *, limit: int) -> list[dict[str, Any]]:
    """Platforma darajasidagi amallar — `club_id IS NULL` qatorlar
    (tashkilot yaratish, to'lov yozish). Bitta klub ICHIDAGI amallar
    (xodim/mahsulot/xona) BU YERDA emas — ular klub egasi/adminining
    o'z jurnalida (`staff/router.py::list_club_logs`), "o'ziga hos
    loglar" talabini shu ikkiga ajratish bilan qanoatlantiradi
    (loyiha egasining so'rovi, 2026-08-16).

    `audit_log_platform_read` policy'si (`0018_platform_log_read.py`)
    shart — undan oldin `app_platform()` uchun o'qish policy'si yo'q
    edi, GRANT bor bo'lsa ham (`[[playbron-grant-vs-rls-blind-spot]]`).
    """
    rows = (
        await session.execute(
            text(
                "SELECT a.id, a.at, a.action, a.target, a.org_id,"
                "       u.first_name AS actor_name, u.login AS actor_login, a.after"
                " FROM audit_log a LEFT JOIN users u ON u.id = a.actor_user_id"
                " WHERE a.club_id IS NULL"
                " ORDER BY a.at DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
    ).all()
    return [
        {
            "id": f"audit:{row.id}",
            "at": row.at.isoformat(),
            "action": row.action,
            "target": row.target,
            "org_id": row.org_id,
            "actor_name": row.actor_name,
            "actor_login": row.actor_login,
            "detail": row.after,
        }
        for row in rows
    ]
