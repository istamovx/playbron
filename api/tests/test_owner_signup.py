"""Klub egasi o'zi ro'yxatdan o'tadi.

Manba: `docs/05-auth-redesign.md` Ilova C.1 va `0008_owner_signup`.
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from conftest import null_actor_refs
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core.config import settings
from playbron.core.passwords import MIN_LENGTH
from playbron.main import app
from playbron.modules.auth import signup

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

LOGIN = "sgn.aziz"
PASSWORD = "juda mustahkam parol"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


def _form(**over: Any) -> dict[str, Any]:
    base = {
        "first_name": "Aziz",
        "club_name": "Neon Arena",
        "phone": "+998901234567",
        "address": "Toshkent, Chilonzor 12",
        "login": LOGIN,
        "password": PASSWORD,
    }
    base.update(over)
    return base


@pytest_asyncio.fixture(autouse=True)
async def clean() -> AsyncIterator[None]:
    """DB va Redis tozalash.

    `RUN_DB_TESTS` qo'yilmagan bo'lsa hech narsa qilmaydi. `skipif` fixture
    setup'idan OLDIN ishlaydi, ya'ni belgilangan testlar bu yergacha
    yetmaydi — lekin shu fayldagi ikkita SOF test (`clean`, `normalize_login`)
    ataylab belgilanmagan va servislarsiz muhitda ular SKIP emas, fixture
    xatosi bo'lib qolardi.
    """
    from playbron.core.redis import redis_client

    if os.environ.get("RUN_DB_TESTS") != "1":
        yield
        return

    async def wipe() -> None:
        redis = redis_client()
        keys = [key async for key in redis.scan_iter(match="rl:*")]
        if keys:
            await redis.delete(*keys)

        engine = _owner_engine()
        async with engine.begin() as conn:
            # Tashkilot va klub `users` ga FK bilan bog'langan; egasini
            # o'chirish uchun avval tashkilot ketadi (klub CASCADE bilan).
            await conn.execute(
                text(
                    "DELETE FROM organizations WHERE owner_user_id IN"
                    " (SELECT id FROM users WHERE kind = 'staff' AND login LIKE 'sgn.%')"
                )
            )
            stale_ids = [
                row[0]
                for row in (
                    await conn.execute(
                        text("SELECT id FROM users WHERE kind = 'staff' AND login LIKE 'sgn.%'")
                    )
                ).all()
            ]
            await null_actor_refs(conn, *stale_ids)
            await conn.execute(
                text("DELETE FROM users WHERE kind = 'staff' AND login LIKE 'sgn.%'")
            )
        await engine.dispose()

    await wipe()
    yield
    await wipe()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@skip_no_db
async def test_signup_creates_org_club_and_working_login(client: httpx.AsyncClient) -> None:
    created = await client.post("/api/v1/auth/owner/signup", json=_form())
    assert created.status_code == 201, created.text
    assert created.json()["login"] == LOGIN

    # Tokenlar bu javobda YO'Q — sessiya faqat `/auth/staff/login` orqali
    assert "access_token" not in created.json()

    signed = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": PASSWORD}
    )
    assert signed.status_code == 200, signed.text
    body = signed.json()

    # O'zi tanlagan parol bir martalik EMAS
    assert body["must_change_password"] is False
    assert [m["role"] for m in body["memberships"]] == ["OWNER"]
    assert body["memberships"][0]["club_name"] == "Neon Arena"


@skip_no_db
async def test_organization_starts_pending_without_plan(client: httpx.AsyncClient) -> None:
    """O'zini o'zi faollashtirish yo'q — tarifni to'lov oqimi qo'yadi."""
    assert (await client.post("/api/v1/auth/owner/signup", json=_form())).status_code == 201

    engine = _owner_engine()
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT o.status, o.plan_code, c.status, c.address, c.phone"
                    " FROM organizations o JOIN clubs c ON c.org_id = o.id"
                    " JOIN users u ON u.id = o.owner_user_id WHERE u.login = :login"
                ),
                {"login": LOGIN},
            )
        ).first()
    await engine.dispose()

    assert row is not None
    org_status, plan_code, club_status, address, phone = row
    assert org_status == "pending"
    assert plan_code is None
    # Klub `draft`: mijozlarga ko'rinmaydi, egasi to'ldirib faollashtiradi
    assert club_status == "draft"
    assert address == "Toshkent, Chilonzor 12"
    assert phone == "+998901234567"


