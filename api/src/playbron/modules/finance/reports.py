"""Boshqaruv paneli va hisobot — klub darajasidagi REAL agregatsiya.

Manba: bookings/service.py (bookings), pos (orders/stations), finance
(expenses, shifts) — hammasi allaqachon REAL, yangi migratsiya kerak
emas. Reja #27 (2026-08-16, loyiha egasi): `dashboard.tsx`/`reports.tsx`
to'liq `useClub()` mock do'konidan edi — "hech qayerda seed qolmasin,
hamma rol 0 dan boshlansin" talabi.

Narx/kirim ustuni yo'q bo'lgani uchun (reja #21 hali qurilmagan) BAR
FOYDASI hisoblanmaydi — faqat TUSHUM (haqiqiy `orders.total`). Xona
`floor` ustuni yo'qligi uchun (reja #19) qavat bo'yicha guruhlash o'rniga
tekis stansiya ro'yxati qaytariladi.
"""

from datetime import date, datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Klub `timezone` ustuni bo'sh bo'lsa ishlatiladigan zaxira qiymat.
# To'g'ridan-to'g'ri ISHLATILMAYDI — `_club_timezone()` orqali.
TZ = "Asia/Tashkent"
Period = Literal["day", "week", "month", "year"]
PERIOD_UNIT: dict[Period, str] = {"day": "day", "week": "week", "month": "month", "year": "year"}


async def _club_timezone(session: AsyncSession, club_id: int) -> str:
    """Hisobot kun chegarasi KLUB zonasida chiziladi.

    Ilgari butun fayl modul darajasidagi `TZ` konstantasiga
    tayanardi. Endi shu oyna `payments` bo'yicha PUL hisobiga ham tegadi —
    boshqa zonadagi klubda kechki to'lovlar noto'g'ri kunga tushardi
    (`CLAUDE.md`, «Vaqt»).
    """
    row = await session.scalar(
        text("SELECT timezone FROM clubs WHERE id = :id"), {"id": club_id}
    )
    return str(row or TZ)


async def _club_hours(session: AsyncSession, club_id: int) -> tuple[int, int]:
    row = (
        await session.execute(
            text("SELECT opens_at_min, closes_at_min FROM clubs WHERE id = :id"), {"id": club_id}
        )
    ).first()
    if row is None:
        return 600, 1560
    return int(row.opens_at_min), int(row.closes_at_min)


def _open_minutes_per_day(opens_at_min: int, closes_at_min: int) -> int:
    span = closes_at_min - opens_at_min
    return span if span > 0 else span + 1440


async def _revenue_expense_for_range(
    session: AsyncSession,
    *,
    club_id: int,
    since: datetime,
    until: datetime,
    since_date: date,
    until_date: date,
) -> dict[str, Any]:
    """`since`/`until` — timestamptz oralig'i (`bookings.period`/`orders.
    created_at` uchun). `since_date`/`until_date` — ALOHIDA, Asia/Tashkent
    taqvim sanasi (`expenses.spent_on` — timestamptz EMAS, xom sana ustuni,
    UTC'dagi timestamp'dan `.date()` bilan chiqarib olinsa noto'g'ri kun
    chiqadi — Tashkent yarim tunidan oldingi UTC soatlarda bir kun orqada
    qoladi). Chaqiruvchi ikkalasini ham SQL orqali, bir xil `AT TIME ZONE`
    bilan hisoblaydi — shu yerda ORQAGA HISOBLANMAYDI."""
    play = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(rate_snapshot * hours), 0) AS amount, count(*) AS sessions,"
                "       COALESCE(SUM(hours), 0) AS hours"
                " FROM bookings"
                " WHERE club_id = :club_id AND status = 'CONFIRMED'"
                "   AND lower(period) >= :since AND lower(period) < :until"
            ),
            {"club_id": club_id, "since": since, "until": until},
        )
    ).one()

    bar = (
        await session.execute(
            text(
                # `CANCELLED` — bekor qilingan buyurtma TUSHUM EMAS
                # (`0028_stock_and_order_cancel.py`). Filtrsiz u "Bugungi
                # tushum"/"Bar savdosi"da qolib ketardi.
                "SELECT COALESCE(SUM(total), 0) FROM orders"
                " WHERE club_id = :club_id AND status <> 'CANCELLED'"
                "   AND created_at >= :since AND created_at < :until"
            ),
            {"club_id": club_id, "since": since, "until": until},
        )
    ).scalar_one()

    expenses = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(amount), 0) FROM expenses"
                " WHERE club_id = :club_id AND status = 'active'"
                "   AND spent_on >= :since_date AND spent_on < :until_date"
            ),
            {"club_id": club_id, "since_date": since_date, "until_date": until_date},
        )
    ).scalar_one()

    # HAQIQATAN OLINGAN pul — `payments` bo'yicha. Yuqoridagi `play`/`bar`
    # REJALASHTIRILGAN summa: `play` bron jadvalidan (mijoz kelmasa ham
    # sanaladi), `bar` esa buyurtma yaratilgan payt bo'yicha. Ikkalasi bir
    # xil son bermaydi va ilgari faqat rejalashtirilgani "daromad" deb
    # ko'rsatilardi (`docs/audit-report.md` §2.3, loyiha egasining qarori
    # 2026-08-17: ikkalasi ham kerak, alohida).
    received = (
        await session.execute(
            text(
                "SELECT COALESCE(SUM(CASE WHEN kind = 'REFUND' THEN -amount ELSE amount END), 0)"
                " FROM payments"
                " WHERE club_id = :club_id AND created_at >= :since AND created_at < :until"
            ),
            {"club_id": club_id, "since": since, "until": until},
        )
    ).scalar_one()

    return {
        "play": int(play.amount),
        "bar": int(bar),
        "sessions": int(play.sessions),
        "hours": int(play.hours),
        "expenses": int(expenses),
        "received": int(received),
    }


