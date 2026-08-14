"""Klub egasi o'zi ro'yxatdan o'tadi.

Manba: `docs/05-auth-redesign.md` §5.5 + Ilova C.1, chetlanish sabablari
`0008_owner_signup` migratsiyasining boshida yozilgan.

Tartib ATAYLAB shunday:

  1. barcha maydonlar tozalanadi va tekshiriladi — DB va Argon2 GACHA
  2. chegara IP bo'yicha — qimmat ishdan oldin
  3. `app.signup_login` doirasi ochiladi
  4. `auth_owner_signup` — bitta tranzaksiyada besh jadval
  5. doira darhol yopiladi
"""

from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import ratelimit
from playbron.core.errors import AppError, BadRequest, Conflict
from playbron.core.passwords import hash_password, validate
from playbron.core.text import clean_name
from playbron.modules.auth.staff import normalize_login
from playbron.modules.bot.contact import normalize_phone

# §10.1: ochiq endpoint. Bu tezlikda global login makonini sanab bo'lmaydi,
# ya'ni «login band» javobini berish hisob sanash orakuliga aylanmaydi.
IP_HOUR: Final = (3, 3_600)
IP_DAY: Final = (10, 86_400)

# IP aniqlanmagan so'rovlar uchun umumiy chelak (§10.5 — «eng qat'iy chelak»).
# Haqiqiy IP hech qachon shu satrga teng bo'lolmaydi.
UNKNOWN_IP: Final = "-noma'lum-"

NAME_MIN: Final = 2
NAME_MAX: Final = 64
ORG_MIN: Final = 2
ORG_MAX: Final = 160
ADDRESS_MIN: Final = 5
ADDRESS_MAX: Final = 500

# Klub egasi — `passwords.MIN_LENGTH['OWNER']` = 14 belgi
OWNER_ROLE: Final = "OWNER"


class SignupInput:
    """Tozalangan va tekshirilgan maydonlar."""

    __slots__ = ("address", "club_name", "first_name", "login", "password", "phone")

    def __init__(
        self,
        *,
        login: str,
        first_name: str,
        club_name: str,
        phone: str,
        address: str,
        password: str,
    ) -> None:
        self.login = login
        self.first_name = first_name
        self.club_name = club_name
        self.phone = phone
        self.address = address
        self.password = password


def _text_field(raw: str, *, low: int, high: int, code: str, label: str) -> str:
    """Tozalaydi va uzunlikni tekshiradi.

    `clean_name` ning `limit` argumenti ATAYLAB ishlatilmaydi — u qiymatni
    jimgina KESADI, ya'ni `len(value) <= high` sharti hech qachon yolg'on
    bo'lmasdi va 600 belgilik manzil xatosiz 500 ga qirqilib bazaga tushardi.
    Foydalanuvchi nima saqlanganini bilmay qolishi shu maydonlar uchun
    maqbul emas: manzil va klub nomi MIJOZGA ko'rinadi.

    Shuning uchun kesish yo'q — chegaradan oshsa aniq xato qaytadi. Yuqori
    chegara Pydantic'nikidan (`OwnerSignupIn`) pastroq, ya'ni oraliqdagi
    qiymat aynan shu yerda tushunarli kod bilan rad etiladi.
    """
    value = clean_name(raw, limit=high + 1)
    if not (low <= len(value) <= high):
        raise BadRequest(f"{label} {low}–{high} belgi bo‘lsin", code=code)
    return value


def clean(body: dict[str, Any]) -> SignupInput:
    """Barcha maydonlarni tekshiradi. Xato bo'lsa SABABI aytiladi.

    Parol eng oxirida tekshiriladi — u boshqa maydonlarga (login, telefon,
    klub nomi) qarab rad etiladi, ya'ni ular allaqachon tozalangan bo'lishi
    kerak.
    """
    login = normalize_login(str(body.get("login") or ""))
    if login is None:
        raise BadRequest(
            "Login faqat kichik lotin harflari, raqam, nuqta, pastki chiziq va "
            "defisdan iborat bo‘lsin (3–32 belgi)",
            code="LOGIN_INVALID_SHAPE",
        )

    first_name = _text_field(
        str(body.get("first_name") or ""),
        low=NAME_MIN,
        high=NAME_MAX,
        code="NAME_INVALID",
        label="Ism",
    )
    club_name = _text_field(
        str(body.get("club_name") or ""),
        low=ORG_MIN,
        high=ORG_MAX,
        code="CLUB_NAME_INVALID",
        label="Klub nomi",
    )
    address = _text_field(
        str(body.get("address") or ""),
        low=ADDRESS_MIN,
        high=ADDRESS_MAX,
        code="ADDRESS_INVALID",
        label="Manzil",
    )

    phone = normalize_phone(str(body.get("phone") or ""))
    if phone is None:
        raise BadRequest("Telefon raqami +998XXXXXXXXX ko‘rinishida bo‘lsin", code="PHONE_INVALID")

    password = validate(
        str(body.get("password") or ""),
        role=OWNER_ROLE,
        login=login,
        phone=phone,
        names=(club_name, first_name),
    )

    return SignupInput(
        login=login,
        first_name=first_name,
        club_name=club_name,
        phone=phone,
        address=address,
        password=password,
    )


