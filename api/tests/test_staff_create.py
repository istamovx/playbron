"""Xodim qo'shish — klub egasi hisob yaratadi va parol beradi.

Manba: `docs/05-auth-redesign.md` Ilova C.1.
"""

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from conftest import purge_audit_actor, rls_bypass
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from playbron.core import db as core_db
from playbron.core.config import settings
from playbron.core.passwords import hash_password
from playbron.main import app

pytestmark = pytest.mark.asyncio

skip_no_db = pytest.mark.skipif(
    os.environ.get("RUN_DB_TESTS") != "1",
    reason="RUN_DB_TESTS=1 va ishlab turgan PostgreSQL/Redis kerak",
)

OWNER_LOGIN = "prov.owner"
ADMIN_LOGIN = "prov.admin"
PASSWORD = "juda mustahkam parol"
NEW_STAFF_PASSWORD = "yangi xodim paroli"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture(autouse=True)
async def clean_limits() -> AsyncIterator[None]:
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
async def world() -> AsyncIterator[dict[str, int]]:
    """Tashkilot, klub, OWNER va ADMIN — ikkalasi ham parolli."""
    engine = _owner_engine()
    ids: dict[str, int] = {}
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        # `world` butun grafni nol'dan quradi — hali tabiiy aktor yo'q,
        # shuning uchun `rls_bypass` (`conftest.py`).
        async with rls_bypass(
            conn, "users", "staff_credentials", "organizations", "clubs", "memberships"
        ):
            for key, login in (("owner", OWNER_LOGIN), ("admin", ADMIN_LOGIN)):
                ids[key] = await conn.scalar(
                    text(
                        "INSERT INTO users (kind, login, status, first_name)"
                        " VALUES ('staff', :login, 'active', :name)"
                        " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                        " DO UPDATE SET status = 'active' RETURNING id"
                    ),
                    {"login": login, "name": key},
                )
                await conn.execute(
                    text(
                        "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                        " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                        " SET password_hash = EXCLUDED.password_hash, must_change = false"
                    ),
                    {"uid": ids[key], "h": password_hash},
                )

            ids["org"] = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                    " VALUES (:u, 'Prov Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status)"
                    " VALUES (:o, 'Prov Club', 'active') RETURNING id"
                ),
                {"o": ids["org"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO memberships (user_id, club_id, role) VALUES"
                    " (:owner, :club, 'OWNER'), (:admin, :club, 'ADMIN')"
                ),
                {"owner": ids["owner"], "admin": ids["admin"], "club": ids["club"]},
            )

    # `rls_bypass()` yuqorida FORCE RLS'ni vaqtincha olib turdi (DDL) — ilova
    # pool'ining tayyorlangan bayonot keshi eskirgan katalog holatiga ishora
    # qilib qolishi mumkin (`test_bookings.py::world`dagi bilan bir xil sabab).
    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users"):
            # Login shabloni bo'yicha o'chiriladi, aniq id bo'yicha emas:
            # login `ON CONFLICT DO UPDATE` bilan qatorni doim qayta
            # ishlatadi, ya'ni bitta muvaffaqiyatsiz tozalash keyingi HAR
            # BIR yurishni `organizations_owner_user_id_fkey` bilan abadiy
            # blokidan qoldirardi — o'z-o'zini davolaydigan tozalash kerak.
            stale_ids = [
                row[0]
                for row in (
                    await conn.execute(
                        text(
                            "SELECT id FROM users WHERE kind = 'staff' AND login LIKE 'prov.%'"
                        )
                    )
                ).all()
            ]
            await purge_audit_actor(conn, *stale_ids)
            await conn.execute(
                text(
                    "DELETE FROM organizations WHERE owner_user_id IN"
                    " (SELECT id FROM users WHERE kind = 'staff' AND login LIKE 'prov.%')"
                )
            )
            await conn.execute(
                text("DELETE FROM users WHERE kind = 'staff' AND login LIKE 'prov.%'")
            )
    await engine.dispose()


async def _auth(client: httpx.AsyncClient, login: str, club_id: int) -> dict[str, str]:
    signed = await client.post(
        "/api/v1/auth/staff/login", json={"login": login, "password": PASSWORD}
    )
    assert signed.status_code == 200, signed.text
    return {
        "Authorization": f"Bearer {signed.json()['access_token']}",
        "X-Club-Id": str(club_id),
    }


def _payload(**over: Any) -> dict[str, Any]:
    base = {
        "first_name": "Aziz",
        "login": "prov.kassa",
        "password": NEW_STAFF_PASSWORD,
        "role": "STAFF",
    }
    base.update(over)
    return base


