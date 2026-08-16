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
from playbron.core.audit import log_action
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


class StaffMemberOut(BaseModel):
    user_id: int
    login: str
    first_name: str
    role: str
    status: str


class ActivityLogOut(BaseModel):
    """`audit_log` (CRUD) + `auth_events` (kirish/chiqish) birlashtirilgan
    ko'rinishi — klub egasi/admini o'z klubi bo'yicha."""

    id: str
    at: str
    source: str
    event: str
    target: str | None
    actor_name: str | None
    actor_login: str | None
    detail: dict[str, Any] | None


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


@router.get(
    "/{club_id}/staff",
    response_model=list[StaffMemberOut],
    dependencies=[Depends(require_admin)],
)
async def list_staff(
    session: Annotated[AsyncSession, Depends(db)],
    club_id: Annotated[int, Path()],
) -> list[StaffMemberOut]:
    """Klub xodimlari — `memberships_read` (`0007`) OWNER/ADMIN uchun
    butun ro'yxatni ochadi (`app.club_role` GUC orqali)."""
    _assert_path_matches_header(club_id)

    rows = (
        await session.execute(
            text(
                "SELECT u.id, u.login, u.first_name, m.role, u.status"
                " FROM memberships m JOIN users u ON u.id = m.user_id"
                " WHERE m.club_id = :club_id AND m.status = 'active'"
                " ORDER BY m.role, u.login"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [
        StaffMemberOut(
            user_id=r.id, login=r.login, first_name=r.first_name, role=r.role, status=r.status
        )
        for r in rows
    ]


@router.get(
    "/{club_id}/logs",
    response_model=list[ActivityLogOut],
    dependencies=[Depends(require_admin)],
)
async def list_club_logs(
    session: Annotated[AsyncSession, Depends(db)],
    club_id: Annotated[int, Path()],
    limit: int = 100,
) -> list[ActivityLogOut]:
    """Klub faoliyat jurnali — `audit_log` (CRUD) + `auth_events`
    (kirish/chiqish) birlashtirilgan, so'nggidan boshlab.

    RLS'ning o'zi ikkalasini ham `club_id = app_club_id() AND
    app_club_role IN ('OWNER','ADMIN')` bilan cheklaydi (`0005_two_
    worlds_auth.py`) — bu yerdagi `WHERE club_id = :club_id` faqat
    ikkinchi qatlam, RLS allaqachon boshqa klub qatorini ko'rsatmaydi.
    """
    _assert_path_matches_header(club_id)
    limit = max(1, min(limit, 200))

    rows = (
        await session.execute(
            text(
                "SELECT * FROM ("
                "  SELECT 'audit' AS source, a.id, a.at, a.action AS event, a.target,"
                "         u.first_name AS actor_name, u.login AS actor_login, a.after AS detail"
                "  FROM audit_log a LEFT JOIN users u ON u.id = a.actor_user_id"
                "  WHERE a.club_id = :club_id"
                "  UNION ALL"
                "  SELECT 'auth' AS source, e.id, e.at, e.event,"
                "         CAST(NULL AS varchar(128)) AS target,"
                "         u.first_name AS actor_name, u.login AS actor_login, e.detail"
                "  FROM auth_events e LEFT JOIN users u ON u.id = e.user_id"
                "  WHERE e.club_id = :club_id"
                ") combined"
                " ORDER BY at DESC"
                " LIMIT :limit"
            ),
            {"club_id": club_id, "limit": limit},
        )
    ).all()
    return [
        ActivityLogOut(
            id=f"{r.source}:{r.id}",
            at=r.at.isoformat(),
            source=r.source,
            event=r.event,
            target=r.target,
            actor_name=r.actor_name,
            actor_login=r.actor_login,
            detail=r.detail,
        )
        for r in rows
    ]


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
        # SQLAlchemy'ning asyncpg adapteri asl `asyncpg.exceptions.*` ni
        # o'ziga xos DBAPI qobig'iga o'raydi va bu qobiq `constraint_name`ni
        # UZATMAYDI — faqat `sqlstate` va matn saqlanadi (`core/errors.py`
        # dagi global handler ham shu sabab faqat `sqlstate`ga tayanadi).
        # Shuning uchun konstreynt nomi matndan qidiriladi, lekin
        # `sqlstate == 23505` bilan qo'shib — ikkalasi birga ANIQ shu
        # konstreynt buzilganini bildiradi.
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)

        if sqlstate == "23505" and "users_login_staff_uk" in str(exc):
            # `core/errors.py` dagi global handler shu SQLSTATE'ni umumiy
            # ALREADY_EXISTS'ga aylantiradi — bu yerda ANIQ konstreynt nomi
            # bo'yicha ATAYLAB oldin ushlanadi, chunki xabar mijozga tushunarli
            # bo'lishi kerak. Bandlik faqat SAQLASHDA aytiladi: jonli tekshiruv
            # endpointi global login makonini sanab chiqish imkonini berardi.
            raise Conflict("Bu login band", code="LOGIN_TAKEN") from exc

        # `auth_create_staff` rol shifti buzilganda `RAISE EXCEPTION
        # 'ROLE_NOT_ALLOWED'` qiladi (plpgsql, SQLSTATE P0001). Bu matn
        # funksiya ichidagi LITERAL doim shu — hech qanday chaqiruvchi
        # qiymati (login, ism) unga qo'shilmaydi, shuning uchun matn bo'yicha
        # moslash xavfsiz: boshqa hech qanday xato shu satrni tasodifan
        # hosil qila olmaydi.
        if "ROLE_NOT_ALLOWED" in str(exc):
            raise Forbidden("Bu rolni berish huquqingiz yo‘q", code="ROLE_NOT_ALLOWED") from exc
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
    await log_action(
        action="staff_created",
        target=login,
        club_id=club_id,
        after={"role": body.role, "first_name": body.first_name},
    )

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
