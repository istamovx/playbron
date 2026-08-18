"""Pul konturi — `payments`, smena kassasi, chegirma/qarz.

Manba: `api/migrations/versions/0032_payments.py`, `docs/audit-report.md` §2.3.

Bu fayl aynan auditda topilgan uchta teshikni qoplaydi (ular uchun ilgari
BIRORTA test yo'q edi):

  1. bronsiz sotuv kassaga tushmasdi;
  2. naqd xarajat kassadan yechilmasdi;
  3. `paid_amount` hisoblangan summaga umuman tekshirilmasdi.
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

OWNER_LOGIN = "money.owner"
STAFF_LOGIN = "money.kassir"
PASSWORD = "juda mustahkam parol"

RATE = 40_000
BOOKING_HOURS = 2
PLAY_TOTAL = RATE * BOOKING_HOURS  # 80 000


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
                    " VALUES (:u, 'Money Org', 'active', 'gold') RETURNING id"
                ),
                {"u": ids["owner"]},
            )
            ids["club"] = await conn.scalar(
                text(
                    "INSERT INTO clubs (org_id, name, status, opens_at_min, closes_at_min)"
                    " VALUES (:o, 'Money Club', 'active', 0, 1440) RETURNING id"
                ),
                {"o": ids["org"]},
            )
            await conn.execute(
                text("INSERT INTO memberships (user_id, club_id, role) VALUES (:u, :c, 'OWNER')"),
                {"u": ids["owner"], "c": ids["club"]},
            )
            # OWNER emas, HAQIQIY `STAFF` — RLS policy'lari ikkalasi uchun
            # bir xil EMAS va aynan shu farq kassa hisobini buzgan edi.
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
                    " VALUES (:c, 'MNY-1', 'Standart', 'ps5', :rate) RETURNING id"
                ),
                {"c": ids["club"], "rate": RATE},
            )
            starts = datetime.now(UTC) - timedelta(minutes=10)
            ids["booking"] = await conn.scalar(
                text(
                    "INSERT INTO bookings (club_id, station_id, guest_name, guest_phone,"
                    " source, status, period, hours, rate_snapshot, console_type, created_by,"
                    " confirmed_by, confirmed_at)"
                    " VALUES (:c, :s, 'Mehmon', '+998900000000', 'STAFF', 'CONFIRMED',"
                    " tstzrange(:starts, :ends), :hours, :rate, 'ps5', :u, :u, now())"
                    " RETURNING id"
                ),
                {
                    "c": ids["club"],
                    "s": ids["station"],
                    "starts": starts,
                    "ends": starts + timedelta(hours=BOOKING_HOURS),
                    "hours": BOOKING_HOURS,
                    "rate": RATE,
                    "u": ids["owner"],
                },
            )

    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(
            conn,
            "organizations",
            "users",
            "bookings",
            "stations",
            "products",
            "orders",
            "payments",
            "expenses",
            "shifts",
        ):
            await purge_audit_actor(conn, ids["owner"], ids.get("staff"))
            # Tartib muhim: `payments` `orders`/`bookings`/`shifts`ga
            # havola qiladi. Jadval nomlari SHU YERDAGI qat'iy ro'yxatdan,
            # tashqi kirishdan emas.
            for table in ("payments", "expenses", "orders", "products", "bookings", "shifts"):
                await conn.execute(
                    text(f"DELETE FROM {table} WHERE club_id = :c"),  # noqa: S608
                    {"c": ids["club"]},
                )
            await conn.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": ids["org"]})
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


async def _headers(
    client: httpx.AsyncClient, club_id: int, login: str = OWNER_LOGIN
) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": login, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}", "X-Club-Id": str(club_id)}


async def _open_shift(
    client: httpx.AsyncClient, headers: dict[str, str], club_id: int, opening_cash: int = 0
) -> dict:
    r = await client.post(
        f"/api/v1/clubs/{club_id}/shifts", json={"opening_cash": opening_cash}, headers=headers
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _current_shift(
    client: httpx.AsyncClient, headers: dict[str, str], club_id: int
) -> dict:
    r = await client.get(f"/api/v1/clubs/{club_id}/shifts/current", headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


async def _product(
    client: httpx.AsyncClient, headers: dict[str, str], club_id: int, price: int
) -> int:
    r = await client.post(
        f"/api/v1/clubs/{club_id}/products",
        json={"category": "Ichimlik", "name": f"Money Kola {price}", "price": price},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


# ── Ochiq smena majburiyligi ──────────────────────────────────────────────


@skip_no_db
async def test_cash_close_without_shift_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Smenasiz yopilgan naqd hisob hech qaysi kassaga tushmasdi."""
    headers = await _headers(client, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={"payment_method": "CASH", "paid_amount": PLAY_TOTAL},
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "SHIFT_REQUIRED"


# ── Bronsiz sotuv ─────────────────────────────────────────────────────────


@skip_no_db
async def test_walkin_order_lands_in_shift_cash(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Bronsiz sotuv ilgari hisobotda ko'rinardi, kassada esa YO'Q edi."""
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"], opening_cash=50_000)
    product_id = await _product(client, headers, world["club"], 15_000)

    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={
            "booking_id": None,
            "payment_method": "CASH",
            "items": [{"product_id": product_id, "qty": 2}],
        },
        headers=headers,
    )
    assert order.status_code == 201, order.text
    assert order.json()["total"] == 30_000

    shift = await _current_shift(client, headers, world["club"])
    assert shift["expected_cash"] == 50_000 + 30_000


@skip_no_db
async def test_walkin_order_requires_payment_method(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"])
    product_id = await _product(client, headers, world["club"], 15_000)

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={"booking_id": None, "items": [{"product_id": product_id, "qty": 1}]},
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "PAYMENT_METHOD_REQUIRED"


@skip_no_db
async def test_booking_order_must_not_carry_payment_method(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Bronga biriktirilgan buyurtma hisob yopilganda to'lanadi — ikki
    marta to'lanmasligi uchun bu yerda to'lov turi qabul qilinmaydi."""
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"])
    product_id = await _product(client, headers, world["club"], 15_000)

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={
            "booking_id": world["booking"],
            "payment_method": "CASH",
            "items": [{"product_id": product_id, "qty": 1}],
        },
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "PAYMENT_METHOD_NOT_ALLOWED"


# ── Chegirma va qarz ──────────────────────────────────────────────────────


@skip_no_db
async def test_shortfall_without_reason_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Ilgari yetishmagan summa JIMGINA qabul qilinardi va izsiz yo'qolardi."""
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={"payment_method": "CASH", "paid_amount": PLAY_TOTAL - 20_000},
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "SHORTFALL_REASON_REQUIRED"


@skip_no_db
async def test_discount_is_recorded_and_only_paid_cash_counted(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"], opening_cash=10_000)

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={
            "payment_method": "CASH",
            "paid_amount": PLAY_TOTAL - 20_000,
            "shortfall_reason": "DISCOUNT",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == PLAY_TOTAL
    assert body["discount_amount"] == 20_000
    assert body["debt_amount"] == 0

    # Kassaga FAQAT haqiqatan olingan pul tushadi
    shift = await _current_shift(client, headers, world["club"])
    assert shift["expected_cash"] == 10_000 + (PLAY_TOTAL - 20_000)


@skip_no_db
async def test_debt_is_recorded_separately_from_discount(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={
            "payment_method": "CASH",
            "paid_amount": PLAY_TOTAL - 30_000,
            "shortfall_reason": "DEBT",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["debt_amount"] == 30_000
    assert r.json()["discount_amount"] == 0


@skip_no_db
async def test_overpayment_without_reason_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Sababsiz ortiqcha summa terish xatosi bo'lishi mumkin."""
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={"payment_method": "CASH", "paid_amount": PLAY_TOTAL + 5_000},
        headers=headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "OVERPAY_REASON_REQUIRED"


@skip_no_db
async def test_tip_is_recorded_and_stays_in_the_till(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Qaytim olinmagan qism kassada QOLADI.

    Rad etilsa xodim kassadagi haqiqiy puldan kam ko'rsatishga majbur
    bo'lardi va smena aynan o'sha farqqa "ortiq" chiqardi.
    """
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"], opening_cash=10_000)

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={
            "payment_method": "CASH",
            "paid_amount": PLAY_TOTAL + 5_000,
            "overpay_reason": "TIP",
        },
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["tip_amount"] == 5_000
    assert r.json()["discount_amount"] == 0

    shift = await _current_shift(client, headers, world["club"])
    assert shift["expected_cash"] == 10_000 + PLAY_TOTAL + 5_000


# ── Naqd xarajat ──────────────────────────────────────────────────────────


@skip_no_db
async def test_cash_expense_reduces_expected_cash(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Ilgari naqd xarajat kassani kamaytirmasdi — farq har safar manfiy
    chiqardi yoki xodim uni qo'lda ikkinchi marta yozardi."""
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"], opening_cash=100_000)

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/expenses",
        json={
            "spent_on": datetime.now(UTC).date().isoformat(),
            "category": "Suv",
            "amount": 25_000,
            "method": "CASH",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["method"] == "CASH"

    shift = await _current_shift(client, headers, world["club"])
    assert shift["expected_cash"] == 100_000 - 25_000


@skip_no_db
async def test_transfer_expense_does_not_touch_cash(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"], opening_cash=100_000)

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/expenses",
        json={
            "spent_on": datetime.now(UTC).date().isoformat(),
            "category": "Internet",
            "amount": 25_000,
            "method": "TRANSFER",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text

    shift = await _current_shift(client, headers, world["club"])
    assert shift["expected_cash"] == 100_000


@skip_no_db
async def test_cash_expense_without_shift_is_rejected(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    headers = await _headers(client, world["club"])

    r = await client.post(
        f"/api/v1/clubs/{world['club']}/expenses",
        json={
            "spent_on": datetime.now(UTC).date().isoformat(),
            "category": "Suv",
            "amount": 25_000,
            "method": "CASH",
        },
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "SHIFT_REQUIRED"


# ── Hisobot: reja va olingan pul ──────────────────────────────────────────


@skip_no_db
async def test_dashboard_separates_planned_from_received(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Reja va kassa bir xil son EMAS — hisobot ikkalasini alohida beradi.

    Bron bugunga rejalashtirilgan (`planned`), lekin chegirma bilan
    yopilgan — demak `received` undan kam bo'lishi shart.
    """
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"])

    closed = await client.post(
        f"/api/v1/clubs/{world['club']}/bookings/{world['booking']}/close",
        json={
            "payment_method": "CASH",
            "paid_amount": PLAY_TOTAL - 20_000,
            "shortfall_reason": "DISCOUNT",
        },
        headers=headers,
    )
    assert closed.status_code == 200, closed.text

    dash = await client.get(f"/api/v1/clubs/{world['club']}/dashboard", headers=headers)
    assert dash.status_code == 200, dash.text
    body = dash.json()

    assert body["planned_revenue_today"] == PLAY_TOTAL
    assert body["received_revenue_today"] == PLAY_TOTAL - 20_000
    assert body["received_revenue_today"] < body["planned_revenue_today"]


# ── Review topilmalari uchun regressiya testlari ──────────────────────────


@skip_no_db
async def test_staff_and_owner_see_the_same_expected_cash(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """`expenses` uchun yagona policy OWNER/ADMIN edi.

    Xodim o'z smenasidagi naqd xarajatni KO'RMASDI va `_expected_cash()`
    unga jimgina 0 qaytarardi — smena yopilganda u aynan xarajat
    summasiga "kam" bo'lib chiqardi.
    """
    staff_h = await _headers(client, world["club"], STAFF_LOGIN)
    owner_h = await _headers(client, world["club"])

    shift = await _open_shift(client, staff_h, world["club"], opening_cash=100_000)

    # Xarajatni EGA yozadi (endpoint `require_admin`), lekin pul XODIM
    # kassasidan chiqadi — shuning uchun smena aniq ko'rsatiladi.
    r = await client.post(
        f"/api/v1/clubs/{world['club']}/expenses",
        json={
            "spent_on": datetime.now(UTC).date().isoformat(),
            "category": "Suv",
            "amount": 25_000,
            "method": "CASH",
            "shift_id": shift["id"],
        },
        headers=owner_h,
    )
    assert r.status_code == 201, r.text

    staff_view = await _current_shift(client, staff_h, world["club"])
    assert staff_view["expected_cash"] == 75_000, (
        "xodim o'z smenasidagi naqd xarajatni ko'rmayapti — "
        "smena yopilganda u aybdor bo'lib chiqadi"
    )


@skip_no_db
async def test_cancelled_walkin_order_returns_the_cash(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Bekor qilingan bronsiz sotuvning puli kassada qolib ketardi."""
    headers = await _headers(client, world["club"])
    await _open_shift(client, headers, world["club"], opening_cash=10_000)
    product_id = await _product(client, headers, world["club"], 15_000)

    order = await client.post(
        f"/api/v1/clubs/{world['club']}/orders",
        json={
            "booking_id": None,
            "payment_method": "CASH",
            "items": [{"product_id": product_id, "qty": 2}],
        },
        headers=headers,
    )
    assert order.status_code == 201, order.text
    assert (await _current_shift(client, headers, world["club"]))["expected_cash"] == 40_000

    cancelled = await client.post(
        f"/api/v1/clubs/{world['club']}/orders/{order.json()['id']}/cancel", headers=headers
    )
    assert cancelled.status_code == 200, cancelled.text

    after = await _current_shift(client, headers, world["club"])
    assert after["expected_cash"] == 10_000, "bekor qilingan sotuv puli kassada qoldi"


@skip_no_db
async def test_expense_on_closed_shift_cannot_be_edited(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """`_expected_cash()` har o'qishda qayta hisoblaydi.

    Yopilgan smenaga tegishli xarajat tahriri uning farqini RETROAKTIV
    o'zgartirardi va audit jurnalidagi yozuv bilan ziddiyatga tushardi.
    """
    headers = await _headers(client, world["club"])
    shift = await _open_shift(client, headers, world["club"], opening_cash=100_000)

    created = await client.post(
        f"/api/v1/clubs/{world['club']}/expenses",
        json={
            "spent_on": datetime.now(UTC).date().isoformat(),
            "category": "Suv",
            "amount": 25_000,
            "method": "CASH",
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    expense_id = created.json()["id"]

    closed = await client.post(
        f"/api/v1/clubs/{world['club']}/shifts/{shift['id']}/close",
        json={"counted_cash": 75_000},
        headers=headers,
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["variance"] == 0

    r = await client.patch(
        f"/api/v1/clubs/{world['club']}/expenses/{expense_id}",
        json={
            "spent_on": datetime.now(UTC).date().isoformat(),
            "category": "Suv",
            "amount": 25_000,
            "status": "archived",
        },
        headers=headers,
    )
    assert r.status_code == 409, r.text
    assert r.json()["error"]["code"] == "SHIFT_CLOSED"
