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


# Har vazifa YIG'ADIGAN payload'ning namunasi — tasks.py bilan shartnoma.
# Vazifa payload'i o'zgartirilsa BU YERDA ham o'zgartiriladi; shablon bilan
# kelishmovchilik shu test orqali ushlab qolinadi (test-review topilmasi:
# daily_summary shabloni {variance_total} kutib, vazifa occupancy bergan —
# xulosa 3 urinishdan keyin ERROR bo'lib, ega hech qachon olmasdi).
TASK_PAYLOAD_SAMPLES: dict[str, dict[str, object]] = {
    "booking_reminder_2h": {"club": "Klub", "station": "PS-1", "starts_at": "18:00"},
    "booking_reminder_20m": {"club": "Klub", "station": "PS-1", "starts_at": "18:00"},
    "daily_summary": {
        "club": "Klub",
        "date": "2026-08-19",
        "received_revenue": 120_000,
        "sessions": 3,
        "occupancy": 8,
    },
    "shift_variance": {
        "club": "Klub",
        "variance": 100_000,
        "expected": 0,
        "counted": 100_000,
        "staff": "Kassir",
    },
}


def test_task_payloads_render_with_their_templates() -> None:
    """tasks.py yig'adigan payload'lar o'z shablonlari bilan renderlanadi."""
    assert set(TASK_PAYLOAD_SAMPLES) == set(TEMPLATES), "shartnoma to'liq qoplansin"
    for template, payload in TASK_PAYLOAD_SAMPLES.items():
        out = render(template, payload)
        assert out  # bo'sh emas — hamma kalit o'z joyiga tushdi
