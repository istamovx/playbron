"""Telegram imzosini tekshirish testlari.

⚠️ Bu testlar kodning **o'zi bilan izchilligini** tekshiradi: fixture xuddi shu
formula bilan yasaladi. Ular Telegram bilan mosligini **isbotlamaydi**.

Ishlab chiqarishga chiqishdan oldin `test_real_initdata_sample` ga haqiqiy
Mini App'dan olingan `initData` qo'yilishi va u o'tishi shart.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest

from playbron.core.errors import Unauthorized
from playbron.modules.auth import telegram as tg

BOT_TOKEN = "123456:TEST-TOKEN"  # noqa: S105
# Login Widget admin bot bilan ishlaydi — konsol mijoz oqimidan ajratilgan
ADMIN_BOT_TOKEN = "654321:ADMIN-TOKEN"  # noqa: S105


@pytest.fixture(autouse=True)
def _bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tg.settings.bot_token, "get_secret_value", lambda: BOT_TOKEN)
    monkeypatch.setattr(
        tg.settings.admin_bot_token, "get_secret_value", lambda: ADMIN_BOT_TOKEN
    )


def _sign_init_data(fields: dict[str, str]) -> str:
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode({**fields, "hash": signature})


def _sign_widget(fields: dict[str, str]) -> dict[str, str]:
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hashlib.sha256(ADMIN_BOT_TOKEN.encode()).digest()
    signature = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return {**fields, "hash": signature}


def _user_field(telegram_id: int = 777) -> str:
    return json.dumps(
        {"id": telegram_id, "first_name": "Jasur", "username": "jasur", "language_code": "uz"},
        separators=(",", ":"),
    )


# ── initData ──────────────────────────────────────────────────────────────


def test_init_data_valid() -> None:
    raw = _sign_init_data(
        {"user": _user_field(), "auth_date": str(int(time.time())), "query_id": "AAE"}
    )
    identity = tg.verify_init_data(raw)

    assert identity.telegram_id == 777
    assert identity.first_name == "Jasur"
    assert identity.source == "initdata"


def test_init_data_tampered_field_rejected() -> None:
    raw = _sign_init_data({"user": _user_field(), "auth_date": str(int(time.time()))})
    tampered = raw.replace("Jasur", "Botir")

    with pytest.raises(Unauthorized) as err:
        tg.verify_init_data(tampered)
    assert err.value.code == "INITDATA_BAD_SIGNATURE"


def test_init_data_wrong_bot_token_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _sign_init_data({"user": _user_field(), "auth_date": str(int(time.time()))})
    monkeypatch.setattr(tg.settings.bot_token, "get_secret_value", lambda: "999:OTHER")

    with pytest.raises(Unauthorized):
        tg.verify_init_data(raw)


def test_init_data_expired_rejected() -> None:
    old = int(time.time()) - tg.settings.initdata_ttl_sec - 60
    raw = _sign_init_data({"user": _user_field(), "auth_date": str(old)})

    with pytest.raises(Unauthorized) as err:
        tg.verify_init_data(raw)
    assert err.value.code == "AUTH_DATE_EXPIRED"


def test_init_data_future_date_rejected() -> None:
    future = int(time.time()) + 600
    raw = _sign_init_data({"user": _user_field(), "auth_date": str(future)})

    with pytest.raises(Unauthorized) as err:
        tg.verify_init_data(raw)
    assert err.value.code == "AUTH_DATE_INVALID"


def test_init_data_without_hash_rejected() -> None:
    raw = urlencode({"user": _user_field(), "auth_date": str(int(time.time()))})

    with pytest.raises(Unauthorized) as err:
        tg.verify_init_data(raw)
    assert err.value.code == "INITDATA_NO_HASH"


def test_init_data_empty_rejected() -> None:
    with pytest.raises(Unauthorized) as err:
        tg.verify_init_data("")
    assert err.value.code == "INITDATA_MISSING"


# ── Login Widget ──────────────────────────────────────────────────────────


def test_widget_valid() -> None:
    payload = _sign_widget(
        {"id": "777", "first_name": "Jasur", "auth_date": str(int(time.time()))}
    )
    identity = tg.verify_widget(payload)

    assert identity.telegram_id == 777
    assert identity.source == "widget"


def test_widget_tampered_rejected() -> None:
    payload = _sign_widget(
        {"id": "777", "first_name": "Jasur", "auth_date": str(int(time.time()))}
    )
    payload["id"] = "888"

    with pytest.raises(Unauthorized) as err:
        tg.verify_widget(payload)
    assert err.value.code == "WIDGET_BAD_SIGNATURE"


def test_widget_uses_admin_bot_not_main_bot() -> None:
    """Widget asosiy bot tokeni bilan imzolangan bo'lsa qabul qilinmaydi."""
    fields = {"id": "777", "first_name": "Jasur", "auth_date": str(int(time.time()))}
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    wrong = hmac.new(
        hashlib.sha256(BOT_TOKEN.encode()).digest(), check.encode(), hashlib.sha256
    ).hexdigest()

    with pytest.raises(Unauthorized) as err:
        tg.verify_widget({**fields, "hash": wrong})
    assert err.value.code == "WIDGET_BAD_SIGNATURE"


def test_widget_and_initdata_use_different_keys() -> None:
    """Ikki kanal kaliti bir xil bo'lsa — biri ikkinchisining imzosini qabul qilardi."""
    fields = {"id": "777", "first_name": "Jasur", "auth_date": str(int(time.time()))}
    widget = _sign_widget(fields)

    # Widget imzosini initData sifatida uzatib ko'ramiz
    as_init = urlencode({**fields, "user": _user_field(), "hash": widget["hash"]})

    with pytest.raises(Unauthorized):
        tg.verify_init_data(as_init)


@pytest.mark.skip(reason="Haqiqiy initData namunasi qo'yilgach yoqiladi — [TEKSHIRISH]")
def test_real_initdata_sample() -> None:
    """Telegram'dan olingan haqiqiy namuna.

    Bajarish tartibi:
      1. Mini App'ni ochib `window.Telegram.WebApp.initData` ni ko'chirib oling
      2. `BOT_TOKEN` ni shu botning tokeniga almashtiring
      3. `skip` ni olib tashlang va testni yugurting

    Bu o'tmaguncha auth ishlab chiqarishga chiqarilmaydi.
    """
    raise AssertionError("Namuna qo'yilmagan")
