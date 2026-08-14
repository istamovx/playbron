"""Token va kriptografiya yordamchilari."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from playbron.core.config import settings
from playbron.core.errors import Unauthorized


def now() -> datetime:
    return datetime.now(UTC)


def constant_time_equal(left: str, right: str) -> bool:
    """Imzo solishtirish — vaqt bo'yicha sizib chiqmasin."""
    return hmac.compare_digest(left, right)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_refresh_token() -> str:
    """Opaque refresh token. DB'da faqat xeshi saqlanadi."""
    return secrets.token_urlsafe(48)


AUDIENCE_CUSTOMER = "customer"
AUDIENCE_STAFF = "staff"
AUDIENCES = (AUDIENCE_CUSTOMER, AUDIENCE_STAFF)


def encode_access(
    *,
    user_id: int,
    memberships: list[dict[str, Any]],
    is_super_admin: bool,
    audience: str,
    entitlements: dict[str, Any] | None = None,
    ttl_sec: int | None = None,
) -> tuple[str, datetime]:
    ttl = ttl_sec or (settings.sa_access_ttl_sec if is_super_admin else settings.access_ttl_sec)
    expires_at = now() + timedelta(seconds=ttl)

    if audience not in AUDIENCES:
        raise ValueError(f"Noma'lum audience: {audience!r}")

    payload: dict[str, Any] = {
        "sub": str(user_id),
        # Qaysi dunyoga tegishli. Tekshiruv `jwt.decode(audience=...)` da —
        # qo'lda `if knd == 'staff'` yozilmaydi, chunki teskari yozilgan shart
        # da'vosi yo'q tokenni xodim deb qabul qilardi (§6.6).
        "aud": audience,
        "mbr": memberships,
        "sa": is_super_admin,
        "iat": int(now().timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(12),
    }
    if entitlements:
        payload["ent"] = entitlements

    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return token, expires_at


def decode_access(token: str) -> dict[str, Any]:
    try:
        # `require` — klaym yo'q bo'lsa pyjwt o'zi rad etadi (fail-closed).
        # `audience` ro'yxat: ikkala dunyo ham yaroqli, farqi `require_staff_token`
        # da tekshiriladi.
        return jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=list(AUDIENCES),
            options={"require": ["exp", "sub", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise Unauthorized("Sessiya muddati tugadi", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise Unauthorized("Token yaroqsiz", code="TOKEN_INVALID") from exc
