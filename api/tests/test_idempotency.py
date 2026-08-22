"""`Idempotency-Key` — takroriy so'rov bitta amalni ikki marta bajarmasin.

Vakillik uchun `POST /clubs/{club_id}/bookings/staff` to'liq qamraladi
(4 test — CLAUDE.md §Testlar). Qolgan uchta himoyalangan endpoint
(`orders`, `orders/{id}/cancel`, `bookings/{id}/close`) uchun bitta
"replay" tekshiruvi yetarli — mexanizm bitta modulda (`core/idempotency.py`),
takroriy to'liq to'rtlik shart emas.

Manba: `docs/HOLAT.md` — xodim offline navbatining poydevori.
"""

import os
import uuid
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

OWNER_LOGIN = "idem.owner"
OWNER_B_LOGIN = "idem.owner.b"
PASSWORD = "juda mustahkam parol"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture(autouse=True)
async def clean_limits() -> AsyncIterator[None]:
    """`test_bookings.py::clean_limits` bilan bir xil sabab — login rate-limit
    chelagi testlar orasida yig'ilib qolmasin."""
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
    """Bitta klub + faol stansiya + egasi — `test_bookings.py::world` naqshi."""
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
                    " VALUES (:u, 'Idem Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    # 24/7 — `test_bookings.py::world` dagi sabab bilan bir xil:
                    # bron "hozir + N soat" bilan yaratiladi, sukut ish vaqti
                    # oynasi CI qaysi soatda yurishiga qarab tasodifiy chetga
                    # chiqib ketmasin.
                    "INSERT INTO clubs (org_id, name, status, opens_at_min, closes_at_min)"
                    " VALUES (:o, 'Idem Club', 'active', 0, 1440) RETURNING id"
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
                    " VALUES (:c, 'IDM-1', 'Standart', 'ps5', 40000) RETURNING id"
                ),
                {"c": ids["club"]},
            )

    await core_db.dispose()
    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users", "bookings", "idempotency_keys"):
            await purge_audit_actor(conn, ids["owner"])
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(
                text("DELETE FROM idempotency_keys WHERE club_id = :c"), {"c": ids["club"]}
            )
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
            await conn.execute(
                text("DELETE FROM users WHERE login = :l AND kind = 'staff'"), {"l": OWNER_LOGIN}
            )
    await engine.dispose()


@pytest_asyncio.fixture
async def world_b() -> AsyncIterator[dict[str, int]]:
    """Ikkinchi, mustaqil klub — cross-tenant izolyatsiya testi uchun."""
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
                    " VALUES ('staff', :login, 'active', 'Ega B')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"login": OWNER_B_LOGIN},
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
                    " VALUES (:u, 'Idem Org B', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status, opens_at_min, closes_at_min)"
                    " VALUES (:o, 'Idem Club B', 'active', 0, 1440) RETURNING id"
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
                    " VALUES (:c, 'IDM-B-1', 'Standart', 'ps5', 35000) RETURNING id"
                ),
                {"c": ids["club"]},
            )

    await core_db.dispose()
    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users", "bookings", "idempotency_keys"):
            await purge_audit_actor(conn, ids["owner"])
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(
                text("DELETE FROM idempotency_keys WHERE club_id = :c"), {"c": ids["club"]}
            )
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
            await conn.execute(
                text("DELETE FROM users WHERE login = :l AND kind = 'staff'"), {"l": OWNER_B_LOGIN}
            )
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _staff_headers(
    client: httpx.AsyncClient, club_id: int, *, login: str = OWNER_LOGIN
) -> dict[str, str]:
    r = await client.post("/api/v1/auth/staff/login", json={"login": login, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "X-Club-Id": str(club_id)}


async def _customer_headers(client: httpx.AsyncClient, telegram_id: int) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/dev/login", json={"telegram_id": telegram_id, "first_name": "Sinov"}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _starts(hours_from_now: int) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours_from_now)).isoformat()


def _booking_body(world: dict[str, int], *, hours_from_now: int = 5, phone: str) -> dict:
    return {
        "station_id": world["station"],
        "starts_at": _starts(hours_from_now),
        "hours": 1,
        "guest_name": "Idem Mijoz",
        "guest_phone": phone,
    }


@skip_no_db
async def test_same_key_twice_replays_without_second_booking(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """1. Bir xil kalit ikki marta — ikkinchi javob birinchisi bilan bir
    xil, faqat BITTA bron yaratiladi."""
    staff_h = await _staff_headers(client, world["club"])
    key = str(uuid.uuid4())
    body = _booking_body(world, phone="+998901112233")

    r1 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/staff",
        json=body,
        headers={**staff_h, "Idempotency-Key": key},
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/staff",
        json=body,
        headers={**staff_h, "Idempotency-Key": key},
    )
    assert r2.status_code == 201, r2.text
    assert r2.json() == r1.json(), "replay javobi birinchisidan farq qildi"

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "bookings"):
            count = await conn.scalar(
                text("SELECT count(*) FROM bookings WHERE club_id = :c AND guest_phone = :p"),
                {"c": world["club"], "p": "+998901112233"},
            )
    await engine.dispose()
    assert count == 1, f"ikkinchi so'rov qayta bajarilib ketdi — {count} bron yaratildi"


