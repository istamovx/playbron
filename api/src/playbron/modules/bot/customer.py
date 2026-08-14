"""Mijoz boti — `/start` → ism → telefon → Mini App.

Manba: `docs/05-auth-redesign.md` §4.

Ikki qoida butun modul bo'ylab amal qiladi:

1. **Webhook hech qachon 4xx/5xx qaytarmaydi.** Bitta noto'g'ri update
   Telegram navbatini to'xtatsa, BUTUN mijoz ro'yxatdan o'tish oqimi o'ladi.
   Xato ichkarida log'ga va `auth_events` ga yoziladi.

2. **FSM faqat kesh.** Haqiqiy manba — Postgres: qator yo'q → ism so'raladi,
   `phone_verified_at IS NULL` → telefon so'raladi, aks holda Mini App tugmasi.
   Redis o'chsa oqim buzilmaydi. Mijoz oqimida bu fail-open **maqbul**: hech
   qanday huquq berilmaydi (parol va OTP yo'llarida esa fail-closed).
"""

import json
import logging
from typing import Any, Final

from sqlalchemy import text as sql

from playbron.core import telegram_api
from playbron.core.config import settings
from playbron.core.db import AppSession, set_telegram_scope
from playbron.core.redis import redis_client
from playbron.core.text import clean_name
from playbron.modules.bot import contact as contact_check

log = logging.getLogger("playbron.bot.customer")

# Bir kunlik oyna: odam botni ochib telefonini keyinroq ulashishi normal,
# undan uzog'i yarim tashlangan oqimlarni to'playdi.
FSM_TTL: Final = 86_400
# Telegram'ning qayta yuborish oynasidan sezilarli uzoq, lekin Redis xotirasini
# yemaydi
DEDUPE_TTL: Final = 3_600

STEP_NAME: Final = "name"
STEP_CONTACT: Final = "contact"

MAX_CONTACT_ATTEMPTS: Final = 3
QUIET_SEC: Final = 600

NAME_MIN: Final = 2
NAME_MAX: Final = 64

TEXTS: Final[dict[str, dict[str, str]]] = {
    "uz": {
        "ask_name": "Assalomu alaykum! Ismingiz {name}mi?",
        "confirm": "✅ Ha, shu",
        "change": "✍️ Boshqa ism",
        "type_name": "Ismingizni yozing:",
        "bad_name": "Ism 2 dan 64 belgigacha bo‘lsin. Qaytadan yozing:",
        "ask_phone": (
            "{name}, tanishdik. Endi telefon raqamingizni yuboring —"
            " pastdagi tugma orqali."
        ),
        "share": "📱 Raqamimni yuborish",
        "foreign": "Bu boshqa odamning raqami. Pastdagi tugma orqali o‘z raqamingizni yuboring.",
        "bad_phone": "Raqam O‘zbekiston raqamiga o‘xshamadi. Pastdagi tugma orqali yuboring.",
        "typed_phone": "Raqamni qo‘lda yozib bo‘lmaydi — pastdagi tugmani bosing.",
        "quiet": "Juda ko‘p urinish bo‘ldi. 10 daqiqadan keyin qayta urinib ko‘ring.",
        "done": "Tayyor, {name}! Endi ilovani ochib klub tanlashingiz mumkin.",
        "open": "🎮 Ilovani ochish",
        "already": "Siz allaqachon ro‘yxatdan o‘tgansiz. Ilovani oching:",
    },
    "ru": {
        "ask_name": "Здравствуйте! Вас зовут {name}?",
        "confirm": "✅ Да, верно",
        "change": "✍️ Другое имя",
        "type_name": "Напишите ваше имя:",
        "bad_name": "Имя должно быть от 2 до 64 символов. Напишите ещё раз:",
        "ask_phone": (
            "{name}, приятно познакомиться. Теперь отправьте номер"
            " телефона — кнопкой ниже."
        ),
        "share": "📱 Отправить мой номер",
        "foreign": "Это номер другого человека. Отправьте свой номер кнопкой ниже.",
        "bad_phone": "Номер не похож на узбекский. Отправьте его кнопкой ниже.",
        "typed_phone": "Номер нельзя написать вручную — нажмите кнопку ниже.",
        "quiet": "Слишком много попыток. Повторите через 10 минут.",
        "done": "Готово, {name}! Теперь можно открыть приложение и выбрать клуб.",
        "open": "🎮 Открыть приложение",
        "already": "Вы уже зарегистрированы. Откройте приложение:",
    },
}


def _lang(sender: dict[str, Any]) -> str:
    code = str(sender.get("language_code") or "uz").split("-")[0].lower()
    return "ru" if code == "ru" else "uz"


def _t(lang: str, key: str, **fmt: str) -> str:
    return TEXTS[lang][key].format(**fmt)


def _token() -> str:
    return settings.bot_token.get_secret_value()


# ── Holat ────────────────────────────────────────────────────────────────


def _key(telegram_id: int) -> str:
    return f"bot:fsm:cust:{telegram_id}"


