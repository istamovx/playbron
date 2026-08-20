"""Bildirishnoma matnlari — sof render, DB'siz.

Matnlar bot xabarlari uslubida (`modules/bookings/notify.py` bilan bir
xil til — uz). `payload` jsonb'dan keladi, yetishmagan kalit xato beradi —
jimgina bo'sh joy yuborilmaydi.

Testlar: `tests/test_notify_pure.py` (`RUN_DB_TESTS`siz o'tadi).
"""

TEMPLATES: dict[str, str] = {
    "booking_reminder_2h": (
        "⏰ Eslatma: {club} — {station} broningiz bugun {starts_at} da boshlanadi."
        " Ko'rishguncha!"
    ),
    "booking_reminder_20m": (
        "🎮 {club} — {station} broningiz {starts_at} da, 20 daqiqadan kam qoldi."
        " Yo'lga chiqdingizmi?"
    ),
    "daily_summary": (
        "📊 {club} — {date} kuni:\n"
        "Tushum (olingan): {received_revenue} so'm\n"
        "Sessiyalar: {sessions} ta\n"
        "Naqd smenalar farqi: {variance_total} so'm"
    ),
    "shift_variance": (
        "⚠️ {club}: smena yopildi, kassa farqi {variance} so'm"
        " (kutilgan {expected}, sanalgan {counted}). Xodim: {staff}"
    ),
}


def render(template: str, payload: dict[str, object]) -> str:
    """Shablonni to'ldiradi. Noma'lum shablon yoki yetishmagan kalit — xato."""
    try:
        text = TEMPLATES[template]
    except KeyError as exc:
        raise ValueError(f"Noma'lum shablon: {template}") from exc
    try:
        return text.format(**payload)
    except KeyError as exc:
        raise ValueError(f"{template}: payload'da {exc} kaliti yo'q") from exc
