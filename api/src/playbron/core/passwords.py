"""Parol xeshlash va tekshirish — Argon2id.

Manba: `docs/05-auth-redesign.md` §7.

Nega `passlib` emas: 2020 dan beri faol rivojlanmayapti va bcrypt 4.x bilan
mos kelmaslik muammosi bor. Nega `bcrypt` emas: parolni 72 baytda kesadi.

Xesh PHC satri sifatida saqlanadi va o'zini tavsiflaydi — kelajakda
parametrlarni ko'tarib `check_needs_rehash()` bilan jimgina qayta xeshlash
mumkin.
"""

import unicodedata
from typing import Final

import anyio
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from playbron.core.errors import BadRequest

# OWASP ning ikkinchi tavsiya etilgan konfiguratsiyasi: m=19 MiB, t=2, p=1.
# Kutubxona sukuti (64 MiB, p=4) Render'ning 512 MB instansiyasida bir necha
# parallel kirishda OOM beradi.
_hasher: Final = PasswordHasher(
    type=Type.ID,
    memory_cost=19_456,
    time_cost=2,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# Argon2 — ataylab qimmat va bloklovchi amal. Chegarasiz qoldirilsa
# autentifikatsiyasiz OOM va API ning qayta ishga tushish sikli kelib chiqadi:
# 4 × 19 MiB = 76 MiB shift (§6.4).
_limiter: Final = anyio.CapacityLimiter(4)

MAX_LENGTH: Final = 128

# Rol bo'yicha minimal uzunlik. Konsolda pul va mijoz PII si turadi, shuning
# uchun 8 belgi bu yuza uchun past (§7.2).
MIN_LENGTH: Final[dict[str, int]] = {
    "STAFF": 12,
    "ADMIN": 12,
    "OWNER": 14,
    "SUPER_ADMIN": 16,
}
DEFAULT_MIN_LENGTH: Final = 12

# To'liq ro'yxat emas — eng ko'p uchraydigan va o'zbekcha xoslari.
# [TEKSHIRISH] ~10 000 tali sizib chiqqan parollar ro'yxati alohida faylga
# qo'shiladi; hozircha bu tekshiruv faqat eng qo'pol holatlarni ushlaydi.
_COMMON: Final[frozenset[str]] = frozenset(
    {
        "password",
        "parol",
        "parol123",
        "playbron",
        "qwerty",
        "qwerty123",
        "123456",
        "1234567",
        "12345678",
        "123456789",
        "1234567890",
        "admin",
        "admin123",
        "administrator",
        "welcome",
        "iloveyou",
        "letmein",
        "monkey",
        "dragon",
        "football",
        "abc123",
        "111111",
        "000000",
        "121212",
        "zaqwsx",
        "asdfgh",
        "qazwsx",
        "superadmin",
        "toshkent",
        "uzbekistan",
        "salom",
        "playstation",
        "playstation5",
    }
)


def normalize(raw: str) -> str:
    """NFKC + faqat chetlarini trim.

    Ichkaridagi bo'shliq parolning qismi — u olib tashlanmaydi.
    """
    return unicodedata.normalize("NFKC", raw).strip()


def validate(
    raw: str,
    *,
    role: str = "STAFF",
    login: str | None = None,
    phone: str | None = None,
    names: tuple[str, ...] = (),
) -> str:
    """Normallashtirilgan parolni qaytaradi yoki `BadRequest` ko'taradi.

    Tarkib qoidalari (bosh harf, raqam, belgi) ATAYLAB yo'q — ular parolni
    bashoratli qiladi (`Parol1!`). O'rniga uzunlik va qora ro'yxat.

    Rad etilganda SABABI aytiladi: «parol mos emas» degan javob foydalanuvchini
    tasodifiy urinishlarga majburlaydi.
    """
    password = normalize(raw)
    minimum = MIN_LENGTH.get(role, DEFAULT_MIN_LENGTH)

    if len(password) < minimum:
        raise BadRequest(
            f"Parol kamida {minimum} belgi bo‘lishi kerak",
            code="PASSWORD_TOO_SHORT",
        )

    if len(password) > MAX_LENGTH:
        raise BadRequest(
            f"Parol {MAX_LENGTH} belgidan uzun bo‘lmasin",
            code="PASSWORD_TOO_LONG",
        )

    lowered = password.casefold()

    if lowered in _COMMON:
        raise BadRequest(
            "Bu parol juda ko‘p ishlatiladi — boshqasini tanlang",
            code="PASSWORD_TOO_COMMON",
        )

    if login and lowered == login.casefold():
        raise BadRequest("Parol login bilan bir xil bo‘lmasin", code="PASSWORD_IS_LOGIN")

    if phone and _digits(password) and _digits(password) == _digits(phone):
        raise BadRequest("Parol telefon raqami bilan bir xil bo‘lmasin", code="PASSWORD_IS_PHONE")

    for name in names:
        if name and lowered == name.casefold():
            raise BadRequest(
                "Parol klub yoki tashkilot nomi bilan bir xil bo‘lmasin",
                code="PASSWORD_IS_NAME",
            )

    return password


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


async def hash_password(raw: str) -> str:
    """Argon2id PHC satri. Salt kutubxona tomonidan har xeshda yangi."""
    return await anyio.to_thread.run_sync(_hasher.hash, normalize(raw), limiter=_limiter)


async def verify_password(password_hash: str, raw: str) -> bool:
    """Mos kelishini tekshiradi. Xato xesh ham `False` — istisno chiqmaydi."""

    def _check() -> bool:
        try:
            return _hasher.verify(password_hash, normalize(raw))
        except (VerifyMismatchError, InvalidHashError):
            return False

    return await anyio.to_thread.run_sync(_check, limiter=_limiter)


def needs_rehash(password_hash: str) -> bool:
    """Parametrlar ko'tarilgan bo'lsa — keyingi muvaffaqiyatli kirishda qayta xeshlanadi."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


# Hisob topilmaganda ham xuddi shuncha vaqt ketishi uchun: aks holda javob
# vaqtining o'zi «bunday login bor» degan orakulga aylanadi.
DUMMY_HASH: Final = _hasher.hash("playbron-dummy-password-for-timing")


async def waste_time() -> None:
    """Login topilmagan yo'lda chaqiriladi — vaqt profili bir xil qolsin."""
    await verify_password(DUMMY_HASH, "definitely-not-the-password")
