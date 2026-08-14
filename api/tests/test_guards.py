"""Ikki dunyo chegarasi API qatlamida.

Manba: `docs/05-auth-redesign.md` §6.6, `docs/06-super-admin.md` §0.1 (P0-2).
"""


import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from playbron.core import context, errors
from playbron.core.security import AUDIENCE_CUSTOMER, AUDIENCE_STAFF, encode_access
from playbron.deps import require_admin, require_staff_token, require_super_admin

pytestmark = pytest.mark.asyncio


def _token(*, audience: str, super_admin: bool = False, club_id: int | None = None) -> str:
    memberships = (
        [{"club_id": club_id, "role": "STAFF", "org_id": 1}] if club_id is not None else []
    )
    token, _ = encode_access(
        user_id=1,
        memberships=memberships,
        is_super_admin=super_admin,
        audience=audience,
    )
    return token


def _probe_app() -> FastAPI:
    """Guard'larni alohida sinash uchun minimal ilova."""
    probe = FastAPI()
    # Xato ishlovchilari — haqiqiy ilovadagidek, aks holda `Forbidden` 500 ga aylanadi
    errors.install(probe)

    @probe.get("/staff-only", dependencies=[Depends(require_staff_token)])
    async def staff_only() -> dict[str, bool]:
        return {"ok": True}

    @probe.get("/admin-only", dependencies=[Depends(require_admin)])
    async def admin_only() -> dict[str, bool]:
        return {"ok": True}

    @probe.get("/platform", dependencies=[Depends(require_super_admin)])
    async def platform() -> dict[str, bool]:
        return {"ok": True}

    return probe


async def _call(path: str, token: str, headers: dict[str, str] | None = None) -> int:
    context.set_context(context.RequestContext(request_id="test"))
    transport = ASGITransport(app=_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            path, headers={"Authorization": f"Bearer {token}", **(headers or {})}
        )
    return response.status_code


async def test_customer_token_cannot_reach_staff_routes() -> None:
    assert await _call("/staff-only", _token(audience=AUDIENCE_CUSTOMER)) == 403
    assert await _call("/staff-only", _token(audience=AUDIENCE_STAFF)) == 200


async def test_customer_token_cannot_reach_platform() -> None:
    """Mijoz tokeni `sa` da'vosi bilan kelsa ham o'tmasligi kerak.

    Token imzolangani uchun bunday da'vo faqat server xatosi bilan paydo
    bo'lishi mumkin — lekin himoya aynan shu holat uchun.
    """
    token = _token(audience=AUDIENCE_CUSTOMER, super_admin=True)
    assert await _call("/platform", token) == 403


async def test_super_admin_no_longer_bypasses_club_role() -> None:
    """P0-2: ilgari `if ctx.is_super_admin: return` har qanday rol tekshiruvini
    auditsiz chetlab o'tardi. Endi super admin ham klub a'zoligiga muhtoj."""
    token = _token(audience=AUDIENCE_STAFF, super_admin=True)
    # Klub tanlanmagan — hech qanday istisno yo'q
    assert await _call("/admin-only", token) == 403


async def test_staff_without_required_role_is_rejected() -> None:
    token = _token(audience=AUDIENCE_STAFF, club_id=7)
    assert await _call("/admin-only", token, {"X-Club-Id": "7"}) == 403


async def test_customer_token_cannot_select_a_club() -> None:
    """`X-Club-Id` — xodim dunyosining sarlavhasi."""
    token = _token(audience=AUDIENCE_CUSTOMER)
    assert await _call("/staff-only", token, {"X-Club-Id": "7"}) == 403