@skip_no_db
async def test_owner_creates_staff_and_they_can_sign_in(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _auth(client, OWNER_LOGIN, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/staff", json=_payload(), headers=headers
    )
    assert created.status_code == 201, created.text
    assert created.json()["login"] == "prov.kassa"
    assert created.json()["must_change_password"] is True

    # Yangi xodim darhol kira oladi va almashtirish talab qilinadi
    signed = await client.post(
        "/api/v1/auth/staff/login",
        json={"login": "prov.kassa", "password": NEW_STAFF_PASSWORD},
    )
    assert signed.status_code == 200, signed.text
    assert signed.json()["must_change_password"] is True


@skip_no_db
async def test_owner_resets_forgotten_staff_password(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Audit topilmasi (2026-08-16): unutilgan parolni tiklash yo'li YO'Q edi.

    Tiklangach eski parol ISHLAMASLIGI, yangisi ishlashi va `must_change`
    yana `true` bo'lishi kerak (parolni ega bilgani uchun)."""
    headers = await _auth(client, OWNER_LOGIN, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/staff", json=_payload(), headers=headers
    )
    assert created.status_code == 201, created.text
    staff_id = created.json()["user_id"]

    reset_password = "butunlay boshqa mustahkam parol"
    reset = await client.post(
        f"/api/v1/clubs/{world['club']}/staff/{staff_id}/password",
        json={"password": reset_password},
        headers=headers,
    )
    assert reset.status_code == 204, reset.text

    stale = await client.post(
        "/api/v1/auth/staff/login",
        json={"login": "prov.kassa", "password": NEW_STAFF_PASSWORD},
    )
    assert stale.status_code == 401, "eski parol hali ham ishlayapti"

    fresh = await client.post(
        "/api/v1/auth/staff/login",
        json={"login": "prov.kassa", "password": reset_password},
    )
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["must_change_password"] is True


@skip_no_db
async def test_admin_cannot_reset_owner_password(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Rol shifti parol tiklashda ham amal qiladi — ADMIN egaga tegolmaydi."""
    headers = await _auth(client, ADMIN_LOGIN, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/staff/{world['owner']}/password",
        json={"password": "yangi mustahkam parol"},
        headers=headers,
    )
    assert r.status_code == 403, r.text
    assert r.json()["error"]["code"] == "ROLE_NOT_ALLOWED"


@skip_no_db
async def test_owner_lists_club_staff(client: httpx.AsyncClient, world: dict[str, int]) -> None:
    headers = await _auth(client, OWNER_LOGIN, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/staff", json=_payload(), headers=headers
    )
    assert created.status_code == 201, created.text

    r = await client.get(f"/api/v1/clubs/{world['club']}/staff", headers=headers)
    assert r.status_code == 200, r.text
    logins = {row["login"] for row in r.json()}
    assert {OWNER_LOGIN, ADMIN_LOGIN, "prov.kassa"} <= logins


@skip_no_db
async def test_admin_cannot_create_another_admin(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Rol shifti: ADMIN o'ziga teng rol bera olmaydi."""
    headers = await _auth(client, ADMIN_LOGIN, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/staff",
        json=_payload(role="ADMIN", login="prov.boshqa"),
        headers=headers,
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "ROLE_NOT_ALLOWED"


@skip_no_db
async def test_admin_can_create_staff(client: httpx.AsyncClient, world: dict[str, int]) -> None:
    headers = await _auth(client, ADMIN_LOGIN, world["club"])
    r = await client.post(
        f"/api/v1/clubs/{world['club']}/staff",
        json=_payload(login="prov.xodim2"),
        headers=headers,
    )
    assert r.status_code == 201, r.text


@skip_no_db
async def test_path_club_must_match_header(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Yo'ldagi klub va `X-Club-Id` bir xil bo'lmasa — rad."""
    headers = await _auth(client, OWNER_LOGIN, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club'] + 1}/staff", json=_payload(), headers=headers
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CLUB_MISMATCH"


@skip_no_db
async def test_duplicate_login_is_reported_only_on_save(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Bandlik faqat saqlashda aytiladi — jonli tekshiruv endpointi YO'Q."""
    headers = await _auth(client, OWNER_LOGIN, world["club"])
    first = await client.post(
        f"/api/v1/clubs/{world['club']}/staff", json=_payload(), headers=headers
    )
    assert first.status_code == 201

    again = await client.post(
        f"/api/v1/clubs/{world['club']}/staff", json=_payload(), headers=headers
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "LOGIN_TAKEN"


@skip_no_db
async def test_short_password_is_rejected_before_account_is_created(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _auth(client, OWNER_LOGIN, world["club"])
    r = await client.post(
        f"/api/v1/clubs/{world['club']}/staff",
        json=_payload(password="qisqa", login="prov.qisqa"),
        headers=headers,
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "PASSWORD_TOO_SHORT"

    # Hisob yaratilmagan bo'lishi kerak
    signed = await client.post(
        "/api/v1/auth/staff/login", json={"login": "prov.qisqa", "password": "qisqa"}
    )
    assert signed.status_code == 401
