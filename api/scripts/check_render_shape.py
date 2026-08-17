"""Migratsiyalarni RENDER SHAKLIDA sinash — deploy oldidan MAJBURIY.

    python scripts/check_render_shape.py

## Nega kerak

Lokal baza egasi SUPERUSER. Har bir migratsiyadagi `_exempt()`
(`rolsuper OR rolbypassrls`) shuni ko'rib `_self_test()` ni BUTUNLAY
o'tkazib yuboradi. Ya'ni lokalda "migratsiya o'tdi" degani self-test
yashil degani EMAS — u hech qachon ishlamagan.

Render bepul rejasida rol BYPASSRLS ololmaydi
(`[[render-free-tier-no-bypassrls]]`), self-testlar ISHLAYDI va yiqilsa
`alembic upgrade head` to'xtaydi → konteyner ishga tushmaydi → Render
ESKI nusxani jonli qoldiradi. Tashqaridan `healthz` 200 qaytaraveradi,
ya'ni deploy "muvaffaqiyatli" ko'rinadi, aslida kod eski.

2026-08-16 da aynan shu bo'ldi: kun bo'yi hech bir push prod'ga yetib
bormadi, chunki `0025` self-testi Render shaklida yiqilardi.

## Nima qiladi

CI'dagi `api-render-shape` job'ining aynan o'zi:
`NOSUPERUSER CREATEROLE NOCREATEDB NOBYPASSRLS` egasi bilan toza baza
yaratadi va unga `alembic upgrade head` yuritadi. Baza oxirida
o'chiriladi.

Ulanish ma'lumoti `DIRECT_URL` dan olinadi (uning `postgres` bazasiga
admin sifatida ulanib, sinov bazasini yaratadi).
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import psycopg

API_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(API_DIR / "src"))

from playbron.core.config import settings  # noqa: E402

DB = "playbron_rendershape"
ROLE = "rendershape_owner"
# Sir emas: bir necha soniya yashaydigan, faqat `localhost`dagi sinov
# bazasi uchun; skript oxirida rol ham, baza ham o'chiriladi.
PASSWORD = "rendershape"  # noqa: S105


def _admin_dsn() -> str:
    raw = settings.direct_url
    raw = raw.replace("postgresql+psycopg://", "postgresql://")
    raw = raw.replace("postgresql+asyncpg://", "postgresql://")
    # Sinov bazasini yaratish uchun `postgres` bazasiga ulanamiz
    return re.sub(r"/[^/?]+(\?|$)", r"/postgres\1", raw)


def _run(dsn: str, *statements: str) -> None:
    with psycopg.connect(dsn, autocommit=True) as conn:
        for statement in statements:
            conn.execute(statement)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    dsn = _admin_dsn()
    print("== oldingi qoldiqni tozalash ==")
    _run(dsn, f"DROP DATABASE IF EXISTS {DB}", f"DROP ROLE IF EXISTS {ROLE}")

    print("== Render shaklidagi ega (NOSUPERUSER, NOBYPASSRLS) ==")
    _run(
        dsn,
        f"CREATE ROLE {ROLE} LOGIN PASSWORD '{PASSWORD}'"
        " NOSUPERUSER CREATEROLE NOCREATEDB NOBYPASSRLS",
        f"CREATE DATABASE {DB} OWNER {ROLE}",
    )

    url = f"postgresql://{ROLE}:{PASSWORD}@localhost:5432/{DB}"
    env = {
        **os.environ,
        "DATABASE_URL": url,
        "DIRECT_URL": url,
        "PLATFORM_DATABASE_URL": url,
        # Bepul rejada alohida rol yaratib bo'lmaydi — prod bilan bir xil
        "ALLOW_SINGLE_DB_ROLE": "1",
    }

    print("== alembic upgrade head (self-testlar ENDI ishlaydi) ==")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        print(result.stdout[-3000:])
    if result.returncode != 0:
        print("--- XATO ---")
        print(result.stderr[-6000:])

    print("== sinov bazasini o'chirish ==")
    _run(dsn, f"DROP DATABASE IF EXISTS {DB}", f"DROP ROLE IF EXISTS {ROLE}")

    if result.returncode == 0:
        print("\nOK — migratsiyalar Render shaklida o'tadi, deploy xavfsiz")
    else:
        print("\nYIQILDI — shu holda Render deploy ham yiqiladi va ESKI kod jonli qoladi")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