@skip_no_db
async def test_duplicate_login_is_reported(client: httpx.AsyncClient) -> None:
    assert (await client.post("/api/v1/auth/owner/signup", json=_form())).status_code == 201

    again = await client.post("/api/v1/auth/owner/signup", json=_form(club_name="Boshqa"))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "LOGIN_TAKEN"


@skip_no_db
async def test_short_password_is_rejected_with_owner_minimum(
    client: httpx.AsyncClient,
) -> None:
    """Klub egasi uchun minimum 14 belgi — xodimnikidan (12) uzunroq.

    Parol ATAYLAB 13 belgi: STAFF/ADMIN uchun (12) yetarli, OWNER uchun
    (14) yetarli emas. Qisqaroq parol olinsa test har qanday rol ostida
    yashil bo'lardi va aynan shu farqni — `signup.OWNER_ROLE` ni —
    umuman tekshirmasdi.
    """
    thirteen = "parol13belgi!"
    assert len(thirteen) == 13, "test o'z farazini tekshiradi"
    assert MIN_LENGTH["STAFF"] <= len(thirteen) < MIN_LENGTH["OWNER"]

    r = await client.post("/api/v1/auth/owner/signup", json=_form(password=thirteen))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "PASSWORD_TOO_SHORT"

    signed = await client.post(
        "/api/v1/auth/staff/login", json={"login": LOGIN, "password": thirteen}
    )
    assert signed.status_code == 401


@skip_no_db
async def test_bad_phone_is_rejected(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/auth/owner/signup", json=_form(phone="12345"))
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "PHONE_INVALID"


@skip_no_db
async def test_signup_without_scope_creates_nothing(client: httpx.AsyncClient) -> None:
    """`app.signup_login` qo'yilmasa funksiya hech narsa yaratmaydi.

    Bu marshrutdan tashqari chaqiruvga qarshi darvoza: policy `users` ni
    himoya qiladi, funksiya ichidagi tekshiruv esa qolgan to'rtta jadvalni.
    """
    engine = _owner_engine()
    async with engine.begin() as conn:
        with pytest.raises(Exception, match="SIGNUP_SCOPE_MISSING"):
            await conn.execute(
                text(
                    "SELECT auth_owner_signup('sgn.scope', 'X', 'Org', 'Club',"
                    " '+998900000000', 'manzil', 'hash')"
                )
            )
    await engine.dispose()


@skip_no_db
async def test_rate_limit_blocks_after_three_per_hour(client: httpx.AsyncClient) -> None:
    """Ochiq endpoint — IP bo'yicha 3/soat.

    Bu chegara «login band» javobini xavfsiz qiladigan narsa: shu tezlikda
    global login makonini sanab chiqib bo'lmaydi.
    """
    codes = []
    for index in range(signup.IP_HOUR[0] + 1):
        r = await client.post(
            "/api/v1/auth/owner/signup",
            json=_form(login=f"sgn.rate{index}", club_name=f"Klub {index}"),
        )
        codes.append(r.status_code)

    assert codes[: signup.IP_HOUR[0]] == [201] * signup.IP_HOUR[0]
    assert codes[-1] == 429


async def test_clean_rejects_password_equal_to_club_name() -> None:
    """Parol klub nomi bilan bir xil bo'lmasin — sof funksiya, DB kerak emas."""
    from playbron.core.errors import BadRequest

    with pytest.raises(BadRequest) as caught:
        signup.clean(_form(password="Neon Arena klubi", club_name="Neon Arena klubi"))
    assert caught.value.code == "PASSWORD_IS_NAME"


async def test_clean_normalizes_login_case() -> None:
    fields = signup.clean(_form(login="SGN.Aziz"))
    assert fields.login == "sgn.aziz"


async def test_too_long_address_is_rejected_not_truncated() -> None:
    """Uzun manzil JIMGINA kesilmaydi.

    Manzil mijozga ko'rinadi — yarmi qirqilgan qiymat xatosiz saqlansa
    foydalanuvchi buni bilmay qoladi.
    """
    from playbron.core.errors import BadRequest

    with pytest.raises(BadRequest) as caught:
        signup.clean(_form(address="a" * (signup.ADDRESS_MAX + 1)))
    assert caught.value.code == "ADDRESS_INVALID"


async def test_bidi_characters_are_stripped_from_names() -> None:
    """Ism va klub nomi konsolda va mijoz ekranida ko'rsatiladi."""
    fields = signup.clean(_form(first_name=f"Aziz{chr(0x202E)}"))
    assert chr(0x202E) not in fields.first_name
