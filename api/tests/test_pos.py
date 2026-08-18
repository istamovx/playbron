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

OWNER_LOGIN = "pos.owner"
STAFF_LOGIN = "pos.kassir"
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
            # HAQIQIY `STAFF` rolli xodim ham kerak: kassa/buyurtma oqimini
            # kundalik ishda aynan U bajaradi, lekin RLS policy'lari OWNER
            # bilan bir xil EMAS (masalan `products_write` STAFF'ni umuman
            # o'z ichiga olmaydi). Faqat OWNER bilan sinash bu farqni
            # yashiradi — loyiha egasining hisoboti (2026-08-17): "xodim
            # yangi buyurtmani bekor qilganda xatolik yuz berdi".
            ids["staff"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', :login, 'active', 'Kassir')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"login": STAFF_LOGIN},
            )
            await conn.execute(
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                    " SET password_hash = EXCLUDED.password_hash, must_change = false"
                ),
                {"uid": ids["staff"], "h": password_hash},
            )
            await conn.execute(
                text(
                    "INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'STAFF')"
                    " ON CONFLICT (user_id, club_id) DO UPDATE SET status = 'active'"
                ),
                {"u": ids["staff"], "c": ids["club"]},
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
                    " source, status, period, hours, rate_snapshot, console_type, created_by,"
                    " confirmed_by, confirmed_at)"
                    " VALUES (:c, :s, 'Mehmon', '+998900000000', 'STAFF', 'CONFIRMED',"
                    " tstzrange(:starts, :ends), 2, 40000, 'ps5', :u, :u, now()) RETURNING id"
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
            await purge_audit_actor(conn, ids["owner"], ids.get("staff"))
            await conn.execute(text("DELETE FROM orders WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(text("DELETE FROM products WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :c"), {"c": ids["club"]})
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
            # IKKALA login ham o'chiriladi. Avval faqat `OWNER_LOGIN` bor
            # edi va yangi qo'shilgan xodim hisobi bazada qolib ketardi —
            # dev bazasi shu tarzda sinov hisoblari bilan to'lardi.
            await conn.execute(
                text("DELETE FROM users WHERE login = ANY(:l) AND kind = 'staff'"),
                {"l": [OWNER_LOGIN, STAFF_LOGIN]},
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


async def _kassir_headers(client: httpx.AsyncClient, club_id: int) -> dict[str, str]:
    """HAQIQIY `STAFF` roli — kundalik kassa ishini aynan u bajaradi.

    OWNER bilan sinash yetarli EMAS: RLS policy'lari rolga qarab farq
    qiladi (`products_write` STAFF'ni o'z ichiga olmaydi).
    """
    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": STAFF_LOGIN, "password": PASSWORD}
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
async def test_product_stock_is_tracked_and_returned_on_cancel(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Reja #48/#53 (loyiha egasi, 2026-08-16): mahsulot qo'shganda son
    kiritiladi, sotuvda kamayadi, buyurtma bekor qilinsa QAYTADI."""
    headers = await _staff_headers(client, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Snack", "name": "Sanoq Snack", "price": 9000, "stock_qty": 10},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    assert created.json()["stock_qty"] == 10
    product_id = created.json()["id"]

    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={"booking_id": world["booking"], "items": [{"product_id": product_id, "qty": 3}]},
        headers=headers,
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    listed = await client.get(f"/api/v1/clubs/{world['club']}/products", headers=headers)
    after_sale = next(p for p in listed.json() if p["id"] == product_id)
    assert after_sale["stock_qty"] == 7, "sotuvdan keyin qoldiq kamaymadi"

    cancelled = await client.post(
        f"/api/v1/clubs/{world['club']}/orders/{order_id}/cancel", headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"

    listed = await client.get(f"/api/v1/clubs/{world['club']}/products", headers=headers)
    after_cancel = next(p for p in listed.json() if p["id"] == product_id)
    assert after_cancel["stock_qty"] == 10, "bekor qilingandan keyin qoldiq qaytmadi"


@skip_no_db
async def test_cancelled_order_leaves_the_bill(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Audit topilmasi (2026-08-16): bekor qilingan buyurtma summasi hisobda
    qolib ketardi va mijozdan bekor qilingan mahsulot uchun pul olinardi."""
    headers = await _staff_headers(client, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Snack", "name": "Hisob Snack", "price": 20000, "stock_qty": 5},
        headers=headers,
    )
    product_id = created.json()["id"]

    before = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/bill", headers=headers
    )
    assert before.status_code == 200, before.text
    base_orders = before.json()["orders_amount"]

    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={"booking_id": world["booking"], "items": [{"product_id": product_id, "qty": 2}]},
        headers=headers,
    )
    order_id = order.json()["id"]

    during = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/bill", headers=headers
    )
    assert during.json()["orders_amount"] == base_orders + 40000

    await client.post(f"/api/v1/clubs/{world['club']}/orders/{order_id}/cancel", headers=headers)

    after = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/bill", headers=headers
    )
    assert after.json()["orders_amount"] == base_orders, (
        "bekor qilingan buyurtma hisobda qolib ketdi — mijozdan ortiqcha pul olinadi"
    )

    # Hisob tafsilotida ham ko'rinmasligi kerak
    detail = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/detail", headers=headers
    )
    assert detail.status_code == 200, detail.text
    assert not any(item["product_name"] == "Hisob Snack" for item in detail.json()["items"])


