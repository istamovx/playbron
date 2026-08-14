"""Xodimlar — klub egasi va admini uchun.

Manba: `docs/05-auth-redesign.md` Ilova C.1 (parolni klub egasi tayinlaydi).
"""

import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context
from playbron.core.errors import AppError, Conflict, Forbidden
from playbron.core.passwords import hash_password, validate
from playbron.core.text import clean_name
from playbron.deps import db, require_admin
from playbron.modules.auth.staff import normalize_login

log = logging.getLogger("playbron.staff")

router = APIRouter(prefix="/clubs", tags=["staff"])

ROLE_LABELS = {"ADMIN", "STAFF"}


class StaffCreateIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=128)
    login: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=1, max_length=128)
    role: str = Field(pattern="^(ADMIN|STAFF)$")


class StaffCreateOut(BaseModel):
    user_id: int
    login: str
    role: str
    # Parol bir martalik: xodim birinchi kirishda o'zinikini qo'yadi
    must_change_password: bool = True


def _assert_path_matches_header(club_id: int) -> None:
    """Yo'ldagi `club_id` va `X-Club-Id` bir xil bo'lishi shart.

    `current_claims` faol klubni FAQAT sarlavhadan oladi. Yo'l parametri
    tekshirilmasa, A klubning egasi `X-Club-Id: A` bilan kelib
    `/clubs/B/staff` ga yozishga urinardi — RLS uni to'xtatadi, lekin
    tekshiruvni marshrutning o'zida qilish xatoni ancha erta va
    tushunarli qaytaradi (§6.7).
    """
    active = context.current().club_id
    if active is None or int(active) != int(club_id):
        raise Forbidden("Faol klub mos kelmadi", code="CLUB_MISMATCH")


@router.post(
    "/{club_id}/staff",
    response_model=StaffCreateOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_staff(
    body: StaffCreateIn,
    session: Annotated[AsyncSession, Depends(db)],
    club_id: Annotated[int, Path()],
) -> StaffCreateOut:
    """Xodim hisobini yaratadi va boshlang'ich parol qo'yadi.

    Rol shifti (`ADMIN` faqat `STAFF` yarata olishi) funksiya ICHIDA
    tekshiriladi — bu yerdagi tekshiruv faqat erta va tushunarli xato uchun.
    """
    _assert_path_matches_header(club_id)

    login = normalize_login(body.login)
    if login is None:
        raise AppError(
            "Login faqat kichik lotin harflari, raqam, nuqta, pastki chiziq va "
            "defisdan iborat bo‘lsin (3–32 belgi)",
            code="LOGIN_INVALID_SHAPE",
        )

    name = clean_name(body.first_name)
    if not name:
        raise AppError("Ism bo‘sh bo‘lmasin", code="NAME_REQUIRED")

    # Parol uzunligi MAQSAD rolidan kelib chiqadi, chaqiruvchinikidan emas
    password = validate(body.password, role=body.role, login=login)

    try:
        user_id = await session.scalar(
            text("SELECT auth_create_staff(:login, :name, :role)"),
            {"login": login, "name": name, "role": body.role},
        )
    except Exception as exc:  # noqa: BLE001
        if "ROLE_NOT_ALLOWED" in str(exc):
            raise Forbidden(
                "Bu rolni berish huquqingiz yo‘q", code="ROLE_NOT_ALLOWED"
            ) from exc
        if "users_login_staff_uk" in str(exc):
            # Bandlik faqat SAQLASHDA aytiladi: jonli tekshiruv endpointi
            # global login makonini sanab chiqish imkonini berardi
            raise Conflict("Bu login band", code="LOGIN_TAKEN") from exc
        raise

    if user_id is None:
        raise Forbidden("Bu amal uchun ruxsat yo‘q", code="ROLE_FORBIDDEN")

    assigned = await session.scalar(
        text("SELECT auth_assign_password(:uid, :hash)"),
        {"uid": user_id, "hash": await hash_password(password)},
    )
    if not assigned:
        # Funksiya ichidagi avtorizatsiya rad etdi — hisob yaratilgan, lekin
        # parolsiz. Tranzaksiya qaytariladi.
        raise Forbidden("Parol tayinlanmadi", code="PASSWORD_NOT_ASSIGNED")

    await _log_event(session, "staff_created", club_id, {"role": body.role})

    return StaffCreateOut(user_id=int(user_id), login=login, role=body.role)


async def _log_event(
    session: AsyncSession, event: str, club_id: int, detail: dict[str, Any]
) -> None:
    """`auth_events` — login va parol YOZILMAYDI."""
    await session.execute(
        text(
            "INSERT INTO auth_events (event, user_id, club_id, detail)"
            " VALUES (:e, :uid, :club, CAST(:d AS jsonb))"
        ),
        {
            "e": event,
            "uid": context.current().user_id,
            "club": club_id,
            "d": json.dumps(detail),
        },
    )
