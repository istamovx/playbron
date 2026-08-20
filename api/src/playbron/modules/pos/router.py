"""POS marshrutlari — `/api/v1/clubs/{club_id}/...`. Faqat xodim (mijozga ochiq emas)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core import context, telegram_api
from playbron.core.config import settings
from playbron.core.errors import Forbidden, NotFound
from playbron.deps import db, require_admin, require_staff
from playbron.modules.pos import service

router = APIRouter(prefix="/clubs", tags=["pos"])


def _assert_path_matches_header(club_id: int) -> None:
    """`staff/router.py`dagi bilan bir xil naqsh — yo'l va sarlavha klubi mos kelsin."""
    active = context.current().club_id
    if active is None or int(active) != int(club_id):
        raise Forbidden("Faol klub mos kelmadi", code="CLUB_MISMATCH")


def _bot_token() -> str:
    return settings.bot_token.get_secret_value()


# ── Sxemalar ──────────────────────────────────────────────────────────────


class ProductOut(BaseModel):
    id: int
    category: str
    name: str
    price: int
    status: str
    stock_qty: int


class ProductCreateIn(BaseModel):
    category: str = Field(default="Boshqa", max_length=32)
    name: str = Field(min_length=1, max_length=120)
    price: int = Field(gt=0)
    # Loyiha egasi (2026-08-16): "biror mahsulot qo'shganda sonini ham
    # kiritishi kerak". 0 — hali keltirilmagan mahsulot uchun to'g'ri.
    stock_qty: int = Field(default=0, ge=0)


class ProductUpdateIn(BaseModel):
    category: str = Field(default="Boshqa", max_length=32)
    name: str = Field(min_length=1, max_length=120)
    price: int = Field(gt=0)
    status: str = Field(pattern="^(active|archived)$")
    # `None` — qoldiqqa TEGILMAYDI (eski klientlar buzilmasin).
    stock_qty: int | None = Field(default=None, ge=0)


class OrderItemOut(BaseModel):
    product_name: str
    qty: int
    price_snapshot: int


class OrderOut(BaseModel):
    id: int
    booking_id: int | None
    station_code: str | None
    status: str
    total: int
    created_at: str
    items: list[OrderItemOut]


class OrderItemIn(BaseModel):
    product_id: int
    qty: int = Field(gt=0, le=50)


class OrderCreateIn(BaseModel):
    booking_id: int | None = None
    items: list[OrderItemIn] = Field(min_length=1, max_length=30)
    # Faqat bronsiz sotuv uchun — pul darhol olinadi. Bronga biriktirilgan
    # buyurtma hisob yopilganda to'lanadi.
    payment_method: str | None = Field(default=None, pattern="^(CASH|TRANSFER)$")


class OpenBookingOut(BaseModel):
    id: int
    station_code: str
    hours: int
    rate_snapshot: int
    starts_at: str
    ends_at: str
    guest_label: str | None


class BillOut(BaseModel):
    booking_id: int
    play_amount: int
    orders_amount: int
    total: int
    # Reja #37 (2026-08-16) — o'tkazma + botga ulangan mijoz: chek talab
    # qilinadi. `True` bo'lsa hisob HALI YOPILMAGAN, kassa `Kutilmoqda`
    # holatini ko'rsatsin.
    awaiting_proof: bool = False
    payment_proof_status: str | None = None
    # Hisoblangan summa bilan olingan summa farqi — sababi bo'yicha
    # ajratilgan. `get_bill()` (hali yopilmagan hisob) uchun ikkalasi 0.
    discount_amount: int = 0
    debt_amount: int = 0
    tip_amount: int = 0


class CloseBillIn(BaseModel):
    payment_method: str = Field(pattern="^(CASH|TRANSFER)$")
    paid_amount: int = Field(ge=0)
    # `paid_amount` hisoblangan summadan KAM bo'lsa majburiy: farq
    # chegirma sifatidami (daromaddan chiqadi) yoki qarz sifatidami
    # (mijoz zimmasida qoladi) — xodim tanlaydi.
    shortfall_reason: str | None = Field(default=None, pattern="^(DISCOUNT|DEBT)$")
    # `paid_amount` hisobdan KO'P bo'lsa majburiy — qaytim olinmagan qism.
    overpay_reason: str | None = Field(default=None, pattern="^(TIP)$")


class LiveStationOut(BaseModel):
    id: int
    code: str
    room_label: str
    # Band bo'lsa bronning konsoli, bo'sh yangi (konsolsiz) xonada `None`
    # (reja #38, `pos/service.py::list_live_stations()`).
    console_type: str | None
    rate: int
    status: str
    booking_id: int | None
    ends_at: str | None
    guest_label: str | None


# ── Mahsulotlar ───────────────────────────────────────────────────────────


@router.get(
    "/{club_id}/products", response_model=list[ProductOut], dependencies=[Depends(require_staff)]
)
async def list_products(
    club_id: Annotated[int, Path()], session: Annotated[AsyncSession, Depends(db)]
) -> list[ProductOut]:
    _assert_path_matches_header(club_id)
    rows = await service.list_products(session, club_id)
    return [ProductOut(**r) for r in rows]


