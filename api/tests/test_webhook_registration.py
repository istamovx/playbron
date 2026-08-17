"""Start'da webhook ro'yxatdan o'tkazish — «ikkala yuza bitta bot» holati.

Telegram'da webhook BOTGA tegishli va bitta bot uchun BITTA URL bo'ladi.
`BOT_TOKEN` va `ADMIN_BOT_TOKEN` bir xil bo'lsa ikkinchi `setWebhook`
birinchisini jimgina bosib ketardi — Telegram xato bermaydi, log'da ham
hech nima qolmaydi, tashqaridan esa bu «bot javob bermayapti» bo'lib
ko'rinadi (`docs/HOLAT.md`).

Bazaga ham, tarmoqqa ham chiqilmaydi: faqat `register_webhooks()` qaysi
chaqiruvni qilgani tekshiriladi.
"""

import logging

import pytest

from playbron.core.config import settings
from playbron.main import register_webhooks
from playbron.modules.auth import botlogin
from playbron.modules.bot import router as bot_router_setup

pytestmark = pytest.mark.asyncio

PUBLIC_URL = "https://api.playbron.uz"
CUSTOMER_TOKEN = "111:mijoz-bot-tokeni"  # noqa: S105
ADMIN_TOKEN = "222:admin-bot-tokeni"  # noqa: S105


@pytest.fixture
def calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Ro'yxatdan o'tkazish chaqiruvlari shu ro'yxatga tushadi."""
    seen: list[str] = []

    async def fake_admin(public_url: str) -> None:
        seen.append(f"admin:{public_url}")

    async def fake_customer(public_url: str) -> None:
        seen.append(f"customer:{public_url}")

    monkeypatch.setattr(botlogin, "register_webhook", fake_admin)
    monkeypatch.setattr(bot_router_setup, "register_customer_webhook", fake_customer)
    return seen


def _tokens(monkeypatch: pytest.MonkeyPatch, *, customer: str, admin: str) -> None:
    monkeypatch.setattr(settings.bot_token, "get_secret_value", lambda: customer)
    monkeypatch.setattr(settings.admin_bot_token, "get_secret_value", lambda: admin)


async def test_different_bots_register_both(
    monkeypatch: pytest.MonkeyPatch, calls: list[str]
) -> None:
    """Odatdagi (to'g'ri sozlangan) holat — ikkala webhook ham o'rnatiladi."""
    _tokens(monkeypatch, customer=CUSTOMER_TOKEN, admin=ADMIN_TOKEN)

    await register_webhooks(PUBLIC_URL)

    assert calls == [f"admin:{PUBLIC_URL}", f"customer:{PUBLIC_URL}"]


async def test_same_bot_keeps_customer_and_skips_admin(
    monkeypatch: pytest.MonkeyPatch, calls: list[str], caplog: pytest.LogCaptureFixture
) -> None:
    """Bitta token — admin webhook'i O'TKAZIB YUBORILADI, mijoznikisi qoladi.

    Mijoz boti tanlanadi, chunki konsolga parol bilan ham kirish mumkin,
    mijozda esa botdan boshqa yo'l yo'q. Muhimi — qaysi yuza tirik qolgani
    chaqiruvlar tartibi yoki tarmoq xatosiga qoldirilmaydi.
    """
    _tokens(monkeypatch, customer=CUSTOMER_TOKEN, admin=CUSTOMER_TOKEN)

    with caplog.at_level(logging.ERROR, logger="playbron"):
        await register_webhooks(PUBLIC_URL)

    assert calls == [f"customer:{PUBLIC_URL}"]
    assert "ADMIN_BOT_TOKEN" in caplog.text


async def test_admin_token_missing_falls_back_and_is_treated_as_same_bot(
    monkeypatch: pytest.MonkeyPatch, calls: list[str]
) -> None:
    """`ADMIN_BOT_TOKEN` bo'sh bo'lsa `admin_token()` `BOT_TOKEN` ga tushadi.

    Prod'da bunday konfiguratsiya `core/config.py` da to'xtatiladi, lekin
    qaytish yo'li borligicha qolyapti (lokal ishlash uchun) — shuning uchun
    bu yerda ham xuddi bitta bot kabi qaraladi, ya'ni bosib ketish
    boshqa hech qanday muhitda ham yuz bermaydi.
    """
    _tokens(monkeypatch, customer=CUSTOMER_TOKEN, admin="")

    await register_webhooks(PUBLIC_URL)

    assert calls == [f"customer:{PUBLIC_URL}"]
