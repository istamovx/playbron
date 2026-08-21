"""Platforma paneli — super admin cross-tenant statistikasi.

Manba: `api/migrations/versions/0015_platform_stats.py`, loyiha egasining
so'rovi (2026-08-16): "Super admin roli uchun infografikalar".
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

SA_LOGIN = "plt.superadmin"
OWNER_A_LOGIN = "plt.owner.a"
OWNER_B_LOGIN = "plt.owner.b"
PASSWORD = "juda mustahkam parol platforma"


def _owner_engine():  # type: ignore[no-untyped-def]
    return create_async_engine(settings.direct_url.replace("+psycopg", "+asyncpg"))


@pytest_asyncio.fixture(autouse=True)
async def clean_limits() -> AsyncIterator[None]:
    """Bir xil login'lar sinovlar orasida qayta ishlatiladi — chelak
    tozalanmasa keyingi sinov haqiqiy 200 emas 429 RATE_LIMITED olardi
    (`test_bookings.py::clean_limits` bilan bir xil naqsh)."""
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
    """Ikkita ALOHIDA tashkilot/klub/stansiya + har birida bittadan
    CONFIRMED bron (bugun) — cross-tenant agregatsiya shu ikkalasini
    ham qamrashi kerak. Bittasi ham tabiiy aktordan yaratilmagan."""
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
            "super_admins",
            "bookings",
        ):
            ids["sa_user"] = await conn.scalar(
                text(
                    "INSERT INTO users (kind, login, status, first_name)"
                    " VALUES ('staff', :login, 'active', 'SA')"
                    " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                    " DO UPDATE SET status = 'active' RETURNING id"
                ),
                {"login": SA_LOGIN},
            )
            await conn.execute(
                text(
                    "INSERT INTO super_admins (user_id, note) VALUES (:u, 'test')"
                    " ON CONFLICT (user_id) DO NOTHING"
                ),
                {"u": ids["sa_user"]},
            )
            await conn.execute(
                text(
                    "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                    " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                    " SET password_hash = EXCLUDED.password_hash, must_change = false"
                ),
                {"uid": ids["sa_user"], "h": password_hash},
            )

            for tag, login in (("a", OWNER_A_LOGIN), ("b", OWNER_B_LOGIN)):
                owner_id = await conn.scalar(
                    text(
                        "INSERT INTO users (kind, login, status, first_name)"
                        " VALUES ('staff', :login, 'active', 'Ega')"
                        " ON CONFLICT ((lower(login))) WHERE kind = 'staff'"
                        " DO UPDATE SET status = 'active' RETURNING id"
                    ),
                    {"login": login},
                )
                await conn.execute(
                    text(
                        "INSERT INTO staff_credentials (user_id, password_hash, must_change)"
                        " VALUES (:uid, :h, false) ON CONFLICT (user_id) DO UPDATE"
                        " SET password_hash = EXCLUDED.password_hash, must_change = false"
                    ),
                    {"uid": owner_id, "h": password_hash},
                )
                org_id = await conn.scalar(
                    text(
                        "INSERT INTO organizations (owner_user_id, name, status)"
                        " VALUES (:u, :n, 'active') RETURNING id"
                    ),
                    {"u": owner_id, "n": f"Platform Org {tag.upper()}"},
                )
                club_id = await conn.scalar(
                    text(
                        "INSERT INTO clubs (org_id, name, status)"
                        " VALUES (:o, :n, 'active') RETURNING id"
                    ),
                    {"o": org_id, "n": f"Platform Club {tag.upper()}"},
                )
                await conn.execute(
                    text(
                        "INSERT INTO memberships (user_id, club_id, role)"
                        " VALUES (:u, :c, 'OWNER')"
                    ),
                    {"u": owner_id, "c": club_id},
                )
                station_id = await conn.scalar(
                    text(
                        "INSERT INTO stations (club_id, code, room_label, console_type, rate)"
                        " VALUES (:c, 'PLT-1', 'Standart', 'ps5', 30000) RETURNING id"
                    ),
                    {"c": club_id},
                )
                starts = datetime.now(UTC) - timedelta(minutes=10)
                await conn.execute(
                    text(
                        "INSERT INTO bookings"
                        " (club_id, station_id, guest_name, guest_phone, source, status,"
                        "  period, hours, rate_snapshot, play_amount, console_type)"
                        " VALUES (:c, :s, 'Sinov', '+998900000000', 'STAFF', 'CONFIRMED',"
                        "         tstzrange(CAST(:starts AS timestamptz),"
                        "                   CAST(:starts AS timestamptz) + interval '1 hour'),"
                        "         1, 30000, 30000, 'ps5')"
                    ),
                    {"c": club_id, "s": station_id, "starts": starts},
                )
                ids[f"owner_{tag}"] = owner_id
                ids[f"org_{tag}"] = org_id
                ids[f"club_{tag}"] = club_id

    await core_db.dispose()

    yield ids

    async with engine.begin() as conn:
        async with rls_bypass(conn, "organizations", "users", "super_admins", "bookings"):
            await purge_audit_actor(
                conn, ids["sa_user"], ids["owner_a"], ids["owner_b"]
            )
            await conn.execute(text("DELETE FROM bookings WHERE club_id = :a OR club_id = :b"),
                                {"a": ids["club_a"], "b": ids["club_b"]})
            await conn.execute(text("DELETE FROM organizations WHERE id = :a OR id = :b"),
                                {"a": ids["org_a"], "b": ids["org_b"]})
            await conn.execute(text("DELETE FROM super_admins WHERE user_id = :u"),
                                {"u": ids["sa_user"]})
            await conn.execute(
                text(
                    "DELETE FROM users WHERE login IN (:sa, :a, :b) AND kind = 'staff'"
                ),
                {"sa": SA_LOGIN, "a": OWNER_A_LOGIN, "b": OWNER_B_LOGIN},
            )
    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _login(client: httpx.AsyncClient, login: str) -> dict[str, str]:
    r = await client.post(
        "/api/v1/auth/staff/login", json={"login": login, "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@skip_no_db
async def test_regular_owner_gets_404(client: httpx.AsyncClient, world: dict[str, int]) -> None:
    """`require_super_admin` — panel borligi bilinmasin (403 emas, 404)."""
    owner_h = await _login(client, OWNER_A_LOGIN)
    r = await client.get("/api/v1/platform/stats", headers=owner_h)
    assert r.status_code == 404, r.text


@skip_no_db
async def test_super_admin_sees_cross_tenant_stats(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    sa_h = await _login(client, SA_LOGIN)
    r = await client.get("/api/v1/platform/stats", headers=sa_h)
    assert r.status_code == 200, r.text
    body = r.json()

    # `>=` — real (lokal) bazada boshqa klublar/bronlar ham bo'lishi mumkin;
    # bu yerda faqat "ikkalasi ham qo'shildi" tekshiriladi, aniq son emas
    # (`top_clubs` esa boshqa haqiqiy klublar ko'proq bron qilgan bo'lsa
    # bizning ikkitamizni siqib chiqarishi mumkin — shu sabab nomiga
    # tayanilmaydi, faqat shaklga).
    assert body["organizations_total"] >= 2
    assert body["clubs_active"] >= 2
    assert body["bookings_today"] >= 2
    assert body["revenue_today"] >= 60000
    assert isinstance(body["top_clubs"], list)
    for row in body["top_clubs"]:
        assert {"club_id", "club_name", "org_name", "bookings"} <= row.keys()


@skip_no_db
async def test_super_admin_lists_organizations(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    sa_h = await _login(client, SA_LOGIN)
    r = await client.get("/api/v1/platform/orgs", headers=sa_h)
    assert r.status_code == 200, r.text
    rows = r.json()
    org_ids = {row["org_id"] for row in rows}
    assert world["org_a"] in org_ids
    assert world["org_b"] in org_ids
    row_a = next(row for row in rows if row["org_id"] == world["org_a"])
    assert row_a["club_id"] == world["club_a"]
    assert row_a["owner_login"] == OWNER_A_LOGIN
    assert row_a["stations_count"] >= 1
    # Klub tushumi — loyiha egasining so'rovi (2026-08-20): super admin
    # bron tafsilotini emas, faqat SUMMANI ko'radi. `world` klub_a uchun
    # 30 000 so'mlik bitta CONFIRMED bron yaratadi, 7/30/365 kunlik
    # oynaning hammasi shu bronni qamraydi.
    assert row_a["revenue_7d"] >= 30_000
    assert row_a["revenue_30d"] >= 30_000
    assert row_a["revenue_365d"] >= 30_000


@skip_no_db
async def test_super_admin_opens_org_detail(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """`GET /platform/orgs/{id}` — preview modalning manbasi.

    Audit topilmasi (2026-08-16): bu endpoint UMUMAN sinovdan o'tmagan
    edi va shu sababli `memberships`/`stations` uchun `app_platform()`
    policy'lari yo'qligi (prod'da "Xodimlar (0)" va "Stansiya 0")
    e'tibordan chetda qolgan. `0029_platform_read_gaps.py` tuzatdi.
    """
    sa_h = await _login(client, SA_LOGIN)
    r = await client.get(f"/api/v1/platform/orgs/{world['org_a']}", headers=sa_h)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["org_id"] == world["org_a"]
    assert body["owner_login"] == OWNER_A_LOGIN

    clubs = body["clubs"]
    assert any(c["club_id"] == world["club_a"] for c in clubs)
    club_a = next(c for c in clubs if c["club_id"] == world["club_a"])
    assert club_a["stations_count"] >= 1, "stations platform policy'si yo'q — Stansiya 0 bo'ldi"
    assert club_a["revenue_30d"] >= 30_000

    assert any(s["login"] == OWNER_A_LOGIN for s in body["staff"]), (
        "memberships platform policy'si yo'q — Xodimlar ro'yxati bo'sh"
    )


@skip_no_db
async def test_suspending_org_revokes_open_sessions(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Audit topilmasi (2026-08-16): `0026` faqat YANGI kirishni bloklardi,
    allaqachon kirgan xodim refresh rotatsiyasi bilan ishlayverardi."""
    owner_h = await _login(client, OWNER_A_LOGIN)
    # Sessiya tirikligini tasdiqlaymiz
    alive = await client.get("/api/v1/me", headers=owner_h)
    assert alive.status_code == 200, alive.text

    sa_h = await _login(client, SA_LOGIN)
    suspended = await client.patch(
        f"/api/v1/platform/orgs/{world['org_a']}",
        json={"status": "suspended"},
        headers=sa_h,
    )
    assert suspended.status_code == 200, suspended.text
    assert suspended.json()["revoked_sessions"] >= 1, "ochiq sessiya yopilmadi"

    # Boshqa tashkilotning egasi TEGILMAGAN bo'lishi kerak
    other_h = await _login(client, OWNER_B_LOGIN)
    other_alive = await client.get("/api/v1/me", headers=other_h)
    assert other_alive.status_code == 200, other_alive.text

    # Tozalash: fixture teardown'i kutgan holatga qaytaramiz
    await client.patch(
        f"/api/v1/platform/orgs/{world['org_a']}", json={"status": "active"}, headers=sa_h
    )


@skip_no_db
async def test_regular_owner_cannot_open_org_detail(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    owner_h = await _login(client, OWNER_A_LOGIN)
    r = await client.get(f"/api/v1/platform/orgs/{world['org_a']}", headers=owner_h)
    assert r.status_code == 404, r.text


@skip_no_db
async def test_regular_owner_cannot_list_organizations(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    owner_h = await _login(client, OWNER_A_LOGIN)
    r = await client.get("/api/v1/platform/orgs", headers=owner_h)
    assert r.status_code == 404, r.text


@skip_no_db
async def test_super_admin_creates_org_manually(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    sa_h = await _login(client, SA_LOGIN)
    login = "plt.manual.owner"

    try:
        r = await client.post(
            "/api/v1/platform/orgs",
            json={
                "first_name": "Qo'lda",
                "club_name": "Qo'lda Qo'shilgan Klub",
                "phone": "+998901234567",
                "address": "Toshkent, sinov",
                "login": login,
                "password": "juda mustahkam qolda parol",
            },
            headers=sa_h,
        )
        assert r.status_code == 201, r.text
        assert r.json()["login"] == login

        # Yaratilgan hisob darhol o'zi kira oladi (parolni SA tanladi/berdi,
        # lekin `must_change=false` — xuddi owner_signup'dagi kabi).
        login_r = await client.post(
            "/api/v1/auth/staff/login",
            json={"login": login, "password": "juda mustahkam qolda parol"},
        )
        assert login_r.status_code == 200, login_r.text
        assert login_r.json()["memberships"][0]["role"] == "OWNER"

        # Ikkinchi marta bir xil login — LOGIN_TAKEN, 409.
        dup = await client.post(
            "/api/v1/platform/orgs",
            json={
                "first_name": "Boshqa",
                "club_name": "Boshqa Klub",
                "phone": "+998901234568",
                "address": "Toshkent, sinov 2",
                "login": login,
                "password": "yana bitta mustahkam parol",
            },
            headers=sa_h,
        )
        assert dup.status_code == 409, dup.text
        assert dup.json()["error"]["code"] == "LOGIN_TAKEN"
    finally:
        engine = _owner_engine()
        async with engine.begin() as conn:
            async with rls_bypass(conn, "organizations", "users"):
                new_owner_id = await conn.scalar(
                    text("SELECT id FROM users WHERE login = :l"), {"l": login}
                )
                await purge_audit_actor(conn, new_owner_id)
                await conn.execute(
                    text(
                        "DELETE FROM organizations WHERE owner_user_id IN"
                        " (SELECT id FROM users WHERE login = :l)"
                    ),
                    {"l": login},
                )
                await conn.execute(text("DELETE FROM users WHERE login = :l"), {"l": login})
        await engine.dispose()


@skip_no_db
async def test_super_admin_records_payment_and_sees_it_in_report(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    sa_h = await _login(client, SA_LOGIN)

    r = await client.post(
        f"/api/v1/platform/orgs/{world['org_a']}/payments",
        json={"amount": 490000, "plan_code": "gold", "period_months": 1, "note": "sinov to'lovi"},
        headers=sa_h,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["org_id"] == world["org_a"]
    assert body["amount"] == 490000
    assert body["plan_code"] == "gold"

    bad = await client.post(
        f"/api/v1/platform/orgs/{world['org_a']}/payments",
        json={"amount": 0},
        headers=sa_h,
    )
    assert bad.status_code == 422, bad.text  # Field(gt=0) — Pydantic darajasida rad

    missing_org = await client.post(
        "/api/v1/platform/orgs/999999999/payments",
        json={"amount": 100000},
        headers=sa_h,
    )
    assert missing_org.status_code == 404, missing_org.text

    report = await client.get("/api/v1/platform/report", params={"period": "month"}, headers=sa_h)
    assert report.status_code == 200, report.text
    report_body = report.json()
    assert report_body["period"] == "month"
    assert report_body["total_revenue"] >= 490000
    assert sum(report_body["revenue_by_bucket"].values()) >= 490000


@skip_no_db
async def test_payment_updates_org_plan_and_expiry_in_list(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """To'lov qo'shilgandan keyin "Klublar" ro'yxatida TARIF va AMAL
    QILISH MUDDATI ko'rinishi kerak (`0017_platform_org_plan.py`)."""
    sa_h = await _login(client, SA_LOGIN)

    before = await client.get("/api/v1/platform/orgs", headers=sa_h)
    assert before.status_code == 200, before.text
    row_before = next(row for row in before.json() if row["org_id"] == world["org_a"])
    assert row_before["plan_code"] is None
    assert row_before["last_payment_amount"] is None
    assert row_before["plan_expires_at"] is None

    paid = await client.post(
        f"/api/v1/platform/orgs/{world['org_a']}/payments",
        json={"amount": 350000, "plan_code": "platinium", "period_months": 3},
        headers=sa_h,
    )
    assert paid.status_code == 201, paid.text
    paid_at = datetime.fromisoformat(paid.json()["paid_at"])

    after = await client.get("/api/v1/platform/orgs", headers=sa_h)
    assert after.status_code == 200, after.text
    row_after = next(row for row in after.json() if row["org_id"] == world["org_a"])
    assert row_after["plan_code"] == "platinium"
    assert row_after["last_payment_amount"] == 350000
    assert row_after["last_payment_at"] is not None
    assert row_after["plan_expires_at"] is not None

    expires_at = datetime.fromisoformat(row_after["plan_expires_at"])
    # Postgres `interval '1 month'` — kalendar oyi qo'shadi (kun/soat aynan
    # saqlanadi), `timedelta(days=...)` bilan emas — 3 oy qo'shib solishtiramiz.
    expected_month = paid_at.month - 1 + 3
    expected = paid_at.replace(
        year=paid_at.year + expected_month // 12, month=expected_month % 12 + 1
    )
    assert abs((expires_at - expected).total_seconds()) < 60


@skip_no_db
async def test_payment_without_plan_code_leaves_org_plan_untouched(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    """Tarifsiz (bir martalik) to'lov — `organizations.plan_code`ni
    o'zgartirmasligi kerak, faqat to'lov tarixiga qo'shiladi."""
    sa_h = await _login(client, SA_LOGIN)

    r = await client.post(
        f"/api/v1/platform/orgs/{world['org_b']}/payments",
        json={"amount": 120000, "note": "bir martalik"},
        headers=sa_h,
    )
    assert r.status_code == 201, r.text

    rows = await client.get("/api/v1/platform/orgs", headers=sa_h)
    row_b = next(row for row in rows.json() if row["org_id"] == world["org_b"])
    assert row_b["plan_code"] is None
    assert row_b["last_payment_amount"] == 120000
    assert row_b["plan_expires_at"] is None


@skip_no_db
async def test_report_rejects_unknown_period(
    client: httpx.AsyncClient, world: dict[str, int]
) -> None:
    sa_h = await _login(client, SA_LOGIN)
    r = await client.get("/api/v1/platform/report", params={"period": "decade"}, headers=sa_h)
    assert r.status_code == 422, r.text
