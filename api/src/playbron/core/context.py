"""So'rov konteksti — `contextvars` orqali (Node'dagi `nestjs-cls` ning o'rnini bosadi).

Bu yerdagi qiymatlar `core.db.session_scope()` da `SET LOCAL app.*` ga aylanadi va
RLS policy'lari o'shalarni o'qiydi. Qo'lda `WHERE club_id = ...` yozilmaydi.
"""

from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(slots=True)
class RequestContext:
    request_id: str = ""
    user_id: int | None = None
    org_id: int | None = None
    club_id: int | None = None
    is_super_admin: bool = False
    roles: dict[int, str] = field(default_factory=dict)
    """club_id → rol."""

    telegram_id: int | None = None
    """Faqat kirish tranzaksiyasida to'ldiriladi.

    Foydalanuvchi hali yaratilmagan paytda `users` ga yozish uchun RLS policy'siga
    aynan shu bitta qatorni ochish kerak — `app.user_id` hali 0.
    """


# Sukut qiymat `None` — o'zgaruvchan obyekt sukut sifatida qo'yilsa u BARCHA
# so'rovlar orasida bo'lishiladi va bir so'rovning `user_id` si boshqasiga sizib
# o'tadi. Har chaqiruvda yangi nusxa qaytariladi.
_ctx: ContextVar[RequestContext | None] = ContextVar("playbron_ctx", default=None)


def current() -> RequestContext:
    ctx = _ctx.get()
    if ctx is None:
        ctx = RequestContext()
        _ctx.set(ctx)
    return ctx


def set_context(ctx: RequestContext) -> None:
    _ctx.set(ctx)


def reset() -> None:
    _ctx.set(None)


def role_in(club_id: int) -> str | None:
    return current().roles.get(club_id)
