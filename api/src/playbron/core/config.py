"""Ilova sozlamalari — hammasi env'dan, kod ichida sir yo'q."""

import re
from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _with_driver(url: str, driver: str) -> str:
    """Ulanish satriga drayverni qo'yadi.

    Hosting provayderlari (Render, Heroku, Railway) `postgres://` yoki
    `postgresql://` beradi — SQLAlchemy'ga esa aniq drayver kerak. Qo'lda
    to'g'rilash o'rniga shu yerda normallashtiriladi.
    """
    if not url:
        return url
    if "+" in url.split("://", 1)[0]:
        return url
    return re.sub(r"^postgres(ql)?://", f"postgresql+{driver}://", url)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Sukut qiymat ATAYLAB eng qat'iy: `ENV` unutilsa ilova prod deb hisoblaydi va
    # zaif sozlama bilan ishga tushmaydi. Aks holda konteyner ENV'siz deploy bo'lsa
    # barcha prod tekshiruvlari jimgina o'chib qolardi.
    env: str = "prod"
    debug: bool = False

    # ── Ma'lumotlar bazasi ────────────────────────────────────────────────
    # Ilova RLS ostidagi rol bilan ulanadi
    database_url: str = "postgresql+asyncpg://playbron_app:app@localhost:5432/playbron"
    # Migratsiya va seed — egasi roli (RLS'ni chetlab o'tadi)
    direct_url: str = "postgresql+psycopg://playbron:playbron@localhost:5432/playbron"
    # Super admin cross-tenant o'qishi — BYPASSRLS roli
    platform_database_url: str = (
        "postgresql+asyncpg://playbron_platform:platform@localhost:5432/playbron"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 5

    @field_validator("database_url", "platform_database_url")
    @classmethod
    def _async_driver(cls, value: str) -> str:
        return _with_driver(value, "asyncpg")

    @field_validator("direct_url")
    @classmethod
    def _sync_driver(cls, value: str) -> str:
        return _with_driver(value, "psycopg")

    redis_url: str = "redis://localhost:6379/0"

    # ── Telegram ──────────────────────────────────────────────────────────
    bot_token: SecretStr = SecretStr("")
    admin_bot_token: SecretStr = SecretStr("")
    tg_webhook_secret: SecretStr = SecretStr("")

    # initData qisqa yashaydi — Mini App har ochilishda yangisini beradi
    initdata_ttl_sec: int = 300
    # Login Widget cookie'da uzoq yashaydi
    widget_ttl_sec: int = 86_400

    # ── Sessiya ───────────────────────────────────────────────────────────
    # Sukut qiymat YO'Q: repo'da turgan ochiq sir bilan token imzolash imkoniyati
    # butunlay yopiladi. `JWT_SECRET` bo'lmasa ilova ishga tushmaydi.
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_ttl_sec: int = 900  # 15 daqiqa
    refresh_ttl_sec: int = 2_592_000  # 30 kun
    # Super admin uchun qisqaroq
    sa_access_ttl_sec: int = 600
    sa_refresh_ttl_sec: int = 28_800  # 8 soat

    # ── Biznes qoidalari ──────────────────────────────────────────────────
    # Obuna muddati tugagach klub qancha kun ishlashda davom etadi
    grace_days: int = 3
    # Tugashiga necha kun qolganda ogohlantiriladi
    subscription_warn_days: int = 3

    # ── Super admin ───────────────────────────────────────────────────────
    # Seed uchun: vergul bilan ajratilgan telegram_id lar
    super_admin_telegram_ids: str = ""
    # /platform/* uchun IP allowlist (bo'sh — cheklovsiz, prod'da to'ldiriladi)
    platform_ip_allowlist: str = ""

    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    @property
    def super_admin_ids(self) -> list[int]:
        raw = self.super_admin_telegram_ids.strip()
        if not raw:
            return []
        return [int(part) for part in raw.split(",") if part.strip()]

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def platform_ips(self) -> list[str]:
        raw = self.platform_ip_allowlist.strip()
        return [ip.strip() for ip in raw.split(",") if ip.strip()] if raw else []


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# HMAC-SHA256 uchun kalit kamida 32 bayt bo'lishi kerak (RFC 7518 §3.2).
MIN_JWT_SECRET_BYTES = 32
LOCAL_ENVS = {"local", "test"}

_jwt_secret = settings.jwt_secret.get_secret_value()
_is_local = settings.env in LOCAL_ENVS

if not _jwt_secret:
    raise RuntimeError("JWT_SECRET bo‘sh bo‘lmasligi kerak")

if len(_jwt_secret.encode()) < MIN_JWT_SECRET_BYTES:
    message = (
        f"JWT_SECRET {len(_jwt_secret.encode())} bayt — kamida {MIN_JWT_SECRET_BYTES} kerak. "
        "Yangilash: openssl rand -hex 32"
    )
    # Faqat ENV ochiq-oydin `local`/`test` bo'lsagina ogohlantirish bilan cheklanamiz.
    # Boshqa har qanday holatda (jumladan ENV umuman yo'q) — ishga tushmaydi.
    if not _is_local:
        raise RuntimeError(message)

    import warnings

    warnings.warn(message, stacklevel=2)

if not _is_local:
    if not settings.bot_token.get_secret_value():
        raise RuntimeError("BOT_TOKEN prod uchun majburiy")
    if not settings.admin_bot_token.get_secret_value():
        # Konsol Login Widget'i admin bot bilan imzolanadi. Token bo'lmasa
        # telegram.py asosiy botga qaytadi va imzo hech qachon mos kelmaydi —
        # har bir kirish urinishi 401 WIDGET_BAD_SIGNATURE bilan tugaydi.
        raise RuntimeError("ADMIN_BOT_TOKEN prod uchun majburiy")
    if not settings.tg_webhook_secret.get_secret_value():
        raise RuntimeError("TG_WEBHOOK_SECRET prod uchun majburiy")
    if settings.debug:
        # `debug` SQL echo'ni yoqadi — parametrlar (PII, token xeshlari) log'ga tushadi
        raise RuntimeError("DEBUG prod'da yoqilgan bo‘lmasligi kerak")
    if any("localhost" in origin or "127.0.0.1" in origin for origin in settings.cors_origin_list):
        raise RuntimeError("CORS_ORIGINS prod uchun sozlanmagan (localhost qolgan)")

__all__ = ["Settings", "get_settings", "settings", "Field"]