@skip_no_db
async def test_cancelled_order_is_not_counted_as_revenue(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Bekor qilingan buyurtma klub adminining tushum hisobotiga tushmasin."""
    headers = await _staff_headers(client, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Snack", "name": "Tushum Snack", "price": 30000, "stock_qty": 5},
        headers=headers,
    )
    product_id = created.json()["id"]

    before = await client.get(f"/api/v1/clubs/{world['club']}/dashboard", headers=headers)
    assert before.status_code == 200, before.text
    base_bar = before.json()["bar_revenue_today"]

    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={"booking_id": world["booking"], "items": [{"product_id": product_id, "qty": 1}]},
        headers=headers,
    )
    order_id = order.json()["id"]

    during = await client.get(f"/api/v1/clubs/{world['club']}/dashboard", headers=headers)
    assert during.json()["bar_revenue_today"] == base_bar + 30000

    await client.post(f"/api/v1/clubs/{world['club']}/orders/{order_id}/cancel", headers=headers)

    after = await client.get(f"/api/v1/clubs/{world['club']}/dashboard", headers=headers)
    assert after.json()["bar_revenue_today"] == base_bar, (
        "bekor qilingan buyurtma tushumda qolib ketdi"
    )


@skip_no_db
async def test_staff_role_can_create_and_cancel_order(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Loyiha egasining hisoboti (2026-08-17): "xodim yangi buyurtmani
    bekor qilganda xatolik yuz berdi".

    Oldingi testlar OWNER bilan yurgan — `products_write` policy'si esa
    STAFF'ni umuman o'z ichiga olmaydi, ya'ni kundalik ishni bajaradigan
    rol sinovdan CHETDA qolgan edi."""
    owner_h = await _staff_headers(client, world["club"])
    kassir_h = await _kassir_headers(client, world["club"])

    # Mahsulotni EGA qo'shadi (xodimda bunday huquq yo'q — bu to'g'ri)
    created = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Snack", "name": "Kassir Snack", "price": 15000, "stock_qty": 10},
        headers=owner_h,
    )
    assert created.status_code == 201, created.text
    product_id = created.json()["id"]

    # Buyurtmani XODIM kiritadi
    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={"booking_id": world["booking"], "items": [{"product_id": product_id, "qty": 2}]},
        headers=kassir_h,
    )
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]

    # Va XODIM uni bekor qiladi — aynan shu qadam xato berardi
    cancelled = await client.post(
        f"/api/v1/clubs/{world['club']}/orders/{order_id}/cancel", headers=kassir_h
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"

    # Qoldiq to'liq qaytishi kerak
    listed = await client.get(f"/api/v1/clubs/{world['club']}/products", headers=owner_h)
    row = next(p for p in listed.json() if p["id"] == product_id)
    assert row["stock_qty"] == 10, f"xodim bekor qilgach qoldiq qaytmadi: {row['stock_qty']}"


@skip_no_db
async def test_cancel_is_rejected_once_order_left_new(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """"Faqat yangi bo'lgan qiymatida mumkin" — `ACCEPTED` bo'lgach yo'q."""
    headers = await _staff_headers(client, world["club"])

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/products",
        json={"category": "Snack", "name": "Kech Snack", "price": 8000, "stock_qty": 5},
        headers=headers,
    )
    product_id = created.json()["id"]

    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={"booking_id": world["booking"], "items": [{"product_id": product_id, "qty": 1}]},
        headers=headers,
    )
    order_id = order.json()["id"]

    await client.post(f"/api/v1/clubs/{world['club']}/orders/{order_id}/advance", headers=headers)

    rejected = await client.post(
        f"/api/v1/clubs/{world['club']}/orders/{order_id}/cancel", headers=headers
    )
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["error"]["code"] == "ORDER_NOT_CANCELLABLE"


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

    # Naqd to'lov ochiq smenani TALAB QILADI (`0032_payments.py`) — aks
    # holda pul hech qaysi kassaga tushmasdi.
    shift = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts",
        json={"opening_cash": 0},
        headers=headers,
    )
    assert shift.status_code in (200, 201), shift.text

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


# ── To'lov cheki — o'tkazma + botga ulangan mijoz (reja #37) ───────────────


