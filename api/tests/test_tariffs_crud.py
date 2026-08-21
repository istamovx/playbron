"""Xonalar va tariflar CRUD — `0037_rooms_tariffs.py` ustidagi boshqaruv yo'li.

Jadval, RLS va narx hisobi (`modules/bookings/pricing.py`) `0033` dan beri
bor edi, lekin tarifni FAQAT xom SQL bilan kiritish mumkin edi
(`CLAUDE.md`, «Ma'lum texnik qarz»). Bu yerda o'sha yo'l sinaladi.

`CLAUDE.md` §Testlar talab qiladigan uchlik:
  1. amal ishlaydi — egasi xona va tarif yaratadi, ro'yxatda ko'radi;
  2. yetarli roli yo'q xodim `403` oladi — `STAFF` yozolmaydi;
  3. boshqa klub ko'rmaydi — begona a'zo na ro'yxatda ko'radi, na yozadi.
"""

import os
from collections.abc import AsyncIterator

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

OWNER_LOGIN = "trf.owner"
STAFF_LOGIN = "trf.kassir"
OTHER_LOGIN = "trf.begona"
LOGINS = [OWNER_LOGIN, STAFF_LOGIN, OTHER_LOGIN]
PASSWORD = "juda mustahkam parol"

ALL_DAYS = 0b111_1111
# Yarim tundan o'tuvchi oyna — `to_min > 1440` (`tariffs_window_ck`).
EVENING_FROM = 18 * 60
EVENING_TO = 26 * 60


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture(autouse=True)
async def clean_limits() -> AsyncIterator[None]:
    """Uchta login bir necha test bo'ylab qayta ishlatiladi — `login:ip-acct`
    chelaklari yig'ilib qolsa keyingi HAQIQIY kirish 429 bo'lardi."""
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
async def world() -> AsyncIterator[dict[str, int]]:
    """Ikki klub: birida egasi va `STAFF` rolli xodim, ikkinchisida begona egasi.

    Begona klub SHART: `rooms_read`/`tariffs_read` (`0033`) faol klub uchun
    ATAYLAB ochiq (mijoz narxni bron qilishdan oldin ko'rishi kerak) — ya'ni
    izolyatsiya YOZISHDA va boshqaruv ro'yxatida sinaladi, o'qish
    policy'sida emas.
    """
    engine = _owner_engine()
    ids: dict[str, int] = {}
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        async with rls_bypass(
            conn, "users", "organizations", "clubs", "memberships", "staff_credentials"
        ):

            async def account(login: str, first_name: str) -> int:
                user_id = await conn.scalar(
                    text(
                        "INSERT INTO users (kind, login, status, first_name)"
                        " VALUES ('staff', :login, 'active', :name)"
                        " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                        " DO UPDATE SET status = 'active' RETURNING id"
                    ),
                    {"login": login, "name": first_name},
                )
                await conn.execute(
                    text(
                        "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                        " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                        " SET password_hash = EXCLUDED.password_hash, must_change = false"
                    ),
                    {"uid": user_id, "h": password_hash},
                )
                return int(user_id)

            ids["owner"] = await account(OWNER_LOGIN, "Ega")
            ids["staff"] = await account(STAFF_LOGIN, "Kassir")
            ids["other_owner"] = await account(OTHER_LOGIN, "Begona ega")

            for key, owner_key, org_name, club_name in (
                ("org", "owner", "Trf Org", "Trf Club"),
                ("other_org", "other_owner", "Trf Begona Org", "Trf Begona Club"),
            ):
                ids[key] = await conn.scalar(
                    text(
                        "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                        " VALUES (:u, :n, 'active', 'gold') RETURNING id"
                    ),
                    {"u": ids[owner_key], "n": org_name},
                )
                club_key = "club" if key == "org" else "other_club"
                ids[club_key] = await conn.scalar(
                    text(
                        "INSERT INTO clubs (org_id, name, status)"
                        " VALUES (:o, :n, 'active') RETURNING id"
                    ),
                    {"o": ids[key], "n": club_name},
                )
                await conn.execute(
                    text(
                        "INSERT INTO memberships (user_id, club_id, role)"
                        " VALUES (:u, :c, 'OWNER')"
                    ),
                    {"u": ids[owner_key], "c": ids[club_key]},
                )

            # Kundalik ishni bajaradigan HAQIQIY `STAFF` roli: `rooms_write`
            # va `tariffs_write` uni umuman o'z ichiga olmaydi, guard esa
            # `require_admin` — faqat OWNER bilan sinash bu farqni yashirardi.
            await conn.execute(
                text(
                    "INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'STAFF')"
                    " ON CONFLICT (user_id, club_id) DO UPDATE SET status = 'active'"
                ),
                {"u": ids["staff"], "c": ids["club"]},
            )

    # `rls_bypass()` DDL bajardi — ilovaning ochiq hovuzidagi tayyorlangan
    # bayonot keshi eski katalogga ishora qilib qolmasin (`test_bookings.py`).
    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users"):
            await purge_audit_actor(conn, ids["owner"], ids["staff"], ids["other_owner"])
            # `rooms`/`tariffs`/`memberships` — `clubs.id` ga `ON DELETE
            # CASCADE`, klub esa tashkilotga; kaskad RLS'ga qaramaydi.
            await conn.execute(
                text("DELETE FROM organizations WHERE id = ANY(:ids)"),
                {"ids": [ids["org"], ids["other_org"]]},
            )
            await conn.execute(
                text("DELETE FROM users WHERE login = ANY(:l) AND kind = 'staff'"),
                {"l": LOGINS},
            )
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _auth(client: httpx.AsyncClient, login: str, club_id: int) -> dict[str, str]:
    r = await client.post("/api/v1/auth/staff/login", json={"login": login, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "X-Club-Id": str(club_id)}


def _room(name: str = "VIP-1", kind: str = "VIP") -> dict[str, object]:
    return {"name": name, "kind": kind, "sort": 1}


def _tariff(name: str = "Kechqurun") -> dict[str, object]:
    return {
        "name": name,
        "days_mask": ALL_DAYS,
        "from_min": EVENING_FROM,
        "to_min": EVENING_TO,
        "price_per_hour": 50_000,
        "priority": 10,
        "room_kind": "VIP",
    }


@skip_no_db
async def test_owner_creates_and_lists_room_and_tariff(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _auth(client, OWNER_LOGIN, world["club"])
    club = world["club"]

    created_room = await client.post(f"/api/v1/clubs/{club}/rooms", json=_room(), headers=headers)
    assert created_room.status_code == 201, created_room.text
    room = created_room.json()
    assert room["kind"] == "VIP"
    assert room["is_active"] is True

    created_tariff = await client.post(
        f"/api/v1/clubs/{club}/tariffs", json=_tariff(), headers=headers
    )
    assert created_tariff.status_code == 201, created_tariff.text
    tariff = created_tariff.json()
    # Pul JSON'da butun son (`CLAUDE.md`, «Pul»).
    assert tariff["price_per_hour"] == 50_000
    # Berilmagan cheklov `NULL` bo'lib qoladi — «har qanday konsolga».
    assert tariff["console_type"] is None
    assert tariff["to_min"] == EVENING_TO, "yarim tundan o'tuvchi oyna saqlanishi kerak"

    rooms = await client.get(f"/api/v1/clubs/{club}/rooms", headers=headers)
    assert rooms.status_code == 200, rooms.text
    assert any(r["id"] == room["id"] for r in rooms.json())

    tariffs = await client.get(f"/api/v1/clubs/{club}/tariffs", headers=headers)
    assert tariffs.status_code == 200, tariffs.text
    assert any(t["id"] == tariff["id"] for t in tariffs.json())


@skip_no_db
async def test_tariff_is_archived_not_deleted(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """O'chirish YO'Q — yopilgan bronlarning narxi shu qator orqali
    hisoblangan, shuning uchun `products` naqshi bilan `is_active`."""
    headers = await _auth(client, OWNER_LOGIN, world["club"])
    club = world["club"]

    created = await client.post(f"/api/v1/clubs/{club}/tariffs", json=_tariff(), headers=headers)
    assert created.status_code == 201, created.text
    tariff_id = created.json()["id"]

    archived = await client.patch(
        f"/api/v1/clubs/{club}/tariffs/{tariff_id}",
        json={**_tariff(), "is_active": False},
        headers=headers,
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["is_active"] is False

    listed = await client.get(f"/api/v1/clubs/{club}/tariffs", headers=headers)
    row = next(t for t in listed.json() if t["id"] == tariff_id)
    assert row["is_active"] is False, "boshqaruv ro'yxati nofaol tarifni ham ko'rsatadi"


@skip_no_db
async def test_broken_window_is_reported_not_500(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """`tariffs_window_ck` ni buzuvchi kirish barqaror kod bilan qaytadi."""
    headers = await _auth(client, OWNER_LOGIN, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/tariffs",
        json={**_tariff(), "from_min": 1200, "to_min": 1200},
        headers=headers,
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "TARIFF_WINDOW_INVALID"


@skip_no_db
async def test_staff_role_cannot_write_rooms_or_tariffs(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _auth(client, STAFF_LOGIN, world["club"])
    club = world["club"]

    room = await client.post(f"/api/v1/clubs/{club}/rooms", json=_room("Turnir"), headers=headers)
    assert room.status_code == 403, room.text
    assert room.json()["error"]["code"] == "ROLE_FORBIDDEN"

    tariff = await client.post(
        f"/api/v1/clubs/{club}/tariffs", json=_tariff("Kunduzi"), headers=headers
    )
    assert tariff.status_code == 403, tariff.text
    assert tariff.json()["error"]["code"] == "ROLE_FORBIDDEN"

    # O'qish ham boshqaruv ro'yxati — u ham `require_admin` ostida.
    listed = await client.get(f"/api/v1/clubs/{club}/tariffs", headers=headers)
    assert listed.status_code == 403, listed.text


@skip_no_db
async def test_another_clubs_member_sees_and_writes_nothing(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    owner_headers = await _auth(client, OWNER_LOGIN, world["club"])
    room = await client.post(
        f"/api/v1/clubs/{world['club']}/rooms", json=_room(), headers=owner_headers
    )
    assert room.status_code == 201, room.text
    tariff = await client.post(
        f"/api/v1/clubs/{world['club']}/tariffs", json=_tariff(), headers=owner_headers
    )
    assert tariff.status_code == 201, tariff.text

    other = await _auth(client, OTHER_LOGIN, world["other_club"])

    own_rooms = await client.get(f"/api/v1/clubs/{world['other_club']}/rooms", headers=other)
    assert own_rooms.status_code == 200, own_rooms.text
    assert all(r["id"] != room.json()["id"] for r in own_rooms.json())

    own_tariffs = await client.get(f"/api/v1/clubs/{world['other_club']}/tariffs", headers=other)
    assert own_tariffs.status_code == 200, own_tariffs.text
    assert all(t["id"] != tariff.json()["id"] for t in own_tariffs.json())

    # Begona klub yo'lini to'g'ridan-to'g'ri ko'rsatish ham ish bermaydi.
    direct = await client.get(f"/api/v1/clubs/{world['club']}/tariffs", headers=other)
    assert direct.status_code == 403, direct.text
    assert direct.json()["error"]["code"] == "CLUB_MISMATCH"

    await _assert_write_blocked_by_rls(
        user_id=world["other_owner"],
        club_id=world["other_club"],
        tariff_id=tariff.json()["id"],
        room_id=room.json()["id"],
    )


async def _assert_write_blocked_by_rls(
    *, user_id: int, club_id: int, tariff_id: int, room_id: int
) -> None:
    """Guard'ni chetlab o'tib, RLS'ning O'ZINI sinaymiz.

    `_assert_path_matches_header()` — qo'shimcha qatlam, HAKAM emas:
    policy'lar ilova roli (`playbron_app`) ostida ham to'sishi kerak.
    O'qish ATAYLAB ochiq (`*_read` faol klub uchun), shuning uchun bu
    yerda YOZISH tekshiriladi.
    """
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "SELECT set_config('app.user_id', :u, true),"
                    "       set_config('app.club_id', :c, true),"
                    "       set_config('app.telegram_id', '0', true),"
                    "       set_config('app.refresh_hash', '', true)"
                ),
                {"u": str(user_id), "c": str(club_id)},
            )
            wrote_tariff = (
                await conn.execute(
                    text("UPDATE tariffs SET price_per_hour = 1 WHERE id = :id RETURNING id"),
                    {"id": tariff_id},
                )
            ).first()
            wrote_room = (
                await conn.execute(
                    text("UPDATE rooms SET name = 'Bosib olindi' WHERE id = :id RETURNING id"),
                    {"id": room_id},
                )
            ).first()

        assert wrote_tariff is None, "begona klub tarifiga yozish RLS bilan to'silishi kerak"
        assert wrote_room is None, "begona klub xonasiga yozish RLS bilan to'silishi kerak"
    finally:
        await engine.dispose()
