"""Xodim kirishi — login + parol.

Har bir test dizayndagi aniq bir hujumni qulflaydi
(`docs/05-auth-redesign.md` §6, §10).
"""

import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core.config import settings
from playbron.core.passwords import hash_password
from playbron.main import app
from playbron.modules.auth.staff import normalize_login

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

LOGIN = "sinov.kassa"
PASSWORD = "juda mustahkam parol"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture(autouse=True)
async def clean_limits() -> AsyncIterator[None]:
    """Chegara sanagichlarini har test oldidan tozalaydi.

    Ular Redis'da yashaydi va testlar orasida saqlanib qoladi: to'plam
    to'liq yurganda oldingi testlar byudjetni yeb qo'yadi va keyingilari
    401 o'rniga 429 oladi. Bu chegaralagichning to'g'ri ishlashi, shuning
    uchun tuzatish testda — kodda emas.
    """
    from playbron.core.redis import redis_client

    async def wipe() -> None:
        redis = redis_client()
        keys = [key async for key in redis.scan_iter(match="rl:*")]
        if keys:
            await redis.delete(*keys)

    await wipe()
    yield
    await wipe()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def staff_user() -> AsyncIterator[int]:
    """Paroli qo'yilgan faol xodim. Parolni EGASI roli bilan yozamiz —
    `auth_assign_password` klub konteksti talab qiladi, bu yerda u yo'q."""
    engine = _owner_engine()
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        user_id = await conn.scalar(
            text(
                "INSERT INTO users (kind, login, status, first_name)"
                " VALUES ('staff', :login, 'active', 'Sinov')"
                " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                " DO UPDATE SET status = 'active' RETURNING id"
            ),
            {"login": LOGIN},
        )
        await conn.execute(
            text(
                "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                " VALUES (:uid, :h, false)"
                " ON CONFLICT (user_id) DO UPDATE"
                " SET password_hash = EXCLUDED.password_hash, must_change = false,"
                "     failed_count = 0"
            ),
            {"uid": user_id, "h": password_hash},
        )

    yield int(user_id)

    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM users WHERE id = :i"), {"i": user_id})
    await engine.dispose()


async def test_normalize_collapses_lookalikes() -> None:
    """`kassa01`, `KASSA01`, fullwidth va Kelvin belgisi — BITTA satr.

    Aks holda har biri alohida chegara byudjeti olardi va per-hisob
    brute-force chegarasi amalda cheksiz aylanardi (§6.2).
    """
    variants = ["kassa01", "KASSA01", "ｋassa01", "Kassa01", "  Kassa01  "]
    assert {normalize_login(v) for v in variants} == {"kassa01"}


async def test_normalize_rejects_bad_shape() -> None:
    for bad in ["ka", "a" * 33, "kassa 01", "каssa01", "kassa@01", ""]:
        assert normalize_login(bad) is None, bad


@skip_no_db
async def test_login_succeeds(client: httpx.AsyncClient, staff_user: int) -> None:
    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["user"]["id"] == staff_user
    assert body["user"]["login"] == LOGIN
    # Xodimda Telegram YO'Q — u shaxsni tasdiqlamaydi
    assert body["user"]["telegram_id"] is None
    assert body["must_change_password"] is False
    assert body["access_token"]


@skip_no_db
async def test_login_is_case_insensitive(client: httpx.AsyncClient, staff_user: int) -> None:
    r = await client.post(
        "/api/v1/auth/staff/login",
        json={"login": LOGIN.upper(), "password": PASSWORD},
    )
    assert r.status_code == 200, r.text


@skip_no_db
async def test_wrong_password_and_unknown_login_are_identical(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Ikki javob bir xil bo'lmasa — hisob sanash orakuli ochiladi."""
    wrong = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": "boshqa parol"}
    )
    unknown = await client.post(
        "/api/v1/auth/staff/login",
        json={"login": "yoq.bunday", "password": "boshqa parol"},
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == unknown.json()["error"]["code"] == "LOGIN_INVALID"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


@skip_no_db
async def test_disabled_account_gets_the_same_answer(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """`status != 'active'` ham AYNAN o'sha 401 — «hisob bor» degan signal bermaydi."""
    engine = _owner_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET status = 'disabled' WHERE id = :i"), {"i": staff_user}
        )
    await engine.dispose()

    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD}
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "LOGIN_INVALID"


@skip_no_db
async def test_case_variants_share_one_rate_limit_bucket(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Yozuvi har xil login BITTA byudjetdan yeydi.

    Bu §6.2 ning uchidan-uchiga isboti: agar chegaralagich xom satrni
    xeshlaganida `kassa01` / `KASSA01` / fullwidth variantlar har biri yangi
    byudjet ochib, per-hisob brute-force chegarasi ma'nosiz bo'lib qolardi.
    """
    variants = ["sinov.kassa", "SINOV.KASSA", "Sinov.Kassa", "ｓinov.kassa", "SiNoV.kAsSa"]
    codes: list[int] = []

    # IP + login chegarasi 5/5 daq — oltinchisi 429 bo'lishi shart
    for index in range(6):
        r = await client.post(
            "/api/v1/auth/staff/login",
            json={"login": variants[index % len(variants)], "password": "xato parol"},
        )
        codes.append(r.status_code)

    assert codes[:5] == [401] * 5, codes
    assert codes[5] == 429, f"yozuv o'zgarganda chegara aylanib o'tildi: {codes}"


@skip_no_db
async def test_access_token_is_staff_audience(
    client: httpx.AsyncClient, staff_user: int
) -> None:
    """Token `aud='staff'` bo'lishi shart — mijoz tokeni bilan aralashmasin."""
    import jwt

    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD}
    )
    claims = jwt.decode(
        r.json()["access_token"],
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        audience="staff",
    )
    assert claims["aud"] == "staff"