@pytest_asyncio.fixture
async def customer_booking(world: dict[str, int]) -> AsyncIterator[int]:
    """`world["booking"]` guest (customer_id YO'Q) — chek oqimi FAQAT
    botga ulangan (MINIAPP) mijoz uchun ishlaydi, shuning uchun alohida."""
    engine = _owner_engine()
    booking_id: int | None = None
    customer_id: int | None = None

    async with engine.begin() as conn:
        async with rls_bypass(conn, "users", "bookings"):
            customer_id = await conn.scalar(
                text(
                    "INSERT INTO users (kind, telegram_id, status, first_name)"
                    " VALUES ('customer', 900000301, 'active', 'Chek Sinov') RETURNING id"
                )
            )
            # `world["booking"]` bilan bir xil stansiyada, lekin UZOQ
            # kelajakda — `bookings_no_overlap` EXCLUDE bilan to'qnashmasin.
            starts = datetime.now(UTC) + timedelta(hours=5)
            ends = starts + timedelta(hours=1)
            booking_id = await conn.scalar(
                text(
                    "INSERT INTO bookings (club_id, station_id, customer_id, source, status,"
                    " period, hours, rate_snapshot, console_type)"
                    " VALUES (:c, :s, :u, 'MINIAPP', 'CONFIRMED',"
                    " tstzrange(:starts, :ends), 1, 40000, 'ps5') RETURNING id"
                ),
                {
                    "c": world["club"],
                    "s": world["station"],
                    "u": customer_id,
                    "starts": starts,
                    "ends": ends,
                },
            )

    yield int(booking_id)

    async with engine.begin() as conn:
        async with rls_bypass(conn, "users", "bookings"):
            await conn.execute(text("DELETE FROM bookings WHERE id = :i"), {"i": booking_id})
            await conn.execute(text("DELETE FROM users WHERE id = :i"), {"i": customer_id})
    await engine.dispose()


@skip_no_db
async def test_transfer_close_requests_proof_then_confirms(
    client: httpx.AsyncClient, world: dict[str, int], customer_booking: int
) -> None:
    headers = await _staff_headers(client, world["club"])

    # 1-chaqiruv — hisob YOPILMAYDI, chek so'raladi
    first = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{customer_booking}/close",
        json={"payment_method": "TRANSFER", "paid_amount": 40000},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["awaiting_proof"] is True
    assert body["payment_proof_status"] == "PENDING"

    # Hali ochiq — ikkinchi urinish ham "awaiting" qaytaradi (spam yubormaydi)
    again_pending = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{customer_booking}/close",
        json={"payment_method": "TRANSFER", "paid_amount": 40000},
        headers=headers,
    )
    assert again_pending.status_code == 200
    assert again_pending.json()["awaiting_proof"] is True

    # Mijoz botga rasm yuboradi — SQL funksiyasi orqali simulyatsiya
    engine = _owner_engine()
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text("SELECT * FROM bot_submit_payment_proof(900000301, 'sinov-file-id')")
            )
        ).first()
        assert row is not None
        assert row.booking_id == customer_booking
    await engine.dispose()

    # Endi xodim "Yopish" bossa — bu TASDIQLASH, hisob yopiladi
    confirmed = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{customer_booking}/close",
        json={"payment_method": "TRANSFER", "paid_amount": 40000},
        headers=headers,
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["awaiting_proof"] is False
    assert confirmed.json()["payment_proof_status"] == "CONFIRMED"

    proof = await client.get(
        f"/api/v1/clubs/{world['club']}/bookings/{customer_booking}/payment-proof",
        headers=headers,
    )
    # Haqiqiy Telegram file_id emas (sinov qiymati) — tarmoq/token yo'q
    # muhitda 404 kutiladi, lekin endpointning o'zi mavjud va ishlaydi
    assert proof.status_code in (200, 404)


@skip_no_db
async def test_transfer_close_on_guest_booking_closes_immediately(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """`customer_id` yo'q (guest/staff bron) — botga murojaat qilib
    bo'lmaydi, TRANSFER ham DARHOL yopiladi (eski xatti-harakat)."""
    headers = await _staff_headers(client, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        # `world` broni 2 soat x 40000 = 80000. Ilgari bu yerda 40000
        # yozilgan va JIMGINA qabul qilinardi — yetishmagan 40000 izsiz
        # yo'qolardi (`docs/audit-report.md` §2.2).
        json={"payment_method": "TRANSFER", "paid_amount": 80000},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["awaiting_proof"] is False
    assert r.json()["payment_proof_status"] is None
    assert r.json()["discount_amount"] == 0
    assert r.json()["debt_amount"] == 0


@skip_no_db
async def test_payment_proof_bot_ignores_unknown_and_no_pending(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    engine = _owner_engine()
    async with engine.begin() as conn:
        unknown = (
            await conn.execute(
                text("SELECT * FROM bot_submit_payment_proof(999999999, 'x')")
            )
        ).first()
        assert unknown is None
    await engine.dispose()
