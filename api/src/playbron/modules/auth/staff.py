"""Xodim kirishi — login + parol.

Manba: `docs/05-auth-redesign.md` §6.

Qadamlar tartibi ATAYLAB shunday va o'zgartirilmaydi:

  1. login normallashtiriladi — **chegaralagichdan oldin** (§6.2)
  2. chegaralar — **DB va Argon2 gacha**
  3. `auth_lookup_staff` — SECURITY DEFINER, tor tuple
  4. hisob topilmasa ham parol dummy xeshga qarshi tekshiriladi
  5. Argon2 chegaralangan hovuzda
  6. har qanday muvaffaqiyatsizlikda **aynan bir xil** 401
"""

import asyncio
import unicodedata
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context, ratelimit
from playbron.core.db import set_current_user
from playbron.core.errors import AppError, Unauthorized
from playbron.core.passwords import (
    hash_password,
    needs_rehash,
    validate,
    verify_password,
    waste_time,
)
from playbron.core.security import AUDIENCE_STAFF, sha256_hex
from playbron.models import User
from playbron.modules.auth import service

LOGIN_MIN: Final = 3
LOGIN_MAX: Final = 32
_ALLOWED: Final = frozenset("abcdefghijklmnopqrstuvwxyz0123456789._-")

# §10.1
IP_LIMIT: Final = (10, 900)  # 10 / 15 daq
LOGIN_LIMIT: Final = (8, 900)  # 8 / 15 daq
IP_LOGIN_LIMIT: Final = (5, 300)  # 5 / 5 daq
FAIL_WINDOW: Final = 900


def normalize_login(raw: str) -> str | None:
    """NFKC → casefold → trim → shakl tekshiruvi. Mos kelmasa `None`.

    Tartib muhim: NFKC fullwidth `ｋ` ni `k` ga, Kelvin belgisi `K` ni `K` ga
    keltiradi, casefold esa kichik harfga. Ikkalasisiz `kassa01`, `KASSA01`,
    `ｋassa01` va Kelvinli variant HAR BIRI alohida chegara byudjeti olardi —
    per-hisob chegara amalda cheksiz aylanardi (§6.2).
    """
    folded = unicodedata.normalize("NFKC", raw).casefold().strip()
    if not (LOGIN_MIN <= len(folded) <= LOGIN_MAX):
        return None
    if not set(folded) <= _ALLOWED:
        return None
    return folded


def _reject() -> Unauthorized:
    """Yagona javob shakli.

    Hisob yo'q, parol xato, `status != 'active'` — uchalasi ham AYNAN shu
    javobni oladi. Farqli javob hisob sanash orakuliga aylanadi.
    """
    return Unauthorized("Login yoki parol noto‘g‘ri", code="LOGIN_INVALID")


async def _guard_limits(login_hash: str, ip: str | None) -> None:
    """Chegaralar — DB va Argon2 GACHA."""
    checks = [
        ratelimit.hit("login:acct", login_hash, limit=LOGIN_LIMIT[0], window_sec=LOGIN_LIMIT[1]),
    ]
    if ip:
        checks.append(ratelimit.hit("login:ip", ip, limit=IP_LIMIT[0], window_sec=IP_LIMIT[1]))
        checks.append(
            ratelimit.hit(
                "login:ip-acct",
                f"{ip}:{login_hash}",
                limit=IP_LOGIN_LIMIT[0],
                window_sec=IP_LOGIN_LIMIT[1],
            )
        )

    for decision in [await check for check in checks]:
        if not decision.allowed:
            raise AppError(
                "Juda ko‘p urinish — biroz kuting",
                code="RATE_LIMITED",
                status_code=429,
                details={"retry_after": decision.retry_after},
            )


async def _lookup(session: AsyncSession, normalized: str) -> Any:
    """`auth_lookup_staff` — `app.login` doirasi ochilgan holda.

    Kirish paytida `app.user_id` hali 0, ya'ni `users_self` policy'si hech
    qanday qatorni ochmaydi va funksiya BO'SH qaytaradi. `app.login` aynan
    shu bitta loginli xodim qatorini ochadi (`0007` dagi `users_login_probe`).
    Bu mijoz kirishidagi `app.telegram_id` va token almashtirishdagi
    `app.refresh_hash` bilan bir xil naqsh.

    Doira darhol yopiladi: bir tranzaksiyada keyin ketadigan so'rovlar
    begona qatorni ko'rmasin.
    """
    await session.execute(
        text("SELECT set_config('app.login', :login, true)"), {"login": normalized}
    )
    row = (
        await session.execute(
            text(
                "SELECT user_id, password_hash, status, must_change FROM auth_lookup_staff(:login)"
            ),
            {"login": normalized},
        )
    ).first()
    await session.execute(text("SELECT set_config('app.login', '', true)"))
    return row


