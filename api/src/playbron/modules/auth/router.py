"""Auth marshrutlari — `/api/v1/auth/*`."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context, telegram_api
from playbron.core.audit import log_auth_event
from playbron.core.config import settings
from playbron.core.errors import NotFound, Unauthorized
from playbron.core.http import client_ip
from playbron.core.security import AUDIENCE_STAFF, constant_time_equal, now
from playbron.deps import current_claims, db, public_db, require_staff_token
from playbron.models import User
from playbron.modules.auth import botlogin, service, signup, staff, stafflink
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


def _to_session(payload: dict[str, Any]) -> SessionOut:
    """`payload` — `service.sign_in`/`rotate_refresh` yoki `staff.staff_login` natijasi.

    `entitlements` shu yerda QAYTA SO'RALMAYDI: uni chaqiruvchi funksiya
    JWT'ga singdirish uchun allaqachon hisoblagan va `payload["entitlements"]`
    ichida qaytargan. Avval har bir marshrut uni ikkinchi marta so'rar edi —
    har bir kirish/yangilash bitta ortiqcha DB round-trip qilardi.
    """
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
        entitlements=payload.get("entitlements"),
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
    return _to_session(payload)


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
    return _to_session(payload)


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
    return _to_session(payload)


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

    # Klub egasi/admini o'z xodimining kirish tarixini ko'rishi uchun
    # (loyiha egasining so'rovi, 2026-08-16). Muvaffaqiyatsiz urinish ATAYLAB
    # yozilmaydi — `staff.staff_login()`dagi izohlangan qadam tartibi va
    # vaqt-tenglashtirish (`waste_time()`/kechikish) HECH QANDAY o'zgarishsiz
    # qoladi, chunki bu yerga faqat MUVAFFAQIYATLI kirishdan keyin yetiladi.
    memberships = payload.get("memberships") or []
    await log_auth_event(
        event="staff_login",
        user_id=payload["user"].id,
        club_id=memberships[0]["club_id"] if memberships else None,
    )

    out = _to_session(payload)
    out.must_change_password = payload["must_change_password"]
    return out


class OwnerSignupIn(BaseModel):
    """Landing formasidagi maydonlar.

    Uzunlik chegaralari bu yerda **keng**: aniq qoidalar va tushunarli xato
    kodlari `signup.clean()` da. Pydantic faqat aql bovar qilmaydigan
    hajmni to'xtatadi, aks holda foydalanuvchi 422 va texnik matn olardi.
    """

    first_name: str = Field(min_length=1, max_length=128)
    club_name: str = Field(min_length=1, max_length=200)
    phone: str = Field(min_length=1, max_length=32)
    address: str = Field(min_length=1, max_length=600)
    login: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class OwnerSignupOut(BaseModel):
    login: str


@router.post("/owner/signup", response_model=OwnerSignupOut, status_code=201)
async def owner_signup(
    body: OwnerSignupIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(public_db)],
) -> OwnerSignupOut:
    """Klub egasi o'zi ro'yxatdan o'tadi — tashkilot + klub + hisob.

    Sessiya bu yerda ochilmaydi: konsol shu login va foydalanuvchi o'zi
    tanlagan parol bilan darhol `/auth/staff/login` ga murojaat qiladi.
    """
    login = await signup.owner_signup(session, body=body.model_dump(), ip=client_ip(request))
    return OwnerSignupOut(login=login)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=1, max_length=128)


def _top_role(memberships: list[dict[str, Any]], super_admin: bool) -> str:
    """Parol uzunligi roldan kelib chiqadi (§7.2)."""
    if super_admin:
        return "SUPER_ADMIN"
    roles = {m["role"] for m in memberships}
    if "OWNER" in roles:
        return "OWNER"
    if "ADMIN" in roles:
        return "ADMIN"
    return "STAFF"


@router.post("/staff/password/change", response_model=SessionOut)
async def change_password(
    body: PasswordChangeIn,
    request: Request,
    session: Annotated[AsyncSession, Depends(db)],
    _: Annotated[dict[str, Any], Depends(current_claims)],
    user_agent: Annotated[str | None, Header()] = None,
) -> SessionOut:
    """O'z parolini almashtirish. Joriy parol majburiy.

    Muvaffaqiyatda BARCHA eski refresh tokenlar bekor qilinadi va yangi
    sessiya beriladi: parol o'zgargach eski qurilmalardagi sessiyalar
    yashab qolmasin.
    """
    ctx = context.current()
    user = await session.get(User, ctx.user_id)
    if user is None:
        raise NotFound("Foydalanuvchi topilmadi")

    super_admin = await service.is_super_admin(session, user.id)
    memberships = await service.load_memberships(session, user.id)

    await staff.change_password(
        session,
        user_id=user.id,
        current=body.current_password,
        new_password=body.new_password,
        role=_top_role(memberships, super_admin),
        login=user.login,
    )

    # Eski tokenlar — hammasi. Yangi sessiya quyida beriladi.
    await service.revoke_all_tokens(user.id)

    org_id = memberships[0]["org_id"] if memberships else None
    entitlements = await service.load_entitlements(session, org_id)
    issued = await service.issue_tokens(
        session,
        user=user,
        memberships=memberships,
        super_admin=super_admin,
        entitlements=entitlements,
        audience=AUDIENCE_STAFF,
        user_agent=(user_agent[:UA_MAX_LEN] if user_agent else None),
        ip=client_ip(request),
    )

    return _to_session(
        {
            **issued,
            "user": user,
            "memberships": memberships,
            "is_super_admin": super_admin,
            "entitlements": entitlements,
        }
    )


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
    return PollOut(status="ready", session=_to_session(payload))


class LinkStartOut(BaseModel):
    nonce: str
    expires_in: int


class LinkPollOut(BaseModel):
    status: str  # pending | expired | ready


@router.post(
    "/telegram/link/start",
    response_model=LinkStartOut,
    dependencies=[Depends(require_staff_token)],
)
async def start_telegram_link() -> LinkStartOut:
    """Kirgan xodim — bron bildirishnomasi uchun o'z Telegram'ini ulaydi.

    Deep-link (`botlogin.py`dagi bilan bir xil naqsh) — OAuth oynasi yo'q.
    """
    nonce = await stafflink.start_link(context.current().user_id)
    return LinkStartOut(nonce=nonce, expires_in=stafflink.START_TTL_SEC)


@router.post(
    "/telegram/link/{nonce}",
    response_model=LinkPollOut,
    dependencies=[Depends(require_staff_token)],
)
async def poll_telegram_link(nonce: str) -> LinkPollOut:
    """Konsol poll'i. Yozuv webhook'da amalga oshadi — bu yerda faqat holat."""
    status = await stafflink.poll_link(nonce)
    return LinkPollOut(status=status)


_LINK_OK_TEXT: dict[str, str] = {
    "uz": "✅ Bildirishnoma ulandi — yangi bronlar endi shu yerga keladi.",
    "ru": "✅ Уведомления подключены — новые брони будут приходить сюда.",
    "en": "✅ Notifications connected — new bookings will arrive here.",
}
_LINK_EXPIRED_TEXT: dict[str, str] = {
    "uz": "⏱ Havola eskirgan. Konsolda tugmani qaytadan bosing.",
    "ru": "⏱ Ссылка устарела. Нажмите кнопку в консоли ещё раз.",
    "en": "⏱ The link expired. Press the button in the console again.",
}


def _admin_token() -> str:
    return settings.admin_bot_token.get_secret_value() or settings.bot_token.get_secret_value()


async def _handle_link_start(
    session: AsyncSession, nonce: str, sender: dict[str, Any]
) -> None:
    """`stafflink.PREFIX` bilan boshlangan nonce — kirish emas, bog'lash."""
    telegram_id = int(sender["id"])
    lang = str(sender.get("language_code") or "uz").split("-")[0].lower()
    user_id = await stafflink.approve_link(nonce)

    if user_id is None:
        texts = _LINK_EXPIRED_TEXT
        await telegram_api.send_message(_admin_token(), telegram_id, texts.get(lang, texts["uz"]))
        return

    # Telegram xususiy suhbatda `chat.id == user.id` — backfill (`0005`) bilan
    # bir xil taxmin.
    await session.execute(
        sql_text("SELECT staff_telegram_link_confirm(:u, :tg, :chat)"),
        {"u": user_id, "tg": telegram_id, "chat": telegram_id},
    )

    texts = _LINK_OK_TEXT
    await telegram_api.send_message(_admin_token(), telegram_id, texts.get(lang, texts["uz"]))