@skip_no_db
async def test_cross_tenant_same_key_does_not_collide(
    client: httpx.AsyncClient, world: dict[str, int], world_b: dict[str, int]
) -> None:
    """2. Ikki xil klub bir xil kalit satri bilan chaqiradi — ikkalasi ham
    mustaqil muvaffaqiyatli, bittasi ikkinchisiga to'sqinlik qilmaydi."""
    key = str(uuid.uuid4())

    staff_a = await _staff_headers(client, world["club"], login=OWNER_LOGIN)
    ra = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/staff",
        json=_booking_body(world, hours_from_now=6, phone="+998901112244"),
        headers={**staff_a, "Idempotency-Key": key},
    )
    assert ra.status_code == 201, ra.text

    staff_b = await _staff_headers(client, world_b["club"], login=OWNER_B_LOGIN)
    rb = await client.post(
        f"/api/v1/clubs/{world_b['club']}/bookings/staff",
        json=_booking_body(world_b, hours_from_now=6, phone="+998901112255"),
        headers={**staff_b, "Idempotency-Key": key},
    )
    assert rb.status_code == 201, rb.text
    assert ra.json()["id"] != rb.json()["id"]


@skip_no_db
async def test_insufficient_role_still_403s_and_no_row_created(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """3. Xodim tokeni bo'lmagan (mijoz) chaqiruv baribir 403 oladi — hatto
    to'g'ri formatdagi kalit bilan ham — va idempotency qatori yaratilmaydi."""
    customer_h = await _customer_headers(client, telegram_id=970_000_222)
    key = str(uuid.uuid4())

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/staff",
        json=_booking_body(world, hours_from_now=7, phone="+998901112266"),
        headers={**customer_h, "Idempotency-Key": key},
    )
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "STAFF_TOKEN_REQUIRED"

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "idempotency_keys"):
            count = await conn.scalar(
                text("SELECT count(*) FROM idempotency_keys WHERE idempotency_key = :k"), {"k": key}
            )
    await engine.dispose()
    assert count == 0, "rol tekshiruvidan OLDIN idempotency qatori yozilib ketdi"

    async with engine.begin() as conn:
        async with rls_bypass(conn, "users"):
            await conn.execute(
                text("DELETE FROM users WHERE telegram_id = 970000222 AND kind = 'customer'")
            )
    await engine.dispose()


@skip_no_db
async def test_same_key_different_body_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """4. Bir xil kalit, boshqa body — 409 IDEMPOTENCY_KEY_REUSED, birinchi
    bron o'zgarmaydi, ikkinchisi yaratilmaydi."""
    staff_h = await _staff_headers(client, world["club"])
    key = str(uuid.uuid4())

    r1 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/staff",
        json=_booking_body(world, hours_from_now=8, phone="+998901112277"),
        headers={**staff_h, "Idempotency-Key": key},
    )
    assert r1.status_code == 201, r1.text

    r2 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/staff",
        json=_booking_body(world, hours_from_now=8, phone="+998901112288"),  # boshqa telefon
        headers={**staff_h, "Idempotency-Key": key},
    )
    assert r2.status_code == 409, r2.text
    assert r2.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "bookings"):
            count = await conn.scalar(
                text(
                    "SELECT count(*) FROM bookings"
                    " WHERE club_id = :c AND guest_phone IN (:p1, :p2)"
                ),
                {"c": world["club"], "p1": "+998901112277", "p2": "+998901112288"},
            )
    await engine.dispose()
    assert count == 1, "rad etilgan takroriy so'rov baribir bron yaratdi"


