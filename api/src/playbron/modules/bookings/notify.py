"""Bron bildirishnomalari — ikki yo'nalish.

Manba: `api/migrations/versions/0009_bookings.py` — RLS asosini shu yerda
qayta tushuntirmaymiz, faqat Telegram yuborish qatlami.

Ikkalasi ham **best-effort**: xato bron oqimini to'xtatmaydi, faqat log'ga
yoziladi. Bron muvaffaqiyatli yaratilgan/tasdiqlangan bo'lsa, bildirishnoma
yetib bormasligi buni bekor qilmaydi — mijoz konsolda/ilovada baribir
ko'radi.
"""

import logging
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import telegram_api
from playbron.core.config import settings

log = logging.getLogger("playbron.bookings.notify")


def _token() -> str:
    # Mijoz botiga — u shu yerda ro'yxatdan o'tgan (`modules/bot/customer.py`)
    return settings.bot_token.get_secret_value()


def _admin_token() -> str:
    return settings.admin_bot_token.get_secret_value() or settings.bot_token.get_secret_value()


async def notify_staff_new_booking(
    session: AsyncSession,
    *,
    club_id: int,
    club_name: str,
    station_code: str,
    guest_label: str,
    starts_label: str,
    hours: int,
) -> None:
    """Yangi (PENDING) bron — klub xodimlariga.

    `booking_notify_targets` SECURITY DEFINER: chaqiruvchi (mijoz) bu
    klubda hech qanday standart huquqqa ega emas, funksiya buni o'z
    ichida hal qiladi (`0009` migratsiyasiga qara).
    """
    try:
        rows = (
            await session.execute(
                text("SELECT chat_id FROM booking_notify_targets(:club_id)"),
                {"club_id": club_id},
            )
        ).all()
    except Exception:  # noqa: BLE001
        log.warning("booking_notify_targets so'rovi muvaffaqiyatsiz", exc_info=True)
        return

    if not rows:
        # Hech kim Telegram ulamagan — kutilgan holat, xato emas
        log.info("Klub %s uchun bildirishnoma nishoni yo'q (Telegram ulanmagan)", club_id)
        return

    text_body = (
        f"🆕 Yangi bron — {club_name}\n"
        f"Xona: {station_code}\n"
        f"Mijoz: {guest_label}\n"
        f"Vaqt: {starts_label} · {hours} soat\n\n"
        "Konsolda tasdiqlang."
    )
    for (chat_id,) in rows:
        await telegram_api.send_message(_admin_token(), chat_id, text_body)


LATE_GRACE_MIN = 10


def booking_card(
    *, title: str, club_name: str, room_label: str, starts_at: Any, hours: int, timezone: str
) -> str:
    """Mijozga ketadigan bron kartochkasi — yagona shakl.

    Tasdiq va eslatma bir xil ko'rinishda bo'lishi kerak: mijoz ikkinchi
    xabarni ko'rganda uni tanishi va qidirmasligi zarur. Sana va vaqt
    ALOHIDA qatorda — telefon ekranida bitta uzun qator o'qilmaydi.
    """
    local = _to_club_time(starts_at, timezone)
    return (
        f"{title} — {club_name}\n"
        f"🎮 Xona: {room_label}\n"
        f"📆 Sana: {local:%d-%m-%Y}\n"
        f"🕔 Bron vaqti: {local:%H:%M}\n"
        f"⏳ Vaqt: {hours} soat\n"
        f"ℹ️ Iltimos, kechikmang — belgilangan vaqtdan {LATE_GRACE_MIN} daqiqa "
        "o'tsa joyingiz bo'shatilishi mumkin."
    )


async def notify_customer_confirmed(
    session: AsyncSession,
    *,
    club_id: int,
    customer_id: int,
    club_name: str,
    room_label: str,
    starts_at: Any,
    hours: int,
    timezone: str,
) -> None:
    """Xodim tasdiqladi — mijozga.

    `users_booking_contact` policy'si (0009) shu o'qishni ochadi: chaqiruvchi
    xodim, `app.club_id`/`app.club_role` to'g'ri, mijozning shu klubda FAOL
    broni bor.
    """
    await _notify_customer(
        session,
        customer_id=customer_id,
        text_body=booking_card(
            title="✅ Broningiz tasdiqlandi",
            club_name=club_name,
            room_label=room_label,
            starts_at=starts_at,
            hours=hours,
            timezone=timezone,
        ),
    )


async def notify_customer_rejected(
    session: AsyncSession,
    *,
    customer_id: int,
    club_name: str,
    reason: str | None,
    telegram_id: int | None = None,
) -> None:
    """`telegram_id` — chaqiruvchi uni bron holati o'zgarishidan OLDIN
    o'qib qo'ygan bo'lsa uzatiladi.

    Bu SHART: `users_booking_contact` policy'si mijoz qatorini faqat uning
    shu klubda `PENDING`/`CONFIRMED` broni bo'lsa ochadi. Bron `CANCELLED`
    bo'lgach shart yolg'onga aylanadi va bu yerdagi o'qish jimgina NULL
    qaytaradi — xabar hech qachon yuborilmasdi (audit topilmasi,
    2026-08-16). Berilmasa eski (zaxira) yo'l saqlanadi.
    """
    tail = f"\n\nSabab: {reason}" if reason else ""
    await _notify_customer(
        session,
        customer_id=customer_id,
        text_body=f"❌ Broningiz bekor qilindi — {club_name}{tail}",
        telegram_id=telegram_id,
    )


async def _notify_customer(
    session: AsyncSession, *, customer_id: int, text_body: str, telegram_id: int | None = None
) -> None:
    if telegram_id is None:
        try:
            telegram_id = await session.scalar(
                text("SELECT telegram_id FROM users WHERE id = :uid AND kind = 'customer'"),
                {"uid": customer_id},
            )
        except Exception:  # noqa: BLE001
            log.warning("Mijoz telegram_id o'qib bo'lmadi (uid=%s)", customer_id, exc_info=True)
            return

    if not telegram_id:
        return

    await telegram_api.send_message(_token(), int(telegram_id), text_body)


def _to_club_time(starts_at: Any, timezone: str) -> Any:
    """Klub zonasidagi mahalliy vaqt. Zona noto'g'ri bo'lsa xom qiymat."""
    try:
        return starts_at.astimezone(ZoneInfo(timezone))
    except Exception:  # noqa: BLE001
        log.warning("Klub zonasi o'qilmadi: %s", timezone)
        return starts_at


def format_starts_at(starts_at: Any, timezone: str) -> str:
    """`DD-MM-YYYY HH:MM` — xodim xabarlari uchun bir qatorli shakl."""
    return _to_club_time(starts_at, timezone).strftime("%d-%m-%Y %H:%M")