@router.post(
    "/{club_id}/products",
    response_model=ProductOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
async def create_product(
    body: ProductCreateIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ProductOut:
    _assert_path_matches_header(club_id)
    row = await service.create_product(
        session,
        club_id=club_id,
        category=body.category,
        name=body.name,
        price=body.price,
        stock_qty=body.stock_qty,
    )
    return ProductOut(**row)


@router.patch(
    "/{club_id}/products/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_admin)],
)
async def update_product(
    body: ProductUpdateIn,
    club_id: Annotated[int, Path()],
    product_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> ProductOut:
    _assert_path_matches_header(club_id)
    row = await service.update_product(
        session,
        club_id=club_id,
        product_id=product_id,
        category=body.category,
        name=body.name,
        price=body.price,
        status=body.status,
        stock_qty=body.stock_qty,
    )
    return ProductOut(**row)


# ── Buyurtmalar ───────────────────────────────────────────────────────────


@router.get(
    "/{club_id}/orders", response_model=list[OrderOut], dependencies=[Depends(require_staff)]
)
async def list_orders(
    club_id: Annotated[int, Path()], session: Annotated[AsyncSession, Depends(db)]
) -> list[OrderOut]:
    _assert_path_matches_header(club_id)
    rows = await service.list_orders(session, club_id)
    return [OrderOut(**r) for r in rows]


@router.post(
    "/{club_id}/orders",
    response_model=OrderOut,
    status_code=201,
    dependencies=[Depends(require_staff)],
)
async def create_order(
    body: OrderCreateIn,
    club_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> OrderOut:
    _assert_path_matches_header(club_id)
    row = await service.create_order(
        session,
        club_id=club_id,
        created_by=int(context.current().user_id or 0),
        booking_id=body.booking_id,
        items=[item.model_dump() for item in body.items],
        payment_method=body.payment_method,
    )
    return OrderOut(**row)


@router.post(
    "/{club_id}/orders/{order_id}/advance",
    status_code=200,
    dependencies=[Depends(require_staff)],
)
async def advance_order(
    club_id: Annotated[int, Path()],
    order_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> dict[str, str]:
    _assert_path_matches_header(club_id)
    status = await service.advance_order(session, club_id=club_id, order_id=order_id)
    return {"status": status}


@router.post(
    "/{club_id}/orders/{order_id}/cancel",
    status_code=200,
    dependencies=[Depends(require_staff)],
)
async def cancel_order(
    club_id: Annotated[int, Path()],
    order_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> dict[str, str]:
    """Faqat `NEW` holatidagi buyurtma bekor qilinadi (loyiha egasi,
    2026-08-16). Qoldiq qaytariladi — `service.cancel_order()`."""
    _assert_path_matches_header(club_id)
    await service.cancel_order(
        session,
        club_id=club_id,
        order_id=order_id,
        cancelled_by=int(context.current().user_id or 0),
    )
    return {"status": "CANCELLED"}


# ── Kassa ─────────────────────────────────────────────────────────────────


@router.get(
    "/{club_id}/bookings/open",
    response_model=list[OpenBookingOut],
    dependencies=[Depends(require_staff)],
)
async def list_open_bookings(
    club_id: Annotated[int, Path()], session: Annotated[AsyncSession, Depends(db)]
) -> list[OpenBookingOut]:
    _assert_path_matches_header(club_id)
    rows = await service.list_open_bookings(session, club_id)
    return [OpenBookingOut(**r) for r in rows]


@router.get(
    "/{club_id}/bookings/{booking_id}/bill",
    response_model=BillOut,
    dependencies=[Depends(require_staff)],
)
async def get_bill(
    club_id: Annotated[int, Path()],
    booking_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> BillOut:
    _assert_path_matches_header(club_id)
    row = await service.get_bill(session, club_id=club_id, booking_id=booking_id)
    return BillOut(**row)


@router.post(
    "/{club_id}/bookings/{booking_id}/close",
    response_model=BillOut,
    dependencies=[Depends(require_staff)],
)
async def close_bill(
    body: CloseBillIn,
    club_id: Annotated[int, Path()],
    booking_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> BillOut:
    _assert_path_matches_header(club_id)
    row = await service.close_bill(
        session,
        club_id=club_id,
        booking_id=booking_id,
        closed_by=int(context.current().user_id or 0),
        payment_method=body.payment_method,
        paid_amount=body.paid_amount,
        shortfall_reason=body.shortfall_reason,
        overpay_reason=body.overpay_reason,
    )
    return BillOut(**row)


@router.get(
    "/{club_id}/bookings/{booking_id}/payment-proof",
    dependencies=[Depends(require_staff)],
)
async def payment_proof(
    club_id: Annotated[int, Path()],
    booking_id: Annotated[int, Path()],
    session: Annotated[AsyncSession, Depends(db)],
) -> Response:
    """To'lov cheki — web Kassa'da ko'rsatish uchun (reja #37).

    Rasm bazada saqlanmaydi (faqat Telegram `file_id`) — TOKEN frontendga
    hech qachon chiqmasin deb backend proxy qiladi (`core/telegram_api.py::
    download_file()`).
    """
    _assert_path_matches_header(club_id)
    file_id = await service.get_payment_proof_file_id(
        session, club_id=club_id, booking_id=booking_id
    )
    downloaded = await telegram_api.download_file(_bot_token(), file_id)
    if downloaded is None:
        raise NotFound("Chekni yuklab bo'lmadi")
    content, content_type = downloaded
    return Response(content=content, media_type=content_type)


# ── Live board ────────────────────────────────────────────────────────────


@router.get(
    "/{club_id}/live", response_model=list[LiveStationOut], dependencies=[Depends(require_staff)]
)
async def list_live(
    club_id: Annotated[int, Path()], session: Annotated[AsyncSession, Depends(db)]
) -> list[LiveStationOut]:
    _assert_path_matches_header(club_id)
    rows = await service.list_live_stations(session, club_id)
    return [LiveStationOut(**r) for r in rows]