async def staff_login(
    session: AsyncSession,
    *,
    login: str,
    password: str,
    user_agent: str | None = None,
    ip: str | None = None,
) -> dict[str, Any]:
    """Login + parol bilan sessiya ochadi."""
    normalized = normalize_login(login)
    if normalized is None:
        # Shakl mos emas: bucket ochilmaydi, DB'ga tegilmaydi — aks holda
        # istalgan axlat satr chegara byudjetini yeb qo'yardi
        raise _reject()

    login_hash = sha256_hex(normalized)
    await _guard_limits(login_hash, ip)

    row = await _lookup(session, normalized)

    # Hisob topilmasa ham vaqt profili bir xil qolishi kerak
    if row is None:
        await waste_time()
        delay = await ratelimit.failure_delay("login", login_hash, window_sec=FAIL_WINDOW)
        await asyncio.sleep(delay)
        raise _reject()

    user_id, password_hash, status, must_change = row

    ok = await verify_password(password_hash, password)

    if not ok or status != "active":
        # `status` sababli rad etishda ham AYNAN o'sha javob va o'sha kechikish
        delay = await ratelimit.failure_delay("login", login_hash, window_sec=FAIL_WINDOW)
        await asyncio.sleep(delay)
        await session.execute(text("SELECT auth_touch_login(:uid, false)"), {"uid": user_id})
        raise _reject()

    await ratelimit.clear_failures("login", login_hash)
    await session.execute(text("SELECT auth_touch_login(:uid, true)"), {"uid": user_id})

    # Parametrlar ko'tarilgan bo'lsa xesh jimgina qayta yoziladi —
    # PHC satri o'zini tavsiflagani uchun eski xesh ham ishlayveradi
    if needs_rehash(password_hash):
        await session.execute(
            text("SELECT auth_assign_password(:uid, :h)"),
            {"uid": user_id, "h": await hash_password(password)},
        )

    # RLS konteksti FAQAT shu yerda ochiladi. `app.telegram_id` xodim oqimida
    # hech qachon o'rnatilmaydi — u mijoz dunyosining kaliti.
    await set_current_user(session, user_id)
    ctx = context.current()
    ctx.user_id = user_id
    context.set_context(ctx)

    user = await session.get(User, user_id)
    if user is None:
        raise _reject()

    super_admin = await service.is_super_admin(session, user_id)
    memberships = await service.load_memberships(session, user_id)
    org_id = memberships[0]["org_id"] if memberships else None
    entitlements = await service.load_entitlements(session, org_id)

    issued = await service.issue_tokens(
        session,
        user=user,
        memberships=memberships,
        super_admin=super_admin,
        entitlements=entitlements,
        audience=AUDIENCE_STAFF,
        user_agent=user_agent,
        ip=ip,
    )

    return {
        **issued,
        "user": user,
        "memberships": memberships,
        "is_super_admin": super_admin,
        # `true` bo'lsa konsol faqat parol almashtirish ekranini ochadi (§7.3)
        "must_change_password": bool(must_change),
    }


async def change_password(
    session: AsyncSession,
    *,
    user_id: int,
    current: str,
    new_password: str,
    role: str,
    login: str | None,
) -> None:
    """O'z parolini almashtirish.

    Joriy parol MAJBURIY: sessiyasi o'g'irlangan hujumchi parolni jimgina
    almashtirib, haqiqiy egasini butunlay chiqarib yuborolmasin (§7.3).
    """
    row = await _lookup(session, login or "")

    if row is None or int(row[0]) != int(user_id):
        raise _reject()

    if not await verify_password(row[1], current):
        delay = await ratelimit.failure_delay("pwchange", str(user_id), window_sec=FAIL_WINDOW)
        await asyncio.sleep(delay)
        raise _reject()

    validated = validate(new_password, role=role, login=login)
    if await verify_password(row[1], validated):
        raise AppError(
            "Yangi parol eskisi bilan bir xil", code="PASSWORD_UNCHANGED", status_code=400
        )

    changed = await session.scalar(
        text("SELECT auth_change_password(:h)"), {"h": await hash_password(validated)}
    )
    if not changed:
        raise _reject()

    await ratelimit.clear_failures("pwchange", str(user_id))