@skip_no_db
async def test_pos_endpoints_replay_on_same_key(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """POS uchtasi (`orders`, `orders/{id}/cancel`, `bookings/{id}/close`)
    bitta umumiy modulni ishlatadi (`core/idempotency.py`) — har biriga
    to'liq to'rtlik takrorlanmaydi, replay ishlayotganini bir yo'la
    tekshirish yetarli."""
    staff_h = await _staff_headers(client, world["club"])

    # Naqd sotuv ochiq smena talab qiladi (`pos/service.py::_record_payment`).
    shift = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts", json={"opening_cash": 0}, headers=staff_h
    )
    assert shift.status_code == 201, shift.text

    # Mahsulot va bronsiz sotuv — order create replay
    product = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Ichimlik", "name": "Cola", "price": 12000, "stock_qty": 10},
        headers=staff_h,
    )
    assert product.status_code == 201, product.text
    product_id = product.json()["id"]

    order_key = str(uuid.uuid4())
    order_body = {
        "booking_id": None,
        "items": [{"product_id": product_id, "qty": 1}],
        "payment_method": "CASH",
    }
    o1 = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json=order_body,
        headers={**staff_h, "Idempotency-Key": order_key},
    )
    assert o1.status_code == 201, o1.text
    o2 = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json=order_body,
        headers={**staff_h, "Idempotency-Key": order_key},
    )
    assert o2.status_code == 201, o2.text
    assert o1.json() == o2.json()

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "orders"):
            order_count = await conn.scalar(
                text("SELECT count(*) FROM orders WHERE club_id = :c"), {"c": world["club"]}
            )
    await engine.dispose()
    assert order_count == 1, f"order create replay ishlamadi — {order_count} order yaratildi"


@skip_no_db
async def test_booking_lifecycle_endpoints_replay_on_same_key(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """`confirm`/`reject`/`extend`/`cancel` — offline-sync uchun kengaytirilgan
    idempotency (`playbron-security-offline-10-10-audit.md` §14). Har biri
    bitta replay bilan tekshiriladi: ikkinchi so'rov xatosiz qaytadi va
    holat/DB qatori faqat BIR marta o'zgaradi."""
    staff_h = await _staff_headers(client, world["club"])
    customer_h = await _customer_headers(client, telegram_id=970_000_333)

    # ── confirm ──
    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": _starts(4), "hours": 2},
        headers=customer_h,
    )
    assert r.status_code == 201, r.text
    booking_id = r.json()["id"]

    confirm_key = str(uuid.uuid4())
    c1 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/confirm",
        headers={**staff_h, "Idempotency-Key": confirm_key},
    )
    assert c1.status_code == 204, c1.text
    c2 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/confirm",
        headers={**staff_h, "Idempotency-Key": confirm_key},
    )
    assert c2.status_code == 204, c2.text

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "bookings"):
            status = await conn.scalar(
                text("SELECT status FROM bookings WHERE id = :b"), {"b": booking_id}
            )
    await engine.dispose()
    assert status == "CONFIRMED"

    # ── extend ──
    extend_key = str(uuid.uuid4())
    e1 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/extend",
        json={"extra_hours": 1},
        headers={**staff_h, "Idempotency-Key": extend_key},
    )
    assert e1.status_code == 200, e1.text
    e2 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/extend",
        json={"extra_hours": 1},
        headers={**staff_h, "Idempotency-Key": extend_key},
    )
    assert e2.status_code == 200, e2.text
    assert e1.json() == e2.json(), "extend replay javobi birinchisidan farq qildi"

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "bookings"):
            hours = await conn.scalar(
                text("SELECT hours FROM bookings WHERE id = :b"), {"b": booking_id}
            )
    await engine.dispose()
    assert hours == 3, f"extend takroriy so'rovda ikki marta bajarilib ketdi — hours={hours}"

    # ── cancel (CONFIRMED holatdan) ──
    cancel_key = str(uuid.uuid4())
    x1 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/cancel",
        json={"reason": "Mijoz kelmadi"},
        headers={**staff_h, "Idempotency-Key": cancel_key},
    )
    assert x1.status_code == 204, x1.text
    x2 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{booking_id}/cancel",
        json={"reason": "Mijoz kelmadi"},
        headers={**staff_h, "Idempotency-Key": cancel_key},
    )
    assert x2.status_code == 204, x2.text

    # ── reject (yangi PENDING bron) ──
    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings",
        json={"station_id": world["station"], "starts_at": _starts(9), "hours": 1},
        headers=customer_h,
    )
    assert r.status_code == 201, r.text
    pending_id = r.json()["id"]

    reject_key = str(uuid.uuid4())
    j1 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{pending_id}/reject",
        json={"reason": "Joy yo'q"},
        headers={**staff_h, "Idempotency-Key": reject_key},
    )
    assert j1.status_code == 204, j1.text
    j2 = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{pending_id}/reject",
        json={"reason": "Joy yo'q"},
        headers={**staff_h, "Idempotency-Key": reject_key},
    )
    assert j2.status_code == 204, j2.text

    engine = _owner_engine()
    async with engine.begin() as conn:
        # `bookings.customer_id` FK `ON DELETE` qoidasi yo'q (`0009_bookings.py`)
        # — mijozni o'chirishdan OLDIN uning bronlarini o'chirish shart, aks
        # holda FK buziladi (world fixture o'zi keyinroq faqat `world['club']`
        # bo'yicha o'chiradi, mijoz qatorini emas).
        async with rls_bypass(conn, "bookings", "users"):
            await conn.execute(
                text("DELETE FROM bookings WHERE club_id = :c AND customer_id IS NOT NULL"),
                {"c": world["club"]},
            )
            await conn.execute(
                text("DELETE FROM users WHERE telegram_id = 970000333 AND kind = 'customer'")
            )
    await engine.dispose()