async def _station_count(session: AsyncSession, club_id: int) -> int:
    return int(
        (
            await session.execute(
                text(
                    "SELECT count(*) FROM stations WHERE club_id = :club_id AND status = 'active'"
                ),
                {"club_id": club_id},
            )
        ).scalar_one()
        or 0
    )


def _occupancy_percent(
    hours_booked: int, station_count: int, open_minutes_per_day: int, days: float
) -> int:
    if station_count <= 0 or open_minutes_per_day <= 0 or days <= 0:
        return 0
    capacity_hours = station_count * (open_minutes_per_day / 60) * days
    if capacity_hours <= 0:
        return 0
    return min(100, round((hours_booked / capacity_hours) * 100))


async def get_dashboard(session: AsyncSession, club_id: int) -> dict[str, Any]:
    """"Boshqaruv paneli" — bugungi real ko'rsatkichlar."""
    opens_at_min, closes_at_min = await _club_hours(session, club_id)
    open_minutes = _open_minutes_per_day(opens_at_min, closes_at_min)

    today_range = (
        await session.execute(
            text(
                "SELECT (now() AT TIME ZONE :tz)::date AS today,"
                "       ((now() AT TIME ZONE :tz)::date) AT TIME ZONE :tz AS since_utc,"
                "       (((now() AT TIME ZONE :tz)::date) + 1) AT TIME ZONE :tz AS until_utc,"
                "       ((now() AT TIME ZONE :tz)::date) + 1 AS until_date"
            ),
            {"tz": await _club_timezone(session, club_id)},
        )
    ).one()

    totals = await _revenue_expense_for_range(
        session,
        club_id=club_id,
        since=today_range.since_utc,
        until=today_range.until_utc,
        since_date=today_range.today,
        until_date=today_range.until_date,
    )
    station_count = await _station_count(session, club_id)
    occupancy = _occupancy_percent(totals["hours"], station_count, open_minutes, 1)

    hourly_rows = (
        await session.execute(
            text(
                "SELECT EXTRACT(HOUR FROM lower(period) AT TIME ZONE :tz)::int AS hour,"
                "       count(*) AS n"
                " FROM bookings"
                " WHERE club_id = :club_id AND status = 'CONFIRMED'"
                "   AND lower(period) >= :since AND lower(period) < :until"
                " GROUP BY 1"
            ),
            {
                "tz": await _club_timezone(session, club_id),
                "club_id": club_id,
                "since": today_range.since_utc,
                "until": today_range.until_utc,
            },
        )
    ).all()
    by_hour = {int(r.hour): int(r.n) for r in hourly_rows}

    stations = (
        await session.execute(
            text(
                "SELECT s.id, s.code, s.room_label,"
                "       COALESCE(b.console_type, s.console_type) AS console_type,"
                "       s.status, (b.id IS NOT NULL) AS occupied"
                " FROM stations s"
                " LEFT JOIN bookings b ON b.station_id = s.id AND b.status = 'CONFIRMED'"
                "   AND b.period @> now() AND b.closed_at IS NULL"
                " WHERE s.club_id = :club_id ORDER BY s.code"
            ),
            {"club_id": club_id},
        )
    ).all()

    # `planned` — bugun rejalashtirilgan (bron + buyurtma summasi).
    # `received` — bugun kassaga/hisobga HAQIQATAN tushgan pul.
    # Foyda OLINGAN puldan hisoblanadi: rejadan hisoblansa kelmagan
    # mijozning puli ham foydaga qo'shilib ketardi.
    planned_today = totals["play"] + totals["bar"]
    received_today = totals["received"]
    return {
        "planned_revenue_today": planned_today,
        "received_revenue_today": received_today,
        # `revenue_today` — eski nom, OLINGAN pulni bildiradi. Ilgari u
        # rejani ko'rsatib turgan, `profit_today` esa olingan puldan
        # hisoblangan edi: panelda `tushum − xarajat != foyda` chiqardi
        # va marja ikki xil bazani aralashtirardi.
        "revenue_today": received_today,
        "expenses_today": totals["expenses"],
        "profit_today": received_today - totals["expenses"],
        "sessions_today": totals["sessions"],
        "hours_today": totals["hours"],
        "occupancy_today": occupancy,
        "bar_revenue_today": totals["bar"],
        "opens_at_min": opens_at_min,
        "closes_at_min": closes_at_min,
        "hourly": by_hour,
        "stations": [
            {
                "id": r.id,
                "code": r.code,
                "room_label": r.room_label,
                "console_type": r.console_type,
                "status": r.status,
                "occupied": bool(r.occupied),
            }
            for r in stations
        ],
    }


