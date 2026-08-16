"""Bron oqimi — mijoz to'lovsiz bron qiladi, xodim tasdiqlaydi/rad etadi,
xodim qo'lda ham bron ocha oladi.

Manba: `api/migrations/versions/0009_bookings.py`, loyiha egasining
so'rovi (2026-08-15).
"""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

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

OWNER_LOGIN = "bkg.owner"
PASSWORD = "juda mustahkam parol"
CUSTOMER_TG = 960_000_111


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture(autouse=True)
async def clean_limits() -> AsyncIterator[None]:
    """Har test o'z login chelagini boshidan boshlasin.

    Bir xil `OWNER_LOGIN` bir nechta test bo'ylab qayta ishlatiladi
    (`world` fixture'i uni ON CONFLICT bilan qayta faollashtiradi) — usiz
    `login:ip-acct` (5/5daq) chelaklari testlar orasida yig'ilib, keyingi
    testning HAQIQIY 200 kirishi 429 RATE_LIMITED bo'lib qolardi.
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
async def world() -> AsyncIterator[dict[str, int]]:
    """Klub, faol stansiya, egasi — bittasi ham tabiiy aktordan yaratilmagan."""
    engine = _owner_engine()
    ids: dict[str, int] = {}
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        async with rls_bypass(
            conn, "users", "organizations", "clubs", "memberships", "stations", "staff_credentials"
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
                    " VALUES (:u, 'Bkg Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status)"
                    " VALUES (:o, 'Bkg Club', 'active') RETURNING id"
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
                    " VALUES (:c, 'BKG-1', 'Standart', 'ps5', 40000) RETURNING id"
                ),
                {"c": ids["club"]},
            )

    # `rls_bypass()` yuqorida `ALTER TABLE ... NO FORCE/FORCE ROW LEVEL
    # SECURITY` bilan DDL bajardi. Ilovaning O'ZINING ulanish hovuzi
    # (`app_engine`) bu paytda ochiq turishi mumkin va asyncpg'ning
    # tayyorlangan bayonot keshi eski katalog holatiga ishora qilib
    # qolishi mumkin — keyingi so'rov (masalan mijoz `/auth/dev/login`)
    # "there is no unique or exclusion constraint matching the ON CONFLICT
    # specification" kabi tushunarsiz xato berardi. Faqat SHU sinov
    # muhitiga xos: prodda runtime'da FORCE RLS hech qachon almashtirilmaydi.
    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users", "bookings"):
            customer_id = await conn.scalar(
                text("SELECT id FROM users WHERE telegram_id = :tg AND kind = 'customer'"),
                {"tg": CUSTOMER_TG},
            )
            # `audit_log_actor_user_id_fkey` NO ACTION — sinov davomida
            # yozilgan amallar (masalan `station_updated`) aktyorni o'chirishdan
            # OLDIN tozalanishi shart (`conftest.py::purge_audit_actor`).
            await purge_audit_actor(conn, ids["owner"], customer_id)
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
            await conn.execute(
                text("DELETE FROM users WHERE login = :l AND kind = 'staff'"), {"l": OWNER_LOGIN}
            )
            await conn.execute(
                text("DELETE FROM users WHERE telegram_id = :tg AND kind = 'customer'"),
                {"tg": CUSTOMER_TG},
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


async def _customer_headers(client: httpx.AsyncClient) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/dev/login", json={"telegram_id": CUSTOMER_TG, "first_name": "Sinov"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _starts(hours_from_now: int) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours_from_now)).isoformat()


@skip_no_db
async def test_customer_creates_pending_booking_staff_confirms(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    customer_h = await _customer_headers(client)
    staff_h = await _staff_headers(client, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": _starts(4), "hours": 2},
        headers=customer_h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "PENDING"
    assert body["prepaid_amount"] == 0, "to'lovsiz oqim — Bosqich 1"
    booking_id = body["id"]

    r = await client.get(f"/api/v1/clubs/{world['club']}/bookings/pending", headers=staff_h)
    assert r.status_code == 200
    assert any(b["id"] == booking_id for b in r.json())

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/confirm", headers=staff_h
    )
    assert r.status_code == 204

    r = await client.get("/api/v1/me/bookings", headers=customer_h)
    assert r.status_code == 200
    mine = next(b for b in r.json() if b["id"] == booking_id)
    assert mine["status"] == "CONFIRMED"


@skip_no_db
async def test_overlapping_slot_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    customer_h = await _customer_headers(client)
    starts = _starts(5)

    first = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": starts, "hours": 2},
        headers=customer_h,
    )
    assert first.status_code == 201

    again = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": starts, "hours": 1},
        headers=customer_h,
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "SLOT_TAKEN"


@skip_no_db
async def test_staff_creates_walkin_booking_confirmed_immediately(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Telefon/kelib bron qilgan mijoz — xodim ochadi, ikkinchi tasdiq shart emas."""
    staff_h = await _staff_headers(client, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/staff",
        json={
            "station_id": world["station"],
            "starts_at": _starts(6),
            "hours": 1,
            "guest_name": "Kelgan Mijoz",
            "guest_phone": "+998907654321",
        },
        headers=staff_h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "CONFIRMED"
    assert body["guest_name"] == "Kelgan Mijoz"


@skip_no_db
async def test_customer_cannot_use_staff_endpoint(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    customer_h = await _customer_headers(client)

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/staff",
        json={
            "station_id": world["station"],
            "starts_at": _starts(7),
            "hours": 1,
            "guest_name": "X",
            "guest_phone": "+998900000000",
        },
        headers=customer_h,
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "STAFF_TOKEN_REQUIRED"


@skip_no_db
async def test_staff_cannot_use_customer_endpoint(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    staff_h = await _staff_headers(client, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": _starts(8), "hours": 1},
        headers=staff_h,
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "CUSTOMER_TOKEN_REQUIRED"


@skip_no_db
async def test_reject_marks_cancelled_and_confirm_afterwards_fails(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    customer_h = await _customer_headers(client)
    staff_h = await _staff_headers(client, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": _starts(9), "hours": 1},
        headers=customer_h,
    )
    booking_id = created.json()["id"]

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/reject",
        json={"reason": "xona ta'mirda"},
        headers=staff_h,
    )
    assert r.status_code == 204

    r = await client.get("/api/v1/me/bookings", headers=customer_h)
    mine = next(b for b in r.json() if b["id"] == booking_id)
    assert mine["status"] == "CANCELLED"

    again = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/confirm", headers=staff_h
    )
    assert again.status_code == 403
    assert again.json()["error"]["code"] == "BOOKING_NOT_PENDING"


@skip_no_db
async def test_stations_are_publicly_readable_for_active_club(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Token yo'q — klub `active` bo'lgani uchun ko'rinadi."""
    r = await client.get(f"/api/v1/clubs/{world['club']}/stations")
    assert r.status_code == 200
    assert any(s["id"] == world["station"] for s in r.json())


@skip_no_db
async def test_owner_publishes_draft_club_with_station(client: httpx.AsyncClient) -> None:
    """`draft` klub — egasi o'zi faollashtiradi, super admin shart emas."""
    engine = _owner_engine()
    ids: dict[str, int] = {}
    password_hash = await hash_password(PASSWORD)

    async with engine.begin() as conn:
        async with rls_bypass(
            conn, "users", "organizations", "clubs", "memberships", "staff_credentials"
        ):
            ids["owner"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', 'pub.owner', 'active', 'Pub')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                )
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
                    " VALUES (:u, 'Pub Org', 'pending', NULL) RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status) VALUES (:o, 'Pub Club', 'draft')"
                    " RETURNING id"
                ),
                {"o": ids["org"]},
            )
            await conn.execute(
                text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"),
                {"u": ids["owner"], "c": ids["club"]},
            )
    await core_db.dispose()

    try:
        signed = await client.post(
            "/api/v1/auth/staff/login", json={"login": "pub.owner", "password": PASSWORD}
        )
        assert signed.status_code == 200, signed.text
        headers = {
            "Authorization": f"Bearer {signed.json()['access_token']}",
            "X-Club-Id": str(ids["club"]),
        }

        # `draft` klub — ochiq /clubs ro'yxatida yo'q, lekin egasi
        # `GET /clubs/{id}` orqali status'ini ko'radi
        detail = await client.get(f"/api/v1/clubs/{ids['club']}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["status"] == "draft"

        # Xonasiz — rad etiladi
        r = await client.post(f"/api/v1/clubs/{ids['club']}/publish", headers=headers)
        assert r.status_code == 409
        assert r.json()["error"]["code"] == "CLUB_NO_STATIONS"

        async with engine.begin() as conn:
            async with rls_bypass(conn, "stations"):
                await conn.execute(
                    text(
                        "INSERT INTO stations (club_id, code, console_type, rate, status)"
                        " VALUES (:c, 'PUB-1', 'ps5', 30000, 'active')"
                    ),
                    {"c": ids["club"]},
                )
        await core_db.dispose()

        r = await client.post(f"/api/v1/clubs/{ids['club']}/publish", headers=headers)
        assert r.status_code == 204, r.text

        # Endi ochiq katalogda ko'rinadi
        catalog = await client.get("/api/v1/clubs")
        assert any(c["id"] == ids["club"] for c in catalog.json())
    finally:
        async with engine.begin() as conn:
            async with rls_bypass(conn, "organizations", "users", "stations"):
                await purge_audit_actor(conn, ids.get("owner"))
                await conn.execute(
                    text("DELETE FROM stations WHERE club_id = :c"), {"c": ids["club"]}
                )
                await conn.execute(
                    text("DELETE FROM organizations WHERE id = :o"), {"o": ids["org"]}
                )
                await conn.execute(
                    text("DELETE FROM users WHERE login = 'pub.owner' AND kind = 'staff'")
                )
        await engine.dispose()


@skip_no_db
async def test_active_club_appears_in_public_catalog(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Mijoz ilovasidagi klub katalogi — `GET /clubs`, tokensiz."""
    r = await client.get("/api/v1/clubs")
    assert r.status_code == 200
    body = r.json()
    listed = next((c for c in body if c["id"] == world["club"]), None)
    assert listed is not None, "faol klub katalogda ko'rinishi kerak"
    assert listed["name"] == "Bkg Club"


@skip_no_db
async def test_owner_updates_club_info(client: httpx.AsyncClient, world: dict[str, int]) -> None:
    staff_h = await _staff_headers(client, world["club"])
    r = await client.patch(
        f"/api/v1/clubs/{world['club']}",
        json={
            "name": "Bkg Club Yangi",
            "address": "Toshkent, Yangi ko‘cha",
            "phone": "+998901234567",
            "about": "Yangilangan tavsif",
            "opens_at_min": 9 * 60,
            "closes_at_min": 25 * 60,
            "google_maps_url": "https://maps.google.com/?q=41.3,69.2",
            "yandex_maps_url": "https://yandex.uz/maps/?ll=69.2,41.3",
        },
        headers=staff_h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Bkg Club Yangi"
    assert body["opens_at_min"] == 9 * 60
    assert body["google_maps_url"] == "https://maps.google.com/?q=41.3,69.2"
    assert body["yandex_maps_url"] == "https://yandex.uz/maps/?ll=69.2,41.3"

    r = await client.get("/api/v1/clubs")
    listed = next(c for c in r.json() if c["id"] == world["club"])
    assert listed["name"] == "Bkg Club Yangi"
    assert listed["google_maps_url"] == "https://maps.google.com/?q=41.3,69.2"


@skip_no_db
async def test_club_maps_url_must_be_https(client: httpx.AsyncClient, world: dict[str, int]) -> None:
    staff_h = await _staff_headers(client, world["club"])
    r = await client.patch(
        f"/api/v1/clubs/{world['club']}",
        json={
            "name": "Bkg Club",
            "address": "",
            "phone": None,
            "about": "",
            "opens_at_min": 9 * 60,
            "closes_at_min": 25 * 60,
            "google_maps_url": "javascript:alert(1)",
        },
        headers=staff_h,
    )
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "MAPS_URL_INVALID"


@skip_no_db
async def test_owner_manages_stations(client: httpx.AsyncClient, world: dict[str, int]) -> None:
    staff_h = await _staff_headers(client, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/stations",
        json={"code": "BKG-9", "room_label": "VIP", "console_type": "ps5pro", "rate": 90000},
        headers=staff_h,
    )
    assert created.status_code == 201, created.text
    station_id = created.json()["id"]

    updated = await client.patch(
        f"/api/v1/clubs/{world['club']}/stations/{station_id}",
        json={
            "room_label": "VIP",
            "console_type": "ps5pro",
            "rate": 95000,
            "status": "maintenance",
        },
        headers=staff_h,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "maintenance"

    # `maintenance` — ochiq ro'yxatda ko'rinmaydi, boshqaruv ro'yxatida ko'rinadi
    public = await client.get(f"/api/v1/clubs/{world['club']}/stations")
    assert not any(s["id"] == station_id for s in public.json())

    managed = await client.get(f"/api/v1/clubs/{world['club']}/stations/manage", headers=staff_h)
    assert any(s["id"] == station_id and s["status"] == "maintenance" for s in managed.json())


@skip_no_db
async def test_hours_out_of_range_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    customer_h = await _customer_headers(client)
    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": _starts(10), "hours": 20},
        headers=customer_h,
    )
    # Pydantic `le=6` — 422 (schema darajasida), servis qatlamiga yetmaydi
    assert r.status_code == 422


@skip_no_db
async def test_past_start_time_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    customer_h = await _customer_headers(client)
    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={
            "station_id": world["station"],
            "starts_at": _starts(-3),
            "hours": 1,
        },
        headers=customer_h,
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "STARTS_AT_PAST"


# ── Live Board detali — buyurtma, uzaytirish, bekor qilish (reja #36) ──────


async def _walkin_booking(
    client: httpx.AsyncClient, staff_h: dict[str, str], club_id: int, station_id: int
) -> int:
    r = await client.post(
        f"/api/v1/clubs/{club_id}/bookings/staff",
        json={
            "station_id": station_id,
            "starts_at": _starts(0),
            "hours": 1,
            "guest_name": "Mehmon",
            "guest_phone": "+998901234567",
        },
        headers=staff_h,
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


@skip_no_db
async def test_booking_detail_includes_orders(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    staff_h = await _staff_headers(client, world["club"])
    booking_id = await _walkin_booking(client, staff_h, world["club"], world["station"])

    product = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Ichimlik", "name": "Detail Sinov Kola", "price": 15000},
        headers=staff_h,
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]

    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={"booking_id": booking_id, "items": [{"product_id": product_id, "qty": 2}]},
        headers=staff_h,
    )
    assert order.status_code == 201, order.text

    r = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/detail", headers=staff_h
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "CONFIRMED"
    assert body["hours"] == 1
    assert body["orders_amount"] == 30000
    assert body["play_amount"] == body["rate_snapshot"]
    assert body["total"] == body["play_amount"] + 30000
    assert any(
        item["product_name"] == "Detail Sinov Kola" and item["qty"] == 2 for item in body["items"]
    )


@skip_no_db
async def test_staff_extends_confirmed_booking(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    staff_h = await _staff_headers(client, world["club"])
    booking_id = await _walkin_booking(client, staff_h, world["club"], world["station"])

    before = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/detail", headers=staff_h
    )
    ends_before = before.json()["ends_at"]

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/extend",
        json={"extra_hours": 2},
        headers=staff_h,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["hours"] == 3
    assert body["ends_at"] > ends_before

    detail = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/detail", headers=staff_h
    )
    assert detail.json()["hours"] == 3


@skip_no_db
async def test_extend_out_of_range_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    staff_h = await _staff_headers(client, world["club"])
    booking_id = await _walkin_booking(client, staff_h, world["club"], world["station"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/extend",
        json={"extra_hours": 10},
        headers=staff_h,
    )
    assert r.status_code == 422, r.text  # Pydantic `le=EXTEND_MAX_HOURS`


@skip_no_db
async def test_staff_cancels_confirmed_booking_customer_not_arrived(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    staff_h = await _staff_headers(client, world["club"])
    booking_id = await _walkin_booking(client, staff_h, world["club"], world["station"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/cancel",
        json={"reason": "Mijoz kelmadi"},
        headers=staff_h,
    )
    assert r.status_code == 204, r.text

    detail = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/detail", headers=staff_h
    )
    assert detail.json()["status"] == "CANCELLED"

    # Bo'shagan xona — endi Live Board'da bo'sh ko'rinishi kerak
    live = await client.get(f"/api/v1/clubs/{world['club']}/live", headers=staff_h)
    assert live.status_code == 200, live.text
    station = next(s for s in live.json() if s["id"] == world["station"])
    assert station["booking_id"] is None


@skip_no_db
async def test_cancel_already_closed_booking_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    staff_h = await _staff_headers(client, world["club"])
    booking_id = await _walkin_booking(client, staff_h, world["club"], world["station"])

    closed = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/close",
        json={"payment_method": "CASH", "paid_amount": 0},
        headers=staff_h,
    )
    assert closed.status_code == 200, closed.text

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/cancel",
        json={},
        headers=staff_h,
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "BILL_ALREADY_CLOSED"
