"""`Idempotency-Key` — takroriy so'rov bitta amalni ikki marta bajarmasin.

Xodim offline navbatining poydevori (`docs/HOLAT.md`): tarmoq sekin bo'lsa
yoki tugma ikki marta bosilsa, pul/bron yaratuvchi so'rov IKKINCHI marta
serverga yetib borsa ham, amal faqat BIR marta bajariladi — birinchi javob
aynan takrorlanadi.

Router qatlamida ikkita funksiya chaqiriladi, `deps.db()` ochgan BITTA
so'rov-tranzaksiyasi ichida — shu sabab idempotency yozuvi va haqiqiy
yozuv (bron, to'lov) birga commit/rollback bo'ladi, qo'shimcha tranzaksiya
boshqaruvi shart emas:

    outcome = await begin(session, key=..., route=..., club_id=..., ...)
    if outcome.replay is not None:
        return outcome.replay["body"]  # va status
    result = await service.create_x(...)
    await finish(session, row_id=outcome.row_id, status_code=201, response_body=result)
    return result

Nega toza FastAPI `Depends()` emas: dependency endpoint qaytargan qiymatni
ko'ra olmaydi, natijani `finish()`ga berish uchun esa aynan shu kerak.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.errors import Conflict, IdempotencyKeyReused

PG_UNIQUE_VIOLATION = "23505"

# `idempotency_keys.idempotency_key` ustuni bilan mos — juda uzun (yoki
# bo'sh) sarlavha CHECK konstreyniga urilib 500 chiqarmasin, shu yerda
# oldindan kesiladi.
MAX_KEY_LEN = 128


@dataclass
class IdempotencyOutcome:
    """`begin()` natijasi.

    `replay` to'lgan bo'lsa — servis chaqirilmaydi, saqlangan javob
    aynan qaytariladi. `row_id` to'lgan bo'lsa — amal tugagach `finish()`
    shu qatorni yakunlaydi.
    """

    replay: dict[str, Any] | None
    row_id: int | None


def _hash(path_params: dict[str, Any], body: dict[str, Any]) -> str:
    """Yo'l parametrlari + body — CHUNKI `cancel_order`/`close_bill` kabi
    endpoint'larda `order_id`/`booking_id` BODY'da emas, yo'lda. Faqat
    body xeshlansa ikki xil buyurtma bo'sh `{}` body bilan bir xil xesh
    berardi va noto'g'ri javobni qaytarib yuborardi."""
    canonical = json.dumps(
        {"path": path_params, "body": body}, sort_keys=True, default=str, ensure_ascii=False
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def begin(
    session: AsyncSession,
    *,
    key: str | None,
    route: str,
    club_id: int,
    user_id: int,
    path_params: dict[str, Any],
    body: dict[str, Any],
) -> IdempotencyOutcome:
    """Kalit yo'q bo'lsa — bugungidek ishlaydi (Stage 1'da sarlavha
    ixtiyoriy). Kalit bo'lsa — yozuvni band qiladi yoki eski javobni topadi.
    """
    if not key:
        return IdempotencyOutcome(replay=None, row_id=None)
    key = key[:MAX_KEY_LEN]
    req_hash = _hash(path_params, body)

    # SAVEPOINT — INSERT `23505` bilan yiqilsa, tashqi (butun so'rovlik)
    # tranzaksiya ABORT holatiga tushmasin. Aks holda pastdagi SELECT ham
    # "current transaction is aborted" bilan yiqilardi (`0035` naqshi).
    try:
        async with session.begin_nested():
            row_id = await session.scalar(
                text(
                    "INSERT INTO idempotency_keys"
                    " (club_id, idempotency_key, route, request_hash, created_by)"
                    " VALUES (:club_id, :key, :route, :hash, :user_id) RETURNING id"
                ),
                {
                    "club_id": club_id,
                    "key": key,
                    "route": route,
                    "hash": req_hash,
                    "user_id": user_id,
                },
            )
    except DBAPIError as exc:
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate != PG_UNIQUE_VIOLATION:
            raise
        row = (
            await session.execute(
                text(
                    "SELECT request_hash, completed_at, response_status, response_body"
                    " FROM idempotency_keys"
                    " WHERE club_id = :club_id AND idempotency_key = :key AND route = :route"
                ),
                {"club_id": club_id, "key": key, "route": route},
            )
        ).mappings().one()

        if row["request_hash"] != req_hash:
            raise IdempotencyKeyReused(
                "Bu kalit boshqa so'rov uchun ishlatilgan", code="IDEMPOTENCY_KEY_REUSED"
            ) from exc
        if row["completed_at"] is None:
            # Invariant: committed qator doim `completed_at`li — `finish()`
            # har doim shu funksiya bilan bitta tranzaksiyada, javob
            # qaytishdan OLDIN chaqiriladi. Shu holatga tushish — xato
            # signali, oddiy oqim emas.
            raise Conflict("So'rov hali bajarilmoqda", code="IDEMPOTENCY_IN_PROGRESS") from exc
        return IdempotencyOutcome(
            replay={"status": row["response_status"], "body": row["response_body"]},
            row_id=None,
        )

    return IdempotencyOutcome(replay=None, row_id=row_id)


async def finish(
    session: AsyncSession,
    *,
    row_id: int | None,
    status_code: int,
    response_body: dict[str, Any],
) -> None:
    """Kalit berilmagan bo'lsa (`row_id is None`) — hech narsa qilmaydi."""
    if row_id is None:
        return
    await session.execute(
        text(
            "UPDATE idempotency_keys"
            " SET completed_at = now(), response_status = :status,"
            "     response_body = CAST(:body AS jsonb)"
            " WHERE id = :id"
        ),
        {"status": status_code, "body": json.dumps(response_body, default=str), "id": row_id},
    )
