"""Admin bot — klub egasi/admini uchun hisobot menyusi.

Loyiha egasining so'rovi (2026-08-16): "klub adminidagi bot rolida
tugmalar kerak: 1) Kunlik tushum, 2) Xarajatlar (oy/yil kesimida),
3) Analitika". Bot tugmalari — Telegram inline keyboard
(`callback_data`), matn rasmiy-idoraviy uslubda.

Kimligini aniqlash — `bot_staff_context()` SECURITY DEFINER funksiyasi
(`0022_bot_menu_context.py`): `staff_telegram.telegram_id` orqali xodimni
topadi, FAQAT OWNER/ADMIN uchun klub kontekstini qaytaradi (moliyaviy
ma'lumot — STAFF'ga yopiq, `docs/01-architecture.md`:174 bilan bir xil
ruh). Hisobot ma'lumotlari — `finance/reports.py` (dashboard/reports
ekranlari bilan BIR XIL manba, ikkinchi hisob-kitob yozilmaydi).
"""

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import telegram_api
from playbron.modules.finance import reports

MENU_TEXT = "🎮 PlayBron boshqaruv menyusi. Kerakli hisobotni tanlang:"

_MENU_KEYBOARD = telegram_api.callback_keyboard(
    [
        [("📊 Kunlik tushum", "menu:daily")],
        [("💸 Xarajatlar", "menu:expenses")],
        [("📈 Analitika", "menu:analytics")],
    ]
)


def _money(amount: int) -> str:
    """`S()` (frontend, `mock/data.ts`) bilan bir xil — mingliklar bo'shliq bilan."""
    sign = "-" if amount < 0 else ""
    digits = str(abs(amount))
    grouped: list[str] = []
    while len(digits) > 3:
        grouped.insert(0, digits[-3:])
        digits = digits[:-3]
    grouped.insert(0, digits)
    return f"{sign}{' '.join(grouped)}"


async def _staff_context(session: AsyncSession, telegram_id: int) -> dict[str, Any] | None:
    row = (
        await session.execute(
            text(
                "SELECT user_id, first_name, club_id, club_name, role"
                " FROM bot_staff_context(:tg)"
            ),
            {"tg": telegram_id},
        )
    ).first()
    if row is None:
        return None
    return {
        "user_id": row.user_id,
        "first_name": row.first_name,
        "club_id": row.club_id,
        "club_name": row.club_name,
        "role": row.role,
    }


async def maybe_send_menu(session: AsyncSession, telegram_id: int, chat_id: int) -> bool:
    """Yozgan kishi OWNER/ADMIN sifatida bog'langan bo'lsa menyuni yuboradi.

    `True` — menyu yuborildi (chaqiruvchi boshqa hech narsa qilmasin).
    `False` — bu kishi tanilmadi (bog'lanmagan yoki oddiy STAFF) — chaqiruvchi
    o'z sukut javobini davom ettirsin.
    """
    ctx = await _staff_context(session, telegram_id)
    if ctx is None:
        return False

    await telegram_api.send_message(
        _token(), chat_id, MENU_TEXT, reply_markup=_MENU_KEYBOARD
    )
    return True


def _token() -> str:
    from playbron.core.config import settings

    return settings.admin_bot_token.get_secret_value() or settings.bot_token.get_secret_value()


async def _format_daily(session: AsyncSession, club_id: int, club_name: str) -> str:
    d = await reports.get_dashboard(session, club_id)
    lines = [
        f"📊 Kunlik hisobot — {club_name}",
        "",
        f"Bugungi tushum: {_money(d['revenue_today'])} so'm",
        f"— O'yin: {_money(d['revenue_today'] - d['bar_revenue_today'])} so'm",
        f"— Bar: {_money(d['bar_revenue_today'])} so'm",
        f"Bugungi xarajat: {_money(d['expenses_today'])} so'm",
        f"Sof foyda: {_money(d['profit_today'])} so'm",
        "",
        f"Seanslar: {d['sessions_today']} ta",
        f"Bandlik: {d['occupancy_today']}%",
    ]
    return "\n".join(lines)


async def _format_expenses(session: AsyncSession, club_id: int, club_name: str) -> str:
    month = await reports.get_report(session, club_id=club_id, period="month")
    year = await reports.get_report(session, club_id=club_id, period="year")

    lines = [
        f"💸 Xarajatlar hisoboti — {club_name}",
        "",
        f"Shu oy: {_money(month['expenses'])} so'm",
        f"Shu yil: {_money(year['expenses'])} so'm",
    ]

    if month["expense_by_category"]:
        lines.append("")
        lines.append("Shu oy — moddalar bo'yicha:")
        for row in month["expense_by_category"]:
            lines.append(f"— {row['category']}: {_money(row['amount'])} so'm")
    else:
        lines.append("")
        lines.append("Shu oy hali xarajat kiritilmagan.")

    return "\n".join(lines)


async def _format_analytics(session: AsyncSession, club_id: int, club_name: str) -> str:
    d = await reports.get_dashboard(session, club_id)
    month = await reports.get_report(session, club_id=club_id, period="month")
    margin = 0.0 if month["revenue"] == 0 else (month["profit"] / month["revenue"]) * 100

    lines = [
        f"📈 Analitika — {club_name}",
        "",
        f"Bugungi bandlik: {d['occupancy_today']}%",
        f"Shu oy o'rtacha bandlik: {month['occupancy']}%",
        f"Shu oy rentabellik: {margin:.1f}%",
        f"Shu oy stansiya soni: {month['station_count']} ta",
    ]

    if month["top_products"]:
        lines.append("")
        lines.append("Eng ko'p sotilgan (shu oy):")
        for row in month["top_products"][:5]:
            lines.append(f"— {row['product_name']}: {_money(row['revenue'])} so'm")

    return "\n".join(lines)


_HANDLERS = {
    "menu:daily": _format_daily,
    "menu:expenses": _format_expenses,
    "menu:analytics": _format_analytics,
}

_ACK_TEXT = {
    "menu:daily": "Kunlik hisobot tayyorlanmoqda…",
    "menu:expenses": "Xarajatlar hisoboti tayyorlanmoqda…",
    "menu:analytics": "Analitika tayyorlanmoqda…",
}


async def handle_callback(session: AsyncSession, callback_query: dict[str, Any]) -> None:
    """Tugma bosilganda — Telegram HAR DOIM javob (`answerCallbackQuery`)
    talab qiladi, aks holda yuklanish soatchasi osilib qoladi."""
    callback_id = callback_query.get("id")
    data = callback_query.get("data")
    message = callback_query.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    sender = callback_query.get("from") or {}
    telegram_id = sender.get("id")

    if not isinstance(callback_id, str):
        return

    handler = _HANDLERS.get(data) if isinstance(data, str) else None
    if handler is None or not isinstance(chat_id, int) or not isinstance(telegram_id, int):
        await telegram_api.answer_callback_query(_token(), callback_id)
        return

    ack_text = _ACK_TEXT.get(data, "Tayyorlanmoqda…") if isinstance(data, str) else None
    await telegram_api.answer_callback_query(_token(), callback_id, ack_text)

    ctx = await _staff_context(session, telegram_id)
    if ctx is None:
        await telegram_api.send_message(
            _token(), chat_id, "Bu amal uchun ruxsat yo'q — Telegram bog'lanishini tekshiring."
        )
        return

    text_out = await handler(session, ctx["club_id"], ctx["club_name"])
    await telegram_api.send_message(_token(), chat_id, text_out)
