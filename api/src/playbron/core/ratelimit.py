"""So'rov chegaralari — Redis'dagi sanagich.

Manba: `docs/05-auth-redesign.md` §10.

Ikki narsa ataylab QILINMAYDI:

1. **Hisob qulflanmaydi.** `locked_until` yo'q. Login sir emas (konsolda ustun
   sifatida ko'rinadi), ya'ni qulf istalgan odam qo'lidagi maqsadli DoS quroli
   bo'lardi: 19:00 da har bir loginga besh dona axlat parol yuborilsa butun
   klub ishlamay qolardi. Chegaradan oshgan urinish faqat **kechikish** oladi
   va u vaqt bilan o'zi so'nadi.

2. **Global tripwire yo'q.** «Daqiqasiga >200 muvaffaqiyatsizlik → hammaga
   step-up» qoidasi rad etilgan: 250 IP dan bittadan so'rov per-IP va per-login
   chegaralarining birortasini ishga tushirmaydi, lekin global hisoblagichni
   oshiradi — ya'ni bitta hujumchi butun platformani o'chiradigan tugmaga ega
   bo'lardi.
"""

from dataclasses import dataclass
from typing import Final

from playbron.core.redis import redis_client

PREFIX: Final = "rl:"

# Hisob bo'yicha eksponensial kechikish. Qulf emas — 670 taxmin/kun ni ~50 ga
# tushiradi va halol foydalanuvchini deyarli bezovta qilmaydi (§6.3).
DELAY_LADDER: Final[tuple[float, ...]] = (0.0, 1.0, 4.0, 16.0)
DELAY_MAX: Final = 16.0


@dataclass(slots=True, frozen=True)
class Decision:
    allowed: bool
    retry_after: int


async def hit(scope: str, key: str, *, limit: int, window_sec: int) -> Decision:
    """Belgilangan oynadagi sanagich.

    Birinchi urinishda TTL o'rnatiladi va keyin uzaytirilmaydi — ya'ni oyna
    surilib ketmaydi va chegara vaqt bilan aniq so'nadi.
    """
    redis = redis_client()
    full = f"{PREFIX}{scope}:{key}"

    current = await redis.incr(full)
    if current == 1:
        await redis.expire(full, window_sec)

    if current <= limit:
        return Decision(allowed=True, retry_after=0)

    ttl = await redis.ttl(full)
    return Decision(allowed=False, retry_after=max(int(ttl), 1))


async def failure_delay(scope: str, key: str, *, window_sec: int) -> float:
    """Muvaffaqiyatsiz urinishni hisoblaydi va navbatdagi kechikishni qaytaradi.

    Qaytadigan qiymat — **shu urinish uchun** kechikish, ya'ni birinchi xatoda 0.
    """
    redis = redis_client()
    full = f"{PREFIX}{scope}:fail:{key}"

    # `int(...)` — yangi redis stub'lari `incr` uchun Any qaytaradi
    count = int(await redis.incr(full))
    if count == 1:
        await redis.expire(full, window_sec)

    index = min(count - 1, len(DELAY_LADDER) - 1)
    return DELAY_LADDER[index]


async def clear_failures(scope: str, key: str) -> None:
    """Muvaffaqiyatli kirishdan keyin — kechikish zinapoyasi nolga qaytadi."""
    await redis_client().delete(f"{PREFIX}{scope}:fail:{key}")
