"""Fon vazifalari uchun umumiy asos: GUC konteksti va ish jurnali.

HTTP so'rovidan farqli fon vazifasida so'rov konteksti YO'Q — `app.club_id`
avtomatik kelmaydi va RLS ostidagi so'rovlar xato bermay JIMGINA 0 qator
qaytaradi (`.claude/skills/fon-vazifasi/SKILL.md`). Shu modul kontekstni
har klub uchun ANIQ ochadi.

Jurnal (`jobs`) va bildirishnomalar (`notifications`) tenant ma'lumoti
emas, worker'ning texnik yozuvlari — ularga kirish klub policy'si bilan
emas, `app.job_writer` claim'i bilan ochiladi (`0035`).
"""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.db import AppSession, session_scope

log = logging.getLogger("playbron.worker")


@asynccontextmanager
async def club_scope(club_id: int) -> AsyncIterator[AsyncSession]:
    """Bitta klub uchun worker RLS konteksti ochilgan sessiya.

    Klublar bo'ylab aylanadigan vazifa HAR BIR klub uchun alohida chaqiradi —
    kontekst va `SET LOCAL` lar klublar orasida aralashmaydi.

    `user_id = 0`, `roles` BO'SH — worker hech qanday rol GUC'i ko'tarmaydi:
    `app.club_role` to'ldirilsa GUC-claim policy'lari (masalan memberships
    yozuvi, staff provision) ochilib ketardi — worker ularga muhtoj emas
    (rls-review topilmasi). Butun kirish `app.worker` claim'i (0036, faqat
    joriy klub) va SECURITY DEFINER funksiyalar orqali.
    """
    context.set_context(context.RequestContext(user_id=0, club_id=club_id, roles={}))
    try:
        async with session_scope() as session:
            await session.execute(text("SELECT set_config('app.worker', 'true', true)"))
            yield session
    finally:
        context.reset()


async def mark_job_writer(session: AsyncSession) -> None:
    """Joriy tranzaksiyada `jobs`/`notifications` yozuvini ochadi (SET LOCAL)."""
    await session.execute(text("SELECT set_config('app.job_writer', 'true', true)"))


async def ensure_club_context(session: AsyncSession) -> None:
    """Vazifa `club_scope`siz chaqirilsa BAQIRIB xato beradi.

    Skill talabi (§7): GUC o'rnatilmagan holda vazifa 0 qator EMAS, xato
    berishi kerak — aks holda RLS jimgina bo'sh natija qaytaradi va jurnal
    yolg'on `done` yozadi. Har vazifa handler'ining birinchi qatori shu.
    """
    row = (
        await session.execute(
            text("SELECT app_worker() AS w, app_club_id() AS c")
        )
    ).one()
    if not row.w or int(row.c or 0) == 0:
        raise RuntimeError(
            "Worker konteksti yo'q — vazifa club_scope'siz chaqirilgan"
            f" (app_worker={row.w}, app_club_id={row.c})"
        )


async def active_clubs() -> list[dict[str, Any]]:
    """Faol klublar ro'yxati — id, nom, vaqt zonasi.

    `clubs_read` policy'si (`0001`/`0003`) `status='active'` qatorlarni
    GUC'siz ham ochadi — bu eng arzon cross-tenant o'qish, SECURITY DEFINER
    kerak emas.
    """
    async with AppSession() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, name, timezone,"
                    "       COALESCE(opens_at_min, 0) AS opens_at_min,"
                    "       COALESCE(closes_at_min, 1440) AS closes_at_min"
                    " FROM clubs WHERE status = 'active' ORDER BY id"
                )
            )
        ).all()
    return [
        {
            "id": int(r.id),
            "name": r.name,
            "timezone": r.timezone,
            "opens_at_min": int(r.opens_at_min),
            "closes_at_min": int(r.closes_at_min),
        }
        for r in rows
    ]


async def journal_start(kind: str, *, club_id: int | None = None) -> int:
    """Bajarilish jurnalida `running` yozuvi ochadi, id qaytaradi."""
    async with AppSession() as session:
        async with session.begin():
            await mark_job_writer(session)
            job_id = await session.scalar(
                text(
                    "INSERT INTO jobs (kind, club_id) VALUES (:kind, :club_id) RETURNING id"
                ),
                {"kind": kind, "club_id": club_id},
            )
    return int(job_id or 0)


async def journal_finish(
    job_id: int, *, error: str | None = None, payload: dict[str, Any] | None = None
) -> None:
    """Jurnal yozuvini yakunlaydi. Xato bo'lsa `attempts` oshadi.

    `payload` — bajarilish izi (masalan avto-bekor qilingan bron id'lari):
    tizim qilgan pul-ta'sirli amallar auditsiz qolmasin (§Pul 11-band).
    """
    async with AppSession() as session:
        async with session.begin():
            await mark_job_writer(session)
            # Inkrement Python'da: `:error` parametri SQL ichida ham matn, ham
            # `IS NULL` shartida ishlatilsa asyncpg tipini aniqlay olmaydi
            # (AmbiguousParameterError)
            await session.execute(
                text(
                    "UPDATE jobs SET status = :status, finished_at = now(),"
                    " last_error = :error, attempts = attempts + :inc,"
                    " payload = CAST(:payload AS jsonb)"
                    " WHERE id = :id"
                ),
                {
                    "status": "error" if error else "done",
                    "error": error,
                    "inc": 1 if error else 0,
                    "payload": json.dumps(payload or {}),
                    "id": job_id,
                },
            )


async def run_per_club(kind: str, handler: Any) -> dict[str, int]:
    """Vazifani har faol klub uchun alohida kontekstda yuritadi.

    Bitta klubdagi xato BOSHQA klublarni to'xtatmaydi (sikl ichida
    `try/except`) — skill talabi. Har klub o'z jurnal yozuvini oladi.
    `handler(session, club) -> int` — nechta yozuvga ta'sir qilganini
    qaytaradi (jurnalga tushmaydi, log uchun).
    """
    done = 0
    failed = 0
    for club in await active_clubs():
        # journal_start ham try ICHIDA — jurnal yozuvi yiqilsa (masalan FK)
        # butun sikl emas, faqat shu klub yiqilsin
        job_id = 0
        try:
            job_id = await journal_start(kind, club_id=club["id"])
            async with club_scope(club["id"]) as session:
                result = await handler(session, club)
            # Handler `int` yoki `(int, iz-payload)` qaytarishi mumkin —
            # iz jurnalda qoladi (masalan bekor qilingan bron id'lari)
            if isinstance(result, tuple):
                affected, trail = result
            else:
                affected, trail = result, None
            await journal_finish(job_id, payload=trail)
            done += 1
            if affected:
                log.info("%s: club=%s affected=%s", kind, club["id"], affected)
        except Exception as exc:  # noqa: BLE001 — bir klub xatosi siklni to'xtatmaydi
            failed += 1
            log.error("%s: club=%s yiqildi: %s", kind, club["id"], exc, exc_info=True)
            if job_id:
                await journal_finish(job_id, error=str(exc)[:500])
    return {"clubs": done, "failed": failed}
