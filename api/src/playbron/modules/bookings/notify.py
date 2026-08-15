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


async def notify_customer_confirmed(
    session: AsyncSession,
    *,
    club_id: int,
    customer_id: int,
    club_name: str,
    station_code: str,
    starts_label: str,
    hours: int,
) -> None:
    """Xodim tasdiqladi — mijozga.

    `users_booking_contact` policy'si (0009) shu o'qishni ochadi: chaqiruvchi
    xodim, `app.club_id`/`app.club_role` to'g'ri, mijozning shu klubda FAOL
    broni bor.
    """
    await _notify_customer(
        session,
        customer_id=customer_id,
        text_body=(
            f"✅ Broningiz tasdiqlandi — {club_name}\n"
            f"Xona: {station_code}\n"
            f"Vaqt: {starts_label} · {hours} soat\n\n"
            "Iltimos, kechikmang — belgilangan vaqtdan 10 daqiqa o'tsa "
            "joyingiz bo'shatilishi mumkin."
        ),
    )


async def notify_customer_rejected(
    session: AsyncSession, *, customer_id: int, club_name: str, reason: str | None
) -> None:
    tail = f"\n\nSabab: {reason}" if reason else ""
    await _notify_customer(
        session,
        customer_id=customer_id,
        text_body=f"❌ Broningiz bekor qilindi — {club_name}{tail}",
    )


async def _notify_customer(session: AsyncSession, *, customer_id: int, text_body: str) -> None:
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


def format_starts_at(starts_at: Any, timezone: str) -> str:
    """`DD-MM-YYYY HH:MM` — klub vaqt zonasida (`docs`dagi format bilan bir xil)."""
    # `starts_at` — timezone-aware `datetime`; klub zonasiga o'giramiz.
    try:
        from zoneinfo import ZoneInfo

        local = starts_at.astimezone(ZoneInfo(timezone))
    except Exception:  # noqa: BLE001
        local = starts_at
    return local.strftime("%d-%m-%Y %H:%M")
