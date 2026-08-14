"""Foydalanuvchi kiritgan matnni normallashtirish.

Manba: `docs/05-auth-redesign.md` §3.8.

Nega kerak: `first_name`, `last_name` va `username` `initData` dan keladi,
ya'ni ularni foydalanuvchi TO'LIQ nazorat qiladi (Telegram profilining o'zi).
Botdagi ism validatsiyasi yolg'iz o'zida yetarli emas — hujumchi profil ismini
`Bekor qilindi — 90 111 22 33 ga qo'ng'iroq qiling` ga o'zgartirib Mini App'ni
ochadi va o'sha satr xodim konsolidagi bron ro'yxatida chiqadi.

Shuning uchun tozalash YOZISH nuqtasida, ikkala oqim uchun ham bir joyda.
"""

import unicodedata
from typing import Final

# Belgilar kod nuqtasi bilan quriladi: ko'rinmas belgini manba faylga
# to'g'ridan-to'g'ri yozib bo'lmaydi — tahrirlash zanjirida ular jimgina
# yo'qoladi yoki boshqa belgiga aylanadi.
#
# Ikki tomonlama yozuv boshqaruvi: matnni ko'z bilan ko'rinadigan tarzda
# teskari o'girib, konsolda butunlay boshqa narsa ko'rsatishi mumkin.
_BIDI: Final = frozenset(
    chr(code)
    for code in (
        0x200E, 0x200F,                          # LRM, RLM
        0x202A, 0x202B, 0x202C, 0x202D, 0x202E,  # LRE, RLE, PDF, LRO, RLO
        0x2066, 0x2067, 0x2068, 0x2069,          # LRI, RLI, FSI, PDI
    )
)

# Ko'rinmas ajratgichlar — ismni bo'sh yoki chalg'ituvchi qiladi
_INVISIBLE: Final = frozenset(
    chr(code)
    for code in (
        0x200B, 0x200C, 0x200D,  # ZWSP, ZWNJ, ZWJ
        0x2060, 0xFEFF,          # word joiner, BOM
    )
)

NAME_MAX: Final = 64


def clean_name(raw: str | None, *, limit: int = NAME_MAX) -> str:
    """Ko'rsatishga xavfsiz ism. Bo'sh natija ham bo'lishi mumkin.

    NFKC → boshqaruv, bidi va ko'rinmas belgilarni olib tashlash →
    ketma-ket bo'shliqlarni bittaga keltirish → uzunlik cheklovi.
    """
    if not raw:
        return ""

    text = unicodedata.normalize("NFKC", raw)

    kept: list[str] = []
    for char in text:
        # Bidi va ko'rinmas ajratgichlar butunlay olib tashlanadi: ular
        # so'z chegarasi emas, faqat ko'rinishni buzadi
        if char in _BIDI or char in _INVISIBLE:
            continue

        category = unicodedata.category(char)
        if category == "Cc":
            # Boshqaruv belgisi (`\n`, `\t`) — so'z chegarasi bo'lgani uchun
            # o'chirilmaydi, bo'shliqqa aylanadi. Aks holda «Ism\nFamiliya»
            # «IsmFamiliya» bo'lib qolardi.
            kept.append(" ")
            continue
        if category in {"Cf", "Cs"}:
            continue

        kept.append(char)

    return " ".join("".join(kept).split())[:limit]


def clean_username(raw: str | None) -> str | None:
    """Telegram `username` — faqat ASCII harf, raqam va pastki chiziq."""
    if not raw:
        return None
    cleaned = "".join(ch for ch in raw if ch.isascii() and (ch.isalnum() or ch == "_"))
    return cleaned[:64] or None
