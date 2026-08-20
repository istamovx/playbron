"""Bildirishnoma shablonlari — DB'SIZ, `RUN_DB_TESTS`siz o'tadi.

    cd api && python -m pytest tests/test_notify_pure.py -q
"""

import pytest

from playbron.worker.templates import TEMPLATES, render


def test_reminder_renders_all_fields() -> None:
    out = render(
        "booking_reminder_2h",
        {"club": "Mega Club", "station": "PS-1", "starts_at": "18:00"},
    )
    assert "Mega Club" in out
    assert "PS-1" in out
    assert "18:00" in out


def test_unknown_template_is_rejected() -> None:
    with pytest.raises(ValueError, match="Noma'lum shablon"):
        render("mavjud_emas", {})


def test_missing_payload_key_is_rejected() -> None:
    # Yetishmagan kalit jimgina bo'sh joy bo'lib ketmasin
    with pytest.raises(ValueError, match="payload"):
        render("shift_variance", {"club": "X"})


def test_every_template_has_no_positional_slots() -> None:
    # {0} kabi pozitsion slot render'ni sindiradi — hammasi nomlangan bo'lsin
    for name, text in TEMPLATES.items():
        assert "{}" not in text and "{0" not in text, name