_SUB_UNIT: dict[Period, str] = {"day": "hour", "week": "day", "month": "day", "year": "month"}


async def _revenue_series(
    session: AsyncSession, *, club_id: int, period: Period, since: datetime, until: datetime
) -> list[dict[str, Any]]:
    """Davr ichidagi tushum trendi — grafik uchun (`ActivityBars`, endi
    `LineChart` EMAS — loyiha egasining topilmasi, 2026-08-16). Bo'sh
    chelaklar HAM qaytadi (`generate_series`) — aks holda grafik
    ma'lumot bo'lgan kunlargina ko'rsatib, chalg'ituvchi bo'lardi.

    `sub_unit` — `_SUB_UNIT`dagi qat'iy TO'RTTA qiymatdan biri (foydalanuvchi
    kiritmaydi), shuning uchun f-string bilan qo'shilishi SQL in'ektsiya
    xavfi emas (`platform/service.py::get_financial_report`dagi bilan bir
    xil naqsh)."""
    # `sub_unit` — `_SUB_UNIT`dagi qat'iy TO'RTTA qiymatdan biri (foydalanuvchi
    # kiritmaydi), lekin baribir SQL matniga TIKILMAYDI: `date_trunc`ning
    # birligi bog'lanish parametri sifatida (`:unit`) o'tadi, `interval`
    # birligi esa matn ulanib keyin `::interval`ga o'giriladi
    # (`platform/service.py::get_financial_report`dagi bilan bir xil naqsh).
    sub_unit = _SUB_UNIT[period]
    rows = (
        await session.execute(
            text(
                """
                WITH buckets AS (
                    SELECT generate_series(
                        date_trunc(:unit, :since AT TIME ZONE :tz),
                        date_trunc(:unit, :until AT TIME ZONE :tz),
                        CAST('1 ' || :unit AS text)::interval
                    ) AS bucket_local
                ),
                play AS (
                    SELECT date_trunc(:unit, lower(period) AT TIME ZONE :tz) AS bucket_local,
                           SUM(rate_snapshot * hours) AS amount
                    FROM bookings
                    WHERE club_id = :club_id AND status = 'CONFIRMED'
                      AND lower(period) >= :since AND lower(period) < :until
                    GROUP BY 1
                ),
                bar AS (
                    SELECT date_trunc(:unit, created_at AT TIME ZONE :tz) AS bucket_local,
                           SUM(total) AS amount
                    FROM orders
                    WHERE club_id = :club_id AND status <> 'CANCELLED'
                      AND created_at >= :since AND created_at < :until
                    GROUP BY 1
                )
                SELECT b.bucket_local, COALESCE(p.amount, 0) + COALESCE(o.amount, 0) AS amount
                FROM buckets b
                LEFT JOIN play p ON p.bucket_local = b.bucket_local
                LEFT JOIN bar o ON o.bucket_local = b.bucket_local
                ORDER BY b.bucket_local
                """
            ),
            {
                "unit": sub_unit,
                "tz": await _club_timezone(session, club_id),
                "club_id": club_id,
                "since": since,
                "until": until,
            },
        )
    ).all()
    return [{"bucket": r.bucket_local.isoformat(), "amount": int(r.amount)} for r in rows]


