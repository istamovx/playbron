"""B3 fon vazifalari.

Har vazifa `run_per_club` orqali: klub kesimida alohida GUC kontekst,
alohida jurnal yozuvi, bir klub xatosi boshqasini to'xtatmaydi.
`WHERE club_id = :club` — RLS USTIGA qo'shimcha qatlam (CLAUDE.md §RLS).

Bloklangan vazifalar (brif <constraints>):
- `mark_no_show` — D-bosqichni kutadi (`CHECKED_IN` holati hali yo'q)
- `low_stock_alert` — C-bosqichni kutadi (`products.min_stock` hali yo'q)
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.worker.base import (
    club_scope,
    ensure_club_context,
    journal_finish,
    journal_start,
    run_per_club,
)
from playbron.worker.notify import queue_notification
from playbron.worker.schedule import (
    date_key,
    local_day_utc_range,
    local_hhmm,
    reminder_template,
    summary_date,
)

log = logging.getLogger("playbron.worker")

# `notify.py` dagi mijozga aytilgan «10 daqiqa» va'dasi bilan mos.
# C-bosqichda `club_settings.payment_window_min` ga ko'chadi.
PAYMENT_WINDOW_MIN = 10


def _now() -> datetime:
    """Testlar vaqtni almashtirishi uchun bitta nuqta."""
    return datetime.now(UTC)


async def expire_unpaid_bookings(ctx: dict[str, Any]) -> dict[str, int]:
    """`PENDING` bron to'lov oynasidan oshsa avto-bekor bo'ladi.

    Idempotent: bekor bo'lgan qator ikkinchi yurishda `PENDING` emas.
    `cancelled_by = NULL` — aktyor yo'q, tizim bekor qildi.
    """

    async def handler(
        session: AsyncSession, club: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | None]:
        await ensure_club_context(session)
        # `prepaid_amount = 0` to'sig'i: bugun PENDING'da pul bo'lmaydi
        # (payments faqat settle'da yoziladi), lekin ustun rejada bor —
        # oldindan to'lov kelgan kuni to'langan bronni REFUND'siz bekor
        # qilib yubormaslik uchun (pul-review topilmasi).
        rows = (
            await session.execute(
                text(
                    "UPDATE bookings SET status = 'CANCELLED', cancelled_at = now(),"
                    " cancel_reason = 'PAYMENT_WINDOW_EXPIRED'"
                    " WHERE club_id = :club AND status = 'PENDING'"
                    "   AND created_at < now() - make_interval(mins => :window)"
                    "   AND prepaid_amount = 0"
                    " RETURNING id"
                ),
                {"club": club["id"], "window": PAYMENT_WINDOW_MIN},
            )
        ).all()
        cancelled = [int(r.id) for r in rows]
        # Iz jurnalda: tizim qaysi bronlarni bekor qilgani auditsiz qolmasin
        return len(cancelled), ({"cancelled_ids": cancelled} if cancelled else None)

    return await run_per_club("expire_unpaid_bookings", handler)


async def booking_reminders(ctx: dict[str, Any]) -> dict[str, int]:
    """Tasdiqlangan bronga 2 soat va 20 daqiqa qolganda mijozga eslatma.

    Takror yuborishni `notifications_dedup_uk` to'xtatadi — shablon har
    bosqichda boshqa, shuning uchun ikkala eslatma ham bittadan boradi.
    """

    async def handler(session: AsyncSession, club: dict[str, Any]) -> int:
        await ensure_club_context(session)
        now = _now()
        rows = (
            await session.execute(
                text(
                    "SELECT b.id, b.customer_id, lower(b.period) AS starts_at,"
                    "       s.code AS station, u.telegram_id AS chat"
                    " FROM bookings b"
                    " JOIN stations s ON s.id = b.station_id"
                    " JOIN users u ON u.id = b.customer_id"
                    " WHERE b.club_id = :club AND b.status = 'CONFIRMED'"
                    "   AND b.customer_id IS NOT NULL AND u.telegram_id IS NOT NULL"
                    "   AND lower(b.period) > now()"
                    "   AND lower(b.period) <= now() + make_interval(mins => :early)"
                ),
                {"club": club["id"], "early": 120},
            )
        ).all()

        queued = 0
        for row in rows:
            minutes_left = (row.starts_at - now).total_seconds() / 60
            template = reminder_template(minutes_left)
            if template is None:
                continue
            row_id = await queue_notification(
                session,
                club_id=club["id"],
                recipient_kind="CUSTOMER",
                recipient_id=int(row.customer_id),
                chat_id=int(row.chat),
                template=template,
                entity_id=int(row.id),
                payload={
                    "club": club["name"],
                    "station": row.station,
                    "starts_at": local_hhmm(row.starts_at, club["timezone"]),
                },
            )
            if row_id is not None:
                queued += 1
        return queued

    return await run_per_club("booking_reminders", handler)


async def daily_summary(ctx: dict[str, Any]) -> dict[str, int]:
    """Klub vaqti bilan 09 da egaga kechagi kun xulosasi.

    Manba — `payments` (olingan pul), `bookings.paid_amount` EMAS
    (CLAUDE.md §Pul: hisob `payments`dan).
    """

    async def handler(session: AsyncSession, club: dict[str, Any]) -> int:
        await ensure_club_context(session)
        day = summary_date(_now(), club["timezone"])
        if day is None:
            return 0
        start, end = local_day_utc_range(day, club["timezone"])
        params = {"club": club["id"], "s": start, "e": end}

        received = int(
            await session.scalar(
                text(
                    "SELECT COALESCE(SUM(CASE WHEN kind = 'REFUND' THEN -amount"
                    "                          ELSE amount END), 0)"
                    " FROM payments WHERE club_id = :club"
                    "   AND created_at >= :s AND created_at < :e"
                ),
                params,
            )
            or 0
        )
        sessions = int(
            await session.scalar(
                text(
                    "SELECT count(*) FROM bookings WHERE club_id = :club"
                    "   AND closed_at >= :s AND closed_at < :e"
                ),
                params,
            )
            or 0
        )
        # Faqat CONFIRMED — to'lanmagan PENDING bandlikni shishirmasin
        booked_hours = int(
            await session.scalar(
                text(
                    "SELECT COALESCE(SUM(hours), 0) FROM bookings WHERE club_id = :club"
                    "   AND status = 'CONFIRMED'"
                    "   AND lower(period) >= :s AND lower(period) < :e"
                ),
                params,
            )
            or 0
        )
        stations = int(
            await session.scalar(
                text(
                    "SELECT count(*) FROM stations WHERE club_id = :club"
                    "   AND status = 'active'"
                ),
                {"club": club["id"]},
            )
            or 0
        )
        # Maxraj — klubning ISH soatlari (24 emas). Yarim tundan oshib
        # ishlaydigan klub (masalan 10:00-02:00): closes < opens — o'rab olamiz
        open_minutes = int(club["closes_at_min"]) - int(club["opens_at_min"])
        if open_minutes <= 0:
            open_minutes += 24 * 60
        open_hours = max(1, open_minutes // 60)
        occupancy = (
            min(100, round(booked_hours * 100 / (stations * open_hours))) if stations else 0
        )

        chats = (
            await session.execute(
                text("SELECT chat_id FROM owner_notify_targets(:club)"), {"club": club["id"]}
            )
        ).all()

        queued = 0
        for chat in chats:
            row_id = await queue_notification(
                session,
                club_id=club["id"],
                recipient_kind="OWNER",
                chat_id=int(chat.chat_id),
                template="daily_summary",
                entity_id=date_key(day),
                payload={
                    "club": club["name"],
                    "date": day.isoformat(),
                    "received_revenue": received,
                    "sessions": sessions,
                    "occupancy": occupancy,
                },
            )
            if row_id is not None:
                queued += 1
        return queued

    return await run_per_club("daily_summary", handler)


async def notify_shift_variance(
    ctx: dict[str, Any], club_id: int, shift_id: int, payload: dict[str, Any]
) -> int:
    """Smena katta farq bilan yopilganda egaga darhol xabar.

    API (`finance/shifts.py::close_shift`) navbatga qo'yadi — payload
    (klub nomi, farq, xodim) o'sha yerda, o'z konteksti bilan yig'ilgan.
    """
    job_id = await journal_start("shift_variance_alert", club_id=club_id)
    try:
        async with club_scope(club_id) as session:
            await ensure_club_context(session)
            chats = (
                await session.execute(
                    text("SELECT chat_id FROM owner_notify_targets(:club)"), {"club": club_id}
                )
            ).all()
            queued = 0
            for chat in chats:
                row_id = await queue_notification(
                    session,
                    club_id=club_id,
                    recipient_kind="OWNER",
                    chat_id=int(chat.chat_id),
                    template="shift_variance",
                    entity_id=shift_id,
                    payload=payload,
                )
                if row_id is not None:
                    queued += 1
    except Exception as exc:  # noqa: BLE001 — jurnalga tushsin, keyin arq qayta uradi
        await journal_finish(job_id, error=str(exc)[:500])
        raise
    await journal_finish(job_id)
    return queued


async def mark_no_show(ctx: dict[str, Any]) -> dict[str, int]:
    """D-BOSQICHGA BLOKLANGAN: `CHECKED_IN` holati hali yo'q.

    D kelgach: boshlanishidan `no_show_after_min` o'tgan, `CHECKED_IN`
    bo'lmagan `CONFIRMED` bron → `NO_SHOW`. Hozircha ro'yxatga
    QO'SHILMAGAN (docs/HOLAT.md §Fon vazifalari).
    """
    raise NotImplementedError("D-bosqichni kutadi (bron holat mashinasi)")


async def low_stock_alert(ctx: dict[str, Any]) -> dict[str, int]:
    """C-BOSQICHGA BLOKLANGAN: `products.min_stock` ustuni hali yo'q.

    C kelgach: `stock_qty < min_stock` mahsulotlar bo'yicha menejerga
    xabar. Hozircha ro'yxatga QO'SHILMAGAN (docs/HOLAT.md).
    """
    raise NotImplementedError("C-bosqichni kutadi (products.min_stock)")
