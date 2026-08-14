"""Auth marshrutlari — `/api/v1/auth/*`."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.config import settings
from playbron.core.errors import NotFound, Unauthorized
from playbron.core.http import client_ip
from playbron.core.security import constant_time_equal, now
from playbron.deps import db, public_db
from playbron.modules.auth import botlogin, service, staff
from playbron.modules.auth.telegram import TelegramIdentity, verify_init_data, verify_widget

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Sxemalar ──────────────────────────────────────────────────────────────


class InitDataIn(BaseModel):
    init_data: str = Field(min_length=1, description="window.Telegram.WebApp.initData")


class WidgetIn(BaseModel):
    """Telegram Login Widget qaytargan tekis obyekt."""

    id: int
    first_name: str
    auth_date: int
    hash: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10)


class MembershipOut(BaseModel):
    club_id: int
    club_name: str
    role: str


class UserOut(BaseModel):
    id: int
    # Xodimda YO'Q — uning Telegrami shaxsni tasdiqlamaydi (§3.2)
    telegram_id: int | None = None
    login: str | None = None
    first_name: str
    last_name: str | None
    username: str | None
    phone: str | None
    phone_verified: bool


class SessionOut(BaseModel):
    access_token: str
    access_expires_at: datetime
    refresh_token: str
    refresh_expires_at: datetime
    user: UserOut
    memberships: list[MembershipOut]
    is_super_admin: bool
    entitlements: dict[str, Any] | None = None
    # Birov bergan parol bir martalik: `true` bo'lsa konsol faqat parol
    # almashtirish ekranini ochadi (Ilova C.2)
    must_change_password: bool = False


def _to_session(payload: dict[str, Any], entitlements: dict[str, Any] | None) -> SessionOut:
    user = payload["user"]
    return SessionOut(
        access_token=payload["access_token"],
        access_expires_at=payload["access_expires_at"],
        refresh_token=payload["refresh_token"],
        refresh_expires_at=payload["refresh_expires_at"],
        user=UserOut(
            id=user.id,
            telegram_id=user.telegram_id,
            login=user.login,
            first_name=user.first_name,
            last_name=user.last_name,
            username=user.username,
            phone=user.phone,
            phone_verified=user.phone_verified_at is not None,
        ),
        memberships=[
            MembershipOut(club_id=m["club_id"], club_name=m["club_name"], role=m["role"])
            for m in payload["memberships"]
        ],
        is_super_admin=payload["is_super_admin"],
        entitlements=entitlements,
    )


IP_MAX_LEN = 45  # `refresh_tokens.ip` ustuni kengligi (IPv6 + zona)
UA_MAX_LEN = 512


def _client(request: Request, user_agent: str | None) -> tuple[str | None, str | None]:
    """Sessiya yozuvi uchun mijoz belgilari.

    IP `client_ip()` dan olinadi — `request.client.host` emas: uvicorn
    `--forwarded-allow-ips='*'` bilan yurganda u XFF'ning mijoz boshqaradigan
    eng chap elementiga aylanadi va audit ustuni soxtalanardi.
    """
    ip = client_ip(request)
    return (
        (user_agent[:UA_MAX_LEN] if user_agent else None),
        (ip[:IP_MAX_LEN] if ip else None),
    )


# ── Marshrutlar ───────────────────────────────────────────────────────────


@router.post("/telegram/initdata", response_model=SessionOut)
async def sign_in_initdata(
    body: InitDataIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(public_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> SessionOut:
    """Mini App ichidan kirish."""
    identity = verify_init_data(body.init_data)
    ua, ip = _client(request, user_agent)
    payload = await service.sign_in(session, identity, user_agent=ua, ip=ip)

    org_id = payload["memberships"][0]["org_id"] if payload["memberships"] else None
    entitlements = await service.load_entitlements(session, org_id)
    return _to_session(payload, entitlements)


@router.post("/telegram/widget", response_model=SessionOut)
async def sign_in_widget(
    body: WidgetIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(public_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> SessionOut:
    """Landing'dagi Telegram Login Widget orqali kirish."""
    identity = verify_widget(body.model_dump(exclude_none=True))
    ua, ip = _client(request, user_agent)
    payload = await service.sign_in(session, identity, user_agent=ua, ip=ip)

    org_id = payload["memberships"][0]["org_id"] if payload["memberships"] else None
    entitlements = await service.load_entitlements(session, org_id)
    return _to_session(payload, entitlements)