async def _save_state(telegram_id: int, state: dict[str, Any]) -> None:
    await redis_client().set(_key(telegram_id), json.dumps(state), ex=FSM_TTL)


async def _peek_state(telegram_id: int) -> dict[str, Any]:
    raw = await redis_client().get(_key(telegram_id))
    if not raw:
        return {}
    try:
        loaded: dict[str, Any] = json.loads(raw)
        return loaded
    except json.JSONDecodeError:
        return {}


async def _consume_state(telegram_id: int) -> dict[str, Any]:
    """Holatni ATOMIK o'qib, darhol o'chiradi (§4.2, 6-shart).

    Ikkita kontakt xabari birga kelsa faqat bittasi holatni oladi — takroriy
    telefon o'zgarishi qayta ishlanmaydi.
    """
    raw = await redis_client().getdel(_key(telegram_id))
    if not raw:
        return {}
    try:
        loaded: dict[str, Any] = json.loads(raw)
        return loaded
    except json.JSONDecodeError:
        return {}


async def _seen_before(update_id: Any) -> bool:
    """Takroriy update. Bu himoyasiz sekin javobda kelgan kontakt xabari
    telefon o'zgarishini ikki marta qayta ishlardi."""
    if update_id is None:
        return False
    stored = await redis_client().set(
        f"tg:upd:customer:{update_id}", "1", ex=DEDUPE_TTL, nx=True
    )
    return not stored


async def _quiet(telegram_id: int) -> bool:
    return bool(await redis_client().get(f"bot:quiet:cust:{telegram_id}"))


# ── Ma'lumotlar bazasi ───────────────────────────────────────────────────


async def _profile(telegram_id: int) -> dict[str, Any] | None:
    """Mijoz qatori. RLS uchun `app.telegram_id` ochiladi (`users_self`)."""
    async with AppSession() as session, session.begin():
        await set_telegram_scope(session, telegram_id)
        row = (
            await session.execute(
                sql(
                    "SELECT id, display_name, phone_verified_at IS NOT NULL AS verified"
                    " FROM users WHERE kind = 'customer' AND telegram_id = :tg"
                ),
                {"tg": telegram_id},
            )
        ).first()

    if row is None:
        return None
    return {"id": row[0], "display_name": row[1], "verified": bool(row[2])}


async def _upsert_name(telegram_id: int, name: str) -> None:
    async with AppSession() as session, session.begin():
        await set_telegram_scope(session, telegram_id)
        await session.execute(
            sql(
                "INSERT INTO users (kind, telegram_id, first_name, display_name)"
                " VALUES ('customer', :tg, :name, :name)"
                " ON CONFLICT (telegram_id) WHERE kind = 'customer'"
                " DO UPDATE SET display_name = EXCLUDED.display_name"
            ),
            {"tg": telegram_id, "name": name},
        )


async def _save_phone(telegram_id: int, phone: str) -> None:
    async with AppSession() as session, session.begin():
        await set_telegram_scope(session, telegram_id)
        await session.execute(
            sql(
                "UPDATE users SET phone = :phone, phone_verified_at = now()"
                " WHERE kind = 'customer' AND telegram_id = :tg"
            ),
            {"tg": telegram_id, "phone": phone},
        )


async def _log_event(event: str, telegram_id: int, detail: dict[str, Any]) -> None:
    """`auth_events` — telefon raqami YOZILMAYDI, faqat sabab."""
    try:
        async with AppSession() as session, session.begin():
            await set_telegram_scope(session, telegram_id)
            await session.execute(
                sql(
                    "INSERT INTO auth_events (event, detail) VALUES (:e, CAST(:d AS jsonb))"
                ),
                {"e": event, "d": json.dumps(detail)},
            )
    except Exception:
        log.warning("auth_events yozilmadi: %s", event, exc_info=True)


# ── Qadamlar ─────────────────────────────────────────────────────────────


async def _send_open_app(chat_id: int, lang: str, name: str, *, first_time: bool) -> None:
    """BITTA xabar: matn + ostidagi inline tugma.

    Ilgari ikkita ketardi — biri `ReplyKeyboardRemove` bilan, ikkinchisining
    matni tugma yozuvining o'zi («Ilovani ochish») edi. Natijada chatda bir xil
    yozuv ikki marta ko'rinardi: bo'sh pufakcha va tugma.

    Telefon tugmasi `one_time_keyboard` bilan yuborilgani uchun Telegram uni
    bosilishi bilan o'zi yig'ishtiradi — alohida `ReplyKeyboardRemove` xabari
    shart emas.
    """
    key = "done" if first_time else "already"
    await telegram_api.send_message(
        _token(),
        chat_id,
        _t(lang, key, name=name) if first_time else _t(lang, key),
        reply_markup=telegram_api.webapp_keyboard(_t(lang, "open"), settings.miniapp_url),
    )


async def _ask_phone(chat_id: int, lang: str, name: str) -> None:
    await telegram_api.send_message(
        _token(),
        chat_id,
        _t(lang, "ask_phone", name=name),
        reply_markup=telegram_api.contact_keyboard(_t(lang, "share")),
    )