@router.post("/telegram/webhook/admin")
async def admin_bot_webhook(
    request: Request,
    session: Annotated[AsyncSession, Depends(public_db)],
    secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
) -> dict[str, bool]:
    """Admin bot webhook'i — faqat `/start <nonce>` xabarlarini qayta ishlaydi.

    Sarlavhadagi sekret `setWebhook` da o'rnatilgan qiymat bilan solishtiriladi —
    boshqa hech kim bu endpointga yozolmaydi. Telegram'ga har doim 200 qaytadi,
    aks holda u update'ni qayta-qayta yuboraveradi.

    Ikki nonce turi bitta webhook'da: kirish (`botlogin.start_login`) va
    Telegram bog'lash (`stafflink.start_link`, `lnk_` prefiksi bilan).
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
        if nonce.startswith(stafflink.PREFIX):
            await _handle_link_start(session, nonce, sender)
        else:
            # Muvaffaqiyatda javob tili — konsolda tanlangani; eskirgan
            # nonce'da konsol tili noma'lum, shuning uchun Telegram ilova
            # tiliga qaytamiz
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
    return _to_session(payload)


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshIn,
    # `db` — `current_claims` dan **keyin** ochiladigan sessiya. `public_db` bo'lsa
    # tranzaksiya token ochilishidan oldin boshlanib, `app.user_id` 0 qolardi va
    # RLS `WITH CHECK` yozishga yo'l bermasdi.
    session: Annotated[AsyncSession, Depends(db)],
) -> None:
    await service.sign_out(session, refresh_token=body.refresh_token)
    # `/logout` xodim VA mijoz uchun umumiy — hodisa nomi shuning uchun
    # "staff_" bilan boshlanmaydi (mijozda `club_id` bo'lmaydi, RLS orqali
    # klub egasiga baribir ko'rinmaydi).
    ctx = context.current()
    if ctx.user_id:
        await log_auth_event(event="logout", user_id=ctx.user_id, club_id=ctx.club_id)