@router.post("/refresh", response_model=SessionOut)
async def refresh(
    body: RefreshIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(public_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> SessionOut:
    ua, ip = _client(request, user_agent)
    payload = await service.rotate_refresh(
        session, presented=body.refresh_token, user_agent=ua, ip=ip
    )

    org_id = payload["memberships"][0]["org_id"] if payload["memberships"] else None
    entitlements = await service.load_entitlements(session, org_id)
    return _to_session(payload, entitlements)


class StaffLoginIn(BaseModel):
    """Xodim, klub admini va super admin uchun yagona kirish."""

    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


@router.post("/staff/login", response_model=SessionOut)
async def staff_login(
    body: StaffLoginIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(public_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> SessionOut:
    """Login + parol.

    Hisob yo'qligi, xato parol va faol bo'lmagan holat — uchalasi ham AYNAN
    bir xil 401 qaytaradi.
    """
    ua, ip = _client(request, user_agent)
    payload = await staff.staff_login(
        session,
        login=body.login,
        password=body.password,
        user_agent=ua,
        ip=ip,
    )

    org_id = payload["memberships"][0]["org_id"] if payload["memberships"] else None
    entitlements = await service.load_entitlements(session, org_id)

    out = _to_session(payload, entitlements)
    out.must_change_password = payload["must_change_password"]
    return out


class StartIn(BaseModel):
    """Konsolda tanlangan til — bot javobi shu tilda bo'ladi."""

    lang: str = "uz"


class StartOut(BaseModel):
    nonce: str
    expires_in: int


class PollOut(BaseModel):
    status: str  # pending | expired | ready
    session: SessionOut | None = None


@router.post("/telegram/start", response_model=StartOut)
async def start_bot_login(body: StartIn | None = None) -> StartOut:
    """Bot orqali kirishni boshlaydi — deep-link uchun nonce beradi.

    Konsol foydalanuvchini `tg://resolve?domain=<bot>&start=<nonce>` ga
    yo'naltiradi va shu nonce bilan poll qiladi. OAuth oynasi ochilmaydi,
    @BotFather'dagi `/setdomain` ham shart emas.
    """
    lang = (body.lang if body else "uz").lower()
    if lang not in {"uz", "ru", "en"}:
        lang = "uz"
    nonce = await botlogin.start_login(lang)
    return StartOut(nonce=nonce, expires_in=botlogin.START_TTL_SEC)


@router.post("/telegram/start/{nonce}", response_model=PollOut)
async def poll_bot_login(
    nonce: str,
    request: Request,
    session: Annotated[AsyncSession, Depends(public_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> PollOut:
    """Bot tasdig'ini kutadi. `ready` — sessiya bilan, bir marta."""
    status, profile = await botlogin.poll_login(nonce)
    if status != "ready" or profile is None:
        return PollOut(status=status)

    identity = TelegramIdentity(
        telegram_id=int(profile["id"]),
        first_name=str(profile.get("first_name") or ""),
        last_name=profile.get("last_name"),
        username=profile.get("username"),
        language_code=profile.get("language_code"),
        photo_url=None,
        auth_date=int(now().timestamp()),
        # Nonce bir marta iste'mol qilinadi — replay guard uchun yetarli unikallik
        raw_hash=f"botstart-{nonce}",
        source="bot",
    )

    ua, ip = _client(request, user_agent)
    payload = await service.sign_in(session, identity, user_agent=ua, ip=ip)

    org_id = payload["memberships"][0]["org_id"] if payload["memberships"] else None
    entitlements = await service.load_entitlements(session, org_id)
    return PollOut(status="ready", session=_to_session(payload, entitlements))


@router.post("/telegram/webhook/admin")
async def admin_bot_webhook(
    request: Request,
    secret: Annotated[
        str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")
    ] = None,
) -> dict[str, bool]:
    """Admin bot webhook'i — faqat `/start <nonce>` xabarlarini qayta ishlaydi.

    Sarlavhadagi sekret `setWebhook` da o'rnatilgan qiymat bilan solishtiriladi —
    boshqa hech kim bu endpointga yozolmaydi. Telegram'ga har doim 200 qaytadi,
    aks holda u update'ni qayta-qayta yuboraveradi.
    """
    if not settings.tg_webhook_secret.get_secret_value():
        raise Unauthorized("Webhook sekreti sozlanmagan", code="WEBHOOK_BAD_SECRET")
    if not secret or not constant_time_equal(secret, botlogin.webhook_secret_token()):
        raise Unauthorized("Webhook sekreti mos kelmadi", code="WEBHOOK_BAD_SECRET")

    try:
        update = await request.json()
    except ValueError:
        return {"ok": True}

    parsed = botlogin.extract_start(update if isinstance(update, dict) else {})
    if parsed:
        nonce, sender = parsed
        # Muvaffaqiyatda javob tili — konsolda tanlangani; eskirgan nonce'da
        # konsol tili noma'lum, shuning uchun Telegram ilova tiliga qaytamiz
        console_lang = await botlogin.approve_login(nonce, sender)
        await botlogin.notify(
            int(sender["id"]),
            console_lang or sender.get("language_code"),
            approved=console_lang is not None,
        )

    return {"ok": True}


class DevLoginIn(BaseModel):
    """Faqat lokal ishlab chiqish uchun."""

    telegram_id: int
    first_name: str = "Dev"


@router.post("/dev/login", response_model=SessionOut)
async def dev_login(
    body: DevLoginIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(public_db)],
    user_agent: Annotated[str | None, Header()] = None,
) -> SessionOut:
    """Telegramsiz kirish — **faqat lokal muhitda**.

    Telegram Login Widget `localhost` da ishlamaydi (@BotFather'da haqiqiy domen
    talab qilinadi), shuning uchun konsolni lokal ishlab chiqishda sinash uchun
    shu yo'l bor. Prod'da endpoint umuman javob bermaydi.
    """
    if settings.env not in {"local", "test"}:
        raise NotFound("Topilmadi")

    identity = TelegramIdentity(
        telegram_id=body.telegram_id,
        first_name=body.first_name,
        last_name=None,
        username=None,
        language_code="uz",
        photo_url=None,
        auth_date=int(now().timestamp()),
        # Replay guard uchun har chaqiruvda boshqa qiymat
        raw_hash=f"dev-{body.telegram_id}-{now().timestamp()}",
        source="widget",
    )

    ua, ip = _client(request, user_agent)
    payload = await service.sign_in(session, identity, user_agent=ua, ip=ip)

    org_id = payload["memberships"][0]["org_id"] if payload["memberships"] else None
    entitlements = await service.load_entitlements(session, org_id)
    return _to_session(payload, entitlements)


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshIn,
    # `db` — `current_claims` dan **keyin** ochiladigan sessiya. `public_db` bo'lsa
    # tranzaksiya token ochilishidan oldin boshlanib, `app.user_id` 0 qolardi va
    # RLS `WITH CHECK` yozishga yo'l bermasdi.
    session: Annotated[AsyncSession, Depends(db)],
) -> None:
    await service.sign_out(session, refresh_token=body.refresh_token)