async def _guard_limits(ip: str | None) -> None:
    """Chegara — DB va Argon2 GACHA.

    IP noma'lum bo'lsa chegara O'TKAZIB YUBORILMAYDI. `client_ip()` ishonchsiz
    qiymatni `None` qaytaradi (masalan `X-Forwarded-For: 1.2.3.4,`), ya'ni
    «`None` → cheklovsiz» degan qoida hujumchiga bitta sarlavha bilan barcha
    IP chegaralarini o'chirish imkonini berardi. §10.5 buni nomma-nom
    taqiqlaydi: «`None` = eng qat'iy chelak, «chegarasiz» varianti
    taqiqlanadi».

    Shuning uchun noma'lum IP umumiy chelakka tushadi. Ha, u to'lib qolsa
    boshqa noma'lum IP'lar ham rad etiladi — bu ATAYLAB qabul qilingan narx:
    halol foydalanuvchining IP'si odatda ma'lum, hujumchi esa uni ataylab
    yashiradi.
    """
    bucket = ip or UNKNOWN_IP

    # Har bir oyna O'Z chelagida. Ikkalasi bitta `scope` bilan chaqirilsa
    # bitta Redis kalitini bo'lishadi va har so'rov sanagichni ikki marta
    # oshiradi — soatlik chegara amalda 3 emas, 2 ga aylanadi.
    for scope, (limit, window) in (("signup:ip:h", IP_HOUR), ("signup:ip:d", IP_DAY)):
        decision = await ratelimit.hit(scope, bucket, limit=limit, window_sec=window)
        if not decision.allowed:
            raise AppError(
                "Juda ko‘p urinish — keyinroq qayta urinib ko‘ring",
                code="RATE_LIMITED",
                status_code=429,
                details={"retry_after": decision.retry_after},
            )


async def owner_signup(session: AsyncSession, *, body: dict[str, Any], ip: str | None) -> str:
    """Tashkilot, klub, egasi va uning paroli — bitta tranzaksiyada.

    Tokenlar bu yerda BERILMAYDI: konsol darhol `/auth/staff/login` ga
    murojaat qiladi. Parolni foydalanuvchining o'zi tanlagani uchun bu
    qo'shimcha qadam emas, va sessiya ochish yo'li bitta bo'lib qoladi —
    ikkinchi token beruvchi yuza xato qilish uchun yana bir joy bo'lardi.
    """
    fields = clean(body)
    await _guard_limits(ip)

    digest = await hash_password(fields.password)

    await session.execute(
        text("SELECT set_config('app.signup_login', :login, true)"),
        {"login": fields.login},
    )
    try:
        created = await session.scalar(
            text(
                "SELECT auth_owner_signup(:login, :first_name, :org, :club,"
                " :phone, :address, :digest)"
            ),
            {
                "login": fields.login,
                "first_name": fields.first_name,
                # Tashkilot nomi hozircha klub nomi bilan bir xil: forma bitta
                # klublik egani nazarda tutadi. Ko'p klubli tashkilot uchun
                # nom keyin sozlamalarda o'zgartiriladi.
                "org": fields.club_name,
                "club": fields.club_name,
                "phone": fields.phone,
                "address": fields.address,
                "digest": digest,
            },
        )
    except Exception as exc:  # noqa: BLE001
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == "23505" and "users_login_staff_uk" in str(exc):
            raise Conflict("Bu login band — boshqasini tanlang", code="LOGIN_TAKEN") from exc
        raise

    # `finally` ATAYLAB yo'q. Xato chiqqanda tranzaksiya ABORT holatida
    # bo'ladi va undagi har qanday bayonot `InFailedSQLTransactionError`
    # beradi — ya'ni tozalash asl xatoni (`LOGIN_TAKEN`) yashirib qo'yardi.
    # Doira `SET LOCAL` bilan ochilgani uchun rollback bilan o'zi yopiladi.
    await session.execute(text("SELECT set_config('app.signup_login', '', true)"))

    if not created:
        raise AppError("Ro‘yxatdan o‘tish amalga oshmadi", code="SIGNUP_FAILED")

    await session.execute(
        text(
            "INSERT INTO auth_events (event, user_id, detail)"
            " VALUES ('owner_signup', :uid, '{}'::jsonb)"
        ),
        {"uid": created},
    )

    return fields.login
