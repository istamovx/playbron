"""POS — mahsulotlar, buyurtmalar, kassa (hisob yopish).

Manba: `api/migrations/versions/0013_pos.py`, loyiha egasining
so'rovi (2026-08-16).
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from conftest import rls_bypass
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

OWNER_LOGIN = "pos.owner"
PASSWORD = "juda mustahkam parol"


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
async def world() -> AsyncIterator[dict[str, int]]:
    """Klub, faol stansiya, egasi — bir bron CONFIRMED holatda (kassa uchun)."""
    engine = _owner_engine()
    ids: dict[str, int] = {}
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        async with rls_bypass(
            conn,
            "users",
            "organizations",
            "clubs",
            "memberships",
            "stations",
            "staff_credentials",
            "bookings",
        ):
            ids["owner"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', :login, 'active', 'Ega')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"login": OWNER_LOGIN},
            )
            await conn.execute(
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                    " SET password_hash = EXCLUDED.password_hash, must_change = false"
                ),
                {"uid": ids["owner"], "h": password_hash},
            )
            ids["org"] = await conn.scalar(
                text(
                    "INSERT INTO organizations (owner_user_id, name, status, plan_code)"
                    " VALUES (:u, 'Pos Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status)"
                    " VALUES (:o, 'Pos Club', 'active') RETURNING id"
                ),
                {"o": ids["org"]},
            )
            await conn.execute(
                text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"),
                {"u": ids["owner"], "c": ids["club"]},
            )
            ids["station"] = await conn.scalar(
                text(
                    "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                    " VALUES (:c, 'POS-1', 'Standart', 'ps5', 40000) RETURNING id"
                ),
                {"c": ids["club"]},
            )
            starts = datetime.now(UTC) - timedelta(minutes=10)
            ends = starts + timedelta(hours=2)
            ids["booking"] = await conn.scalar(
                text(
                    "INSERT INTO bookings (club_id, station_id, guest_name, guest_phone,"
                    " source, status, period, hours, rate_snapshot, created_by, confirmed_by,"
                    " confirmed_at)"
                    " VALUES (:c, :s, 'Mehmon', '+998900000000', 'STAFF', 'CONFIRMED',"
                    " tstzrange(:starts, :ends), 2, 40000, :u, :u, now()) RETURNING id"
                ),
                {
                    "c": ids["club"],
                    "s": ids["station"],
                    "starts": starts,
                    "ends": ends,
                    "u": ids["owner"],
                },
            )

    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(
            conn, "organizations", "users", "bookings", "stations", "products", "orders"
        ):
            await conn.execute(text("DELETE FROM orders WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(text("DELETE FROM products WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
            await conn.execute(
                text("DELETE FROM users WHERE login = :l AND kind = 'staff'"), {"l": OWNER_LOGIN}
            )
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _staff_headers(client: httpx.AsyncClient, club_id: int) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": OWNER_LOGIN, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "X-Club-Id": str(club_id)}


@skip_no_db
async def test_owner_creates_and_lists_products(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _staff_headers(client, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Ichimliklar", "name": "Pepsi 0.5", "price": 12000},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    product_id = r.json()["id"]

    listed = await client.get(f"/api/v1/clubs/{world['club']}/products", headers=headers)
    assert listed.status_code == 200
    assert any(p["id"] == product_id and p["name"] == "Pepsi 0.5" for p in listed.json())


@skip_no_db
async def test_order_created_advanced_and_billed(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _staff_headers(client, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Snack", "name": "Lay's", "price": 10000},
        headers=headers,
    )
    product_id = created.json()["id"]

    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={
            "booking_id": world["booking"],
            "items": [{"product_id": product_id, "qty": 2}],
        },
        headers=headers,
    )
    assert order.status_code == 201, order.text
    assert order.json()["status"] == "NEW"
    assert order.json()["total"] == 20000
    order_id = order.json()["id"]

    listed = await client.get(f"/api/v1/clubs/{world['club']}/orders", headers=headers)
    assert any(o["id"] == order_id for o in listed.json())

    advanced = await client.post(
        f"/api/v1/clubs/{world['club']}/orders/{order_id}/advance", headers=headers
    )
    assert advanced.status_code == 200
    assert advanced.json()["status"] == "ACCEPTED"

    # Kassa: ochiq bronlar ro'yxatida ko'rinadi
    open_bookings = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/open", headers=headers
    )
    assert any(b["id"] == world["booking"] for b in open_bookings.json())

    bill = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/bill", headers=headers
    )
    assert bill.status_code == 200, bill.text
    assert bill.json()["play_amount"] == 80000  # 40000 * 2 soat
    assert bill.json()["orders_amount"] == 20000
    assert bill.json()["total"] == 100000

    closed = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={"payment_method": "CASH", "paid_amount": 100000},
        headers=headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["total"] == 100000

    # Ikkinchi marta yopib bo'lmaydi
    again = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={"payment_method": "CASH", "paid_amount": 100000},
        headers=headers,
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "BILL_ALREADY_CLOSED"


@skip_no_db
async def test_live_board_shows_occupied_station(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _staff_headers(client, world["club"])

    r = await client.get(f"/api/v1/clubs/{world['club']}/live", headers=headers)
    assert r.status_code == 200, r.text
    station = next(s for s in r.json() if s["id"] == world["station"])
    assert station["booking_id"] == world["booking"]
    assert station["guest_label"] == "Mehmon"
