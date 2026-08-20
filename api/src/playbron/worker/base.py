"""Fon vazifalari uchun umumiy asos: GUC konteksti va ish jurnali.

HTTP so'rovidan farqli fon vazifasida so'rov konteksti YO'Q — `app.club_id`
avtomatik kelmaydi va RLS ostidagi so'rovlar xato bermay JIMGINA 0 qator
qaytaradi (`.claude/skills/fon-vazifasi/SKILL.md`). Shu modul kontekstni
har klub uchun ANIQ ochadi.

Jurnal (`jobs`) va bildirishnomalar (`notifications`) tenant ma'lumoti
emas, worker'ning texnik yozuvlari — ularga kirish klub policy'si bilan
emas, `app.job_writer` claim'i bilan ochiladi (`0035`).
"""

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
async def club_scope(club_id: int, *, role: str = "ADMIN") -> AsyncIterator[AsyncSession]:
    """Bitta klub uchun RLS konteksti ochilgan sessiya.

    Klublar bo'ylab aylanadigan vazifa HAR BIR klub uchun alohida chaqiradi —
    kontekst va `SET LOCAL` lar klublar orasida aralashmaydi. `user_id = 0`:
    fon vazifasining "aktyori" yo'q, policy'lar rol orqali o'tadi.
    """
    context.set_context(
        context.RequestContext(user_id=0, club_id=club_id, roles={club_id: role})
    )
    try:
        async with session_scope() as session:
            yield session
    finally:
        context.reset()


async def mark_job_writer(session: AsyncSession) -> None:
    """Joriy tranzaksiyada `jobs`/`notifications` yozuvini ochadi (SET LOCAL)."""
    await session.execute(text("SELECT set_config('app.job_writer', 'true', true)"))


async def active_clubs() -> list[dict[str, Any]]:
    """Faol klublar ro'yxati — id, nom, vaqt zonasi.

    `clubs_read` policy'si (`0001`/`0003`) `status='active'` qatorlarni
    GUC'siz ham ochadi — bu eng arzon cross-tenant o'qish, SECURITY DEFINER
    kerak emas.
    """
    async with AppSession() as session:
        rows = (
            await session.execute(
                text("SELECT id, name, timezone FROM clubs WHERE status = 'active' ORDER BY id")
            )
        ).all()
    return [{"id": int(r.id), "name": r.name, "timezone": r.timezone} for r in rows]


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


async def journal_finish(job_id: int, *, error: str | None = None) -> None:
    """Jurnal yozuvini yakunlaydi. Xato bo'lsa `attempts` oshadi."""
    async with AppSession() as session:
        async with session.begin():
            await mark_job_writer(session)
            await session.execute(
                text(
                    "UPDATE jobs SET status = :status, finished_at = now(),"
                    " last_error = :error,"
                    " attempts = attempts + CASE WHEN :error IS NULL THEN 0 ELSE 1 END"
                    " WHERE id = :id"
                ),
                {"status": "error" if error else "done", "error": error, "id": job_id},
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
        job_id = await journal_start(kind, club_id=club["id"])
        try:
            async with club_scope(club["id"]) as session:
                affected = await handler(session, club)
            await journal_finish(job_id)
            done += 1
            if affected:
                log.info("%s: club=%s affected=%s", kind, club["id"], affected)
        except Exception as exc:  # noqa: BLE001 — bir klub xatosi siklni to'xtatmaydi
            failed += 1
            log.error("%s: club=%s yiqildi: %s", kind, club["id"], exc, exc_info=True)
            await journal_finish(job_id, error=str(exc)[:500])
    return {"clubs": done, "failed": failed}
