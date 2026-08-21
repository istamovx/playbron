"""Bron eslatmasi — fon vazifasi.

Manba: `api/migrations/versions/0038_booking_reminders.py`, loyiha
egasining so'rovi (2026-08-18).

Loyihada shu paytgacha HECH QANDAY fon vazifasi yo'q edi
(`docs/audit-report.md` §2.5) — avto-bekor qilish, no-show va eslatma
shu sababdan ishlamasdi. Bu modul o'sha bo'shliqning birinchi bo'lagi va
qolganlari ham shu naqshni takrorlaydi:

  * bitta `asyncio` sikli, `main.py` lifespan'ida boshlanadi;
  * har aylanishda DB'ning O'ZI ishni ATOMAR da'vo qiladi
    (`UPDATE ... RETURNING`), ya'ni ikkita nusxa bir ishni ikki marta
    bajarmaydi;
  * har qanday xato butun siklni to'xtatmaydi — log'ga yozilib, keyingi
    aylanishda qayta uriniladi.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime

from sqlalchemy import text

from playbron.core import telegram_api
from playbron.core.config import LOCAL_ENVS, settings
from playbron.core.db import session_scope
from playbron.modules.bookings import notify

log = logging.getLogger("playbron.bookings.reminders")

# Bron boshlanishidan necha daqiqa oldin eslatiladi.
LEAD_MINUTES = 20
# Sikl qadami. Yetakchi oynadan sezilarli KICHIK bo'lishi kerak, aks holda
# oyna ichidagi bron o'tkazib yuborilishi mumkin.
TICK_SECONDS = 60


async def send_due_reminders() -> int:
    """Yetib kelgan eslatmalarni yuboradi va nechtasini qaytaradi.

    Da'vo va yuborish TARTIBI muhim: DB yozuvi avval belgilanadi. Teskari
    bo'lsa, yuborishdan keyin yozuv yiqilganda mijoz har aylanishda qayta
    xabar olardi.

    Buning narxi: Telegram yiqilsa o'sha eslatma YO'QOLADI (qayta
    urinilmaydi). Bu ataylab — takroriy xabar yuborishdan ko'ra bittasini
    o'tkazib yuborish afzal.
    """
    async with session_scope() as session:
        rows = (
            await session.execute(
                text("SELECT * FROM claim_due_booking_reminders(:lead)"),
                {"lead": LEAD_MINUTES},
            )
        ).all()

    if not rows:
        return 0

    token = settings.bot_token.get_secret_value()
    now = datetime.now(UTC)
    sent = 0
    for row in rows:
        # HAQIQIY qolgan vaqt. Sarlavhada `LEAD_MINUTES` turardi: 19:55 da
        # qilingan 20:00 lik bron birinchi aylanishdayoq da'vo qilinib,
        # mijozga "20 daqiqadan keyin" deb yozilardi — seansga 4 daqiqa
        # qolganda.
        left = max(1, round((row.starts_at - now).total_seconds() / 60))
        body = notify.booking_card(
            title=f"⏰ Broningiz {left} daqiqadan keyin",
            club_name=row.club_name,
            room_label=row.room_label,
            starts_at=row.starts_at,
            hours=row.hours,
            timezone=row.timezone,
        )
        try:
            await telegram_api.send_message(token, int(row.telegram_id), body)
            sent += 1
        except Exception:  # noqa: BLE001 — bitta mijoz qolganlarni to'xtatmasin
            log.warning("Eslatma yuborilmadi (booking=%s)", row.booking_id, exc_info=True)

    log.info("Bron eslatmasi: %s/%s yuborildi", sent, len(rows))
    return sent


async def run_forever() -> None:
    """Lifespan'da ishga tushadigan sikl. `CancelledError` bilan to'xtaydi."""
    log.info("Bron eslatmasi sikli ishga tushdi (%s daqiqa oldin)", LEAD_MINUTES)
    while True:
        try:
            await send_due_reminders()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — sikl HECH QACHON to'xtamaydi
            log.error("Eslatma siklida kutilmagan xato", exc_info=True)
        await asyncio.sleep(TICK_SECONDS)


def start() -> asyncio.Task[None] | None:
    """Siklni ishga tushiradi, yoki ishga tushirmaslik sababini yozadi.

    IKKALA "ishlamaydi" sharti ham SHU YERDA — chaqiruvchi lifespan
    ulardan birini o'zida ushlab tursa, keyingi fon vazifasi o'sha
    shartni yana nusxalashi kerak bo'lardi.
    """
    # `local` ham chetda: ishlab chiquvchi mashinasida sikl JONLI Telegram
    # xabarini yuborardi va qatorni da'vo qilib, prod nusxasi o'sha
    # eslatmani HECH QACHON yubormaydigan qilib qo'yardi. Webhook
    # ro'yxatdan o'tkazish (`main.py`) ham aynan shu to'plamni chetlaydi.
    if settings.env in LOCAL_ENVS:
        return None
    if not settings.bot_token.get_secret_value():
        log.warning("BOT_TOKEN yo'q — bron eslatmasi ishga tushirilmadi")
        return None
    return asyncio.create_task(run_forever())


async def stop(task: asyncio.Task[None] | None) -> None:
    if task is None:
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
