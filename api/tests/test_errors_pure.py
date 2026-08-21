"""`core/errors.py` xato xaritasi — DB'SIZ, `RUN_DB_TESTS`siz o'tadi.

    cd api && python -m pytest tests/test_errors_pure.py -q

`0034` trigger qo'riqchisi `RAISE EXCEPTION 'SHIFT_CLOSED'` (P0001) bilan
gapiradi, `_db_error` esa uni matn bo'yicha `409 SHIFT_CLOSED`ga o'giradi.
Matn moslashuvi buzilsa xato jimgina 500 bo'lib qolardi — shu test uni
muzlatib turadi. Trigger yo'li API orqali faqat poyga holatida ochiladi
(o'qish–yozish orasida smena yopilsa), shuning uchun sinov handler
darajasida: soxta DBAPIError ko'targan marshrut orqali.
"""

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import DBAPIError

from playbron.core import errors

pytestmark = pytest.mark.asyncio


class _FakePGError(Exception):
    """asyncpg xatosining minimal qiyofasi — `sqlstate` atributi bilan."""

    def __init__(self, message: str, sqlstate: str) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


def _app_raising(orig: Exception) -> FastAPI:
    app = FastAPI()
    errors.install(app)

    @app.get("/boom")
    async def boom() -> None:
        raise DBAPIError("INSERT INTO payments ...", None, orig)  # type: ignore[arg-type]

    return app


async def _call(app: FastAPI) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/boom")


async def test_p0001_shift_closed_maps_to_409() -> None:
    orig = _FakePGError("SHIFT_CLOSED", errors.PG_RAISED_EXCEPTION)
    resp = await _call(_app_raising(orig))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "SHIFT_CLOSED"


async def test_p0001_shift_not_found_maps_to_409() -> None:
    # 0034'dan oldin bu holat FK (23503) bilan 409 RELATED_RECORD_MISSING
    # edi — trigger FK'dan oldin ishlasa ham shartnoma o'zgarmaydi
    orig = _FakePGError("SHIFT_NOT_FOUND", errors.PG_RAISED_EXCEPTION)
    resp = await _call(_app_raising(orig))
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "RELATED_RECORD_MISSING"


async def test_p0001_without_known_literal_stays_500() -> None:
    # Notanish RAISE literal'i yutilmasligi kerak — 500 ko'rinib qolsin
    orig = _FakePGError("BOSHQA_TRIGGER_XATOSI", errors.PG_RAISED_EXCEPTION)
    resp = await _call(_app_raising(orig))
    assert resp.status_code == 500


async def test_shift_closed_literal_with_other_sqlstate_stays_500() -> None:
    # Matn mos, sqlstate boshqa — xarita faqat P0001 uchun ishlaydi
    orig = _FakePGError("SHIFT_CLOSED", "P0002")
    resp = await _call(_app_raising(orig))
    assert resp.status_code == 500


async def test_literal_in_bound_params_does_not_match() -> None:
    """Moslash `str(exc)` emas, `str(exc.orig)` ustida ekanini muzlatadi.

    DBAPIError matni SQL va bog'langan parametrlarni o'z ichiga oladi —
    `note` maydonida "SHIFT_CLOSED" yozilgan qator BOSHQA P0001 bilan
    yiqilsa yolg'on 409 chiqmasligi kerak.
    """
    orig = _FakePGError("BOSHQA_XATO", errors.PG_RAISED_EXCEPTION)
    app = FastAPI()
    errors.install(app)

    @app.get("/boom")
    async def boom() -> None:
        raise DBAPIError(
            "INSERT INTO expenses (note) VALUES (%(note)s)",
            {"note": "SHIFT_CLOSED"},
            orig,  # type: ignore[arg-type]
        )

    resp = await _call(app)
    assert resp.status_code == 500