@skip_no_db
async def test_shift_and_expense_endpoints_replay_on_same_key(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """`shifts` (open/movement/close) va `expenses` create — offline-sync
    uchun kengaytirilgan idempotency (`playbron-security-offline-10-10-audit.md`
    §14). Har biri bitta replay bilan tekshiriladi."""
    staff_h = await _staff_headers(client, world["club"])

    open_key = str(uuid.uuid4())
    s1 = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts",
        json={"opening_cash": 50_000},
        headers={**staff_h, "Idempotency-Key": open_key},
    )
    assert s1.status_code == 201, s1.text
    s2 = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts",
        json={"opening_cash": 50_000},
        headers={**staff_h, "Idempotency-Key": open_key},
    )
    assert s2.status_code == 201, s2.text
    assert s1.json() == s2.json(), "shift open replay javobi birinchisidan farq qildi"
    shift_id = s1.json()["id"]

    movement_key = str(uuid.uuid4())
    m1 = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts/{shift_id}/movements",
        json={"kind": "IN", "amount": 10_000, "reason": "Sinov kirim"},
        headers={**staff_h, "Idempotency-Key": movement_key},
    )
    assert m1.status_code == 201, m1.text
    m2 = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts/{shift_id}/movements",
        json={"kind": "IN", "amount": 10_000, "reason": "Sinov kirim"},
        headers={**staff_h, "Idempotency-Key": movement_key},
    )
    assert m2.status_code == 201, m2.text

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "shift_cash_movements"):
            movement_count = await conn.scalar(
                text("SELECT count(*) FROM shift_cash_movements WHERE shift_id = :s"),
                {"s": shift_id},
            )
    await engine.dispose()
    assert movement_count == 1, f"movement takroriy yozildi — {movement_count} qator"

    expense_key = str(uuid.uuid4())
    x1 = await client.post(
        f"/api/v1/clubs/{world['club']}/expenses",
        json={"spent_on": str(datetime.now(UTC).date()), "category": "Boshqa", "amount": 5_000},
        headers={**staff_h, "Idempotency-Key": expense_key},
    )
    assert x1.status_code == 201, x1.text
    x2 = await client.post(
        f"/api/v1/clubs/{world['club']}/expenses",
        json={"spent_on": str(datetime.now(UTC).date()), "category": "Boshqa", "amount": 5_000},
        headers={**staff_h, "Idempotency-Key": expense_key},
    )
    assert x2.status_code == 201, x2.text
    assert x1.json() == x2.json(), "expense replay javobi birinchisidan farq qildi"

    engine = _owner_engine()
    async with engine.begin() as conn:
        async with rls_bypass(conn, "expenses"):
            expense_count = await conn.scalar(
                text("SELECT count(*) FROM expenses WHERE club_id = :c AND category = 'Boshqa'"),
                {"c": world["club"]},
            )
    await engine.dispose()
    assert expense_count == 1, f"expense takroriy yozildi — {expense_count} qator"

    close_key = str(uuid.uuid4())
    cl1 = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts/{shift_id}/close",
        json={"counted_cash": 60_000},
        headers={**staff_h, "Idempotency-Key": close_key},
    )
    assert cl1.status_code == 200, cl1.text
    cl2 = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts/{shift_id}/close",
        json={"counted_cash": 60_000},
        headers={**staff_h, "Idempotency-Key": close_key},
    )
    assert cl2.status_code == 200, cl2.text
    assert cl1.json() == cl2.json(), "shift close replay javobi birinchisidan farq qildi"