async def get_report(session: AsyncSession, *, club_id: int, period: Period) -> dict[str, Any]:
    unit = PERIOD_UNIT[period]
    opens_at_min, closes_at_min = await _club_hours(session, club_id)
    open_minutes = _open_minutes_per_day(opens_at_min, closes_at_min)

    bounds = (
        await session.execute(
            text(
                "SELECT date_trunc(:unit, now() AT TIME ZONE :tz) AT TIME ZONE :tz AS since_utc,"
                "       now() AS until_utc,"
                "       (date_trunc(:unit, now() AT TIME ZONE :tz))::date AS since_date,"
                "       ((now() AT TIME ZONE :tz)::date) + 1 AS until_date,"
                "       EXTRACT(EPOCH FROM (now() - (date_trunc(:unit, now() AT TIME ZONE :tz)"
                "         AT TIME ZONE :tz))) / 86400 AS days_elapsed"
            ),
            {"unit": unit, "tz": await _club_timezone(session, club_id)},
        )
    ).one()
    days_elapsed = max(float(bounds.days_elapsed), 1 / 24)

    totals = await _revenue_expense_for_range(
        session,
        club_id=club_id,
        since=bounds.since_utc,
        until=bounds.until_utc,
        since_date=bounds.since_date,
        until_date=bounds.until_date,
    )
    station_count = await _station_count(session, club_id)
    occupancy = _occupancy_percent(totals["hours"], station_count, open_minutes, days_elapsed)

    top_products = (
        await session.execute(
            text(
                "SELECT oi.product_name,"
                "       SUM(oi.qty * oi.price_snapshot) AS revenue"
                " FROM order_items oi JOIN orders o ON o.id = oi.order_id"
                " WHERE oi.club_id = :club_id AND o.status <> 'CANCELLED'"
                "   AND o.created_at >= :since AND o.created_at < :until"
                " GROUP BY oi.product_name ORDER BY revenue DESC LIMIT 5"
            ),
            {"club_id": club_id, "since": bounds.since_utc, "until": bounds.until_utc},
        )
    ).all()

    expense_cats = (
        await session.execute(
            text(
                "SELECT category, COALESCE(SUM(amount), 0) AS amount FROM expenses"
                " WHERE club_id = :club_id AND status = 'active'"
                "   AND spent_on >= :since_date AND spent_on < :until_date"
                " GROUP BY category ORDER BY amount DESC"
            ),
            {"club_id": club_id, "since_date": bounds.since_date, "until_date": bounds.until_date},
        )
    ).all()

    series = await _revenue_series(
        session, club_id=club_id, period=period, since=bounds.since_utc, until=bounds.until_utc
    )

    # `get_dashboard()` bilan bir xil ta'rif: reja va olingan pul alohida.
    planned = totals["play"] + totals["bar"]
    received = totals["received"]
    # `revenue` — `profit` bilan BIR XIL baza (olingan pul). Reja alohida
    # `planned_revenue` da.
    revenue = received
    return {
        "period": period,
        "revenue": revenue,
        "expenses": totals["expenses"],
        "planned_revenue": planned,
        "received_revenue": received,
        "profit": received - totals["expenses"],
        "play_revenue": totals["play"],
        "bar_revenue": totals["bar"],
        "sessions": totals["sessions"],
        "hours": totals["hours"],
        "occupancy": occupancy,
        "station_count": station_count,
        "top_products": [
            {"product_name": r.product_name, "revenue": int(r.revenue)} for r in top_products
        ],
        "expense_by_category": [
            {"category": r.category, "amount": int(r.amount)} for r in expense_cats
        ],
        "revenue_series": series,
    }