async def _handle_start(sender: dict[str, Any], chat_id: int) -> None:
    telegram_id = int(sender["id"])
    lang = _lang(sender)
    profile = await _profile(telegram_id)

    if profile and profile["verified"]:
        await _send_open_app(chat_id, lang, profile["display_name"] or "", first_time=False)
        return

    if profile:
        # Qator bor, telefon yo'q — ismni qayta so'ramaymiz
        await _save_state(telegram_id, {"step": STEP_CONTACT, "name": profile["display_name"]})
        await _ask_phone(chat_id, lang, profile["display_name"] or "")
        return

    suggested = clean_name(sender.get("first_name"), limit=NAME_MAX)
    await _save_state(telegram_id, {"step": STEP_NAME, "draft": suggested})
    await telegram_api.send_message(
        _token(),
        chat_id,
        _t(lang, "ask_name", name=suggested or "?"),
        reply_markup=telegram_api.name_keyboard(_t(lang, "confirm"), _t(lang, "change")),
    )


async def _handle_text(sender: dict[str, Any], chat_id: int, body: str) -> None:
    telegram_id = int(sender["id"])
    lang = _lang(sender)
    state = await _peek_state(telegram_id)

    if state.get("step") == STEP_CONTACT:
        # Raqamni qo'lda yozib bo'lmaydi — tasdiqning butun ma'nosi shunda
        await telegram_api.send_message(
            _token(),
            chat_id,
            _t(lang, "typed_phone"),
            reply_markup=telegram_api.contact_keyboard(_t(lang, "share")),
        )
        return

    if state.get("step") != STEP_NAME:
        return

    if body == _t(lang, "confirm"):
        name = str(state.get("draft") or "")
    elif body == _t(lang, "change"):
        await telegram_api.send_message(
            _token(), chat_id, _t(lang, "type_name"),
            reply_markup=telegram_api.remove_keyboard(),
        )
        return
    else:
        name = clean_name(body, limit=NAME_MAX)

    if not (NAME_MIN <= len(name) <= NAME_MAX):
        await telegram_api.send_message(_token(), chat_id, _t(lang, "bad_name"))
        return

    await _upsert_name(telegram_id, name)
    await _save_state(telegram_id, {"step": STEP_CONTACT, "name": name})
    await _ask_phone(chat_id, lang, name)


async def _handle_contact(message: dict[str, Any], sender: dict[str, Any], chat_id: int) -> None:
    telegram_id = int(sender["id"])
    lang = _lang(sender)

    # 6-shart: holat ATOMIK iste'mol qilinadi. Kutilmagan kontakt qabul
    # qilinmaydi va soxta webhook uchun qadam soni oshadi.
    state = await _consume_state(telegram_id)
    if state.get("step") != STEP_CONTACT:
        await _log_event("contact_rejected", telegram_id, {"reason": "unexpected"})
        return

    result = contact_check.check_contact(message)
    if not result.ok:
        attempts = int(state.get("attempts") or 0) + 1
        await _log_event("contact_rejected", telegram_id, {"reason": result.reason})

        if attempts >= MAX_CONTACT_ATTEMPTS:
            await redis_client().set(f"bot:quiet:cust:{telegram_id}", "1", ex=QUIET_SEC)
            await telegram_api.send_message(_token(), chat_id, _t(lang, "quiet"))
            return

        state["attempts"] = attempts
        await _save_state(telegram_id, state)

        key = "bad_phone" if result.reason == contact_check.REASON_BAD_PHONE else "foreign"
        await telegram_api.send_message(
            _token(), chat_id, _t(lang, key),
            reply_markup=telegram_api.contact_keyboard(_t(lang, "share")),
        )
        return

    assert result.phone is not None
    await _save_phone(telegram_id, result.phone)
    await _log_event("phone_verified", telegram_id, {"source": "bot"})
    await _send_open_app(chat_id, lang, str(state.get("name") or ""), first_time=True)


async def handle_update(update: dict[str, Any]) -> None:
    """Yagona kirish nuqtasi. HECH QACHON istisno chiqarmaydi."""
    try:
        if await _seen_before(update.get("update_id")):
            return

        message = update.get("message")
        if not isinstance(message, dict):
            return

        sender = message.get("from")
        chat = message.get("chat") or {}
        if not isinstance(sender, dict) or "id" not in sender:
            return

        chat_id = int(chat.get("id") or sender["id"])
        telegram_id = int(sender["id"])

        if await _quiet(telegram_id):
            return

        if "contact" in message:
            await _handle_contact(message, sender, chat_id)
            return

        body = message.get("text")
        if not isinstance(body, str):
            return

        parts = body.strip().split(maxsplit=1)
        if parts and parts[0] == "/start":
            await _handle_start(sender, chat_id)
            return

        await _handle_text(sender, chat_id, body.strip())

    except Exception:
        # Telegram'ga baribir 200 qaytadi — aks holda navbat to'xtaydi
        log.exception("mijoz bot update'i qayta ishlanmadi")
