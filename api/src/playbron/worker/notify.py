"""Bildirishnoma qatlami: navbatga yozish va yuborish.

Oqim (skill §5): to'g'ridan-to'g'ri `telegram_api` chaqirilmaydi —
avval `notifications` jadvaliga yozuv, keyin `send_pending` vazifasi
yuboradi va natijani (`sent_at` yoki `error`) qaytib yozadi. Takror
yuborishni DB'dagi `notifications_dedup_uk` (0035) to'xtatadi.

`chat_id` navbatga qo'yish paytida hal qilingan bo'ladi (0035 izohi) —
bu bosqichda RLS o'qishlari yo'q, faqat claim ostidagi jadval va Telegram.
"""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import telegram_api
from playbron.core.config import settings
from playbron.core.db import AppSession
from playbron.worker.base import mark_job_writer
from playbron.worker.templates import render

log = logging.getLogger("playbron.worker")

# Shu sondan keyin yozuv ERROR bo'ladi va qayta urinilmaydi
MAX_SEND_ATTEMPTS = 3
SEND_BATCH = 50


def _token_for(recipient_kind: str) -> str:
    """CUSTOMER — mijoz boti; OWNER/STAFF — admin bot (yo'q bo'lsa asosiy).

    Fallback `modules/bookings/notify.py::_admin_token()` bilan bir xil.
    """
    if recipient_kind == "CUSTOMER":
        return settings.bot_token.get_secret_value()
    return settings.admin_bot_token.get_secret_value() or settings.bot_token.get_secret_value()


async def queue_notification(
    session: AsyncSession,
    *,
    club_id: int,
    recipient_kind: str,
    chat_id: int,
    template: str,
    entity_id: int,
    payload: dict[str, Any],
    recipient_id: int | None = None,
) -> int | None:
    """Bildirishnomani navbatga yozadi. Takror bo'lsa `None` (dedup).

    Chaqiruvchi tranzaksiyasida ishlaydi — `mark_job_writer` shu yerda
    qo'yiladi (SET LOCAL, klub kontekstiga zarar qilmaydi).
    """
    await mark_job_writer(session)
    row_id = await session.scalar(
        text(
            "INSERT INTO notifications"
            " (club_id, recipient_kind, recipient_id, chat_id, template, entity_id, payload)"
            " VALUES (:club_id, :kind, :recipient_id, :chat_id, :template, :entity_id,"
            "         CAST(:payload AS jsonb))"
            " ON CONFLICT (club_id, template, entity_id, chat_id) DO NOTHING"
            " RETURNING id"
        ),
        {
            "club_id": club_id,
            "kind": recipient_kind,
            "recipient_id": recipient_id,
            "chat_id": chat_id,
            "template": template,
            "entity_id": entity_id,
            "payload": json.dumps(payload),
        },
    )
    return int(row_id) if row_id is not None else None


async def send_pending(ctx: dict[str, Any]) -> int:
    """PENDING bildirishnomalarni yuboradi. Qaytaradi: yuborilganlar soni.

    Har qator alohida tranzaksiyada va alohida `try` da — bitta chatdagi
    xato boshqalarini to'xtatmaydi. Muvaffaqiyat FAQAT Telegram javob
    berganda yoziladi (CLAUDE.md §Xatolar: «bajarildi» DB tasdig'idan
    keyin — bu yerda tasdiq Telegram'niki).
    """
    async with AppSession() as session:
        async with session.begin():
            await mark_job_writer(session)
            rows = (
                await session.execute(
                    text(
                        "SELECT id, recipient_kind, chat_id, template, payload"
                        " FROM notifications WHERE status = 'PENDING'"
                        " ORDER BY created_at LIMIT :n"
                    ),
                    {"n": SEND_BATCH},
                )
            ).all()

    sent = 0
    for row in rows:
        try:
            payload = row.payload if isinstance(row.payload, dict) else {}
            body = render(row.template, payload)
            token = _token_for(row.recipient_kind)
            result = (
                await telegram_api.call(
                    token, "sendMessage", {"chat_id": int(row.chat_id), "text": body}
                )
                if token
                else None
            )
            ok = result is not None
            error = None if ok else "telegram javob bermadi yoki token yo'q"
        except ValueError as exc:  # shablon/payload xatosi — qayta urinish ma'nosiz
            ok = False
            error = str(exc)

        async with AppSession() as session:
            async with session.begin():
                await mark_job_writer(session)
                if ok:
                    await session.execute(
                        text(
                            "UPDATE notifications SET status = 'SENT', sent_at = now(),"
                            " error = NULL WHERE id = :id"
                        ),
                        {"id": row.id},
                    )
                    sent += 1
                else:
                    await session.execute(
                        text(
                            "UPDATE notifications SET attempts = attempts + 1, error = :err,"
                            " status = CASE WHEN attempts + 1 >= :max_a THEN 'ERROR'"
                            "               ELSE 'PENDING' END"
                            " WHERE id = :id"
                        ),
                        {"id": row.id, "err": (error or "")[:500], "max_a": MAX_SEND_ATTEMPTS},
                    )
                    log.warning(
                        "notification %s yuborilmadi (%s): %s", row.id, row.template, error
                    )
    return sent
