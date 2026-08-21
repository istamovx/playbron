"""POS — mahsulotlar, buyurtmalar, kassa (hisob yopish).

Manba: `api/migrations/versions/0013_pos.py`. RLS defense-in-depth — bu
yerdagi tekshiruvlar HAKAM emas, ikkinchi qatlam.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from playbron.core.audit import log_action
from playbron.core.errors import AppError, NotFound
from playbron.core.text import clean_name
from playbron.modules.finance import shifts
from playbron.modules.pos.settlement import settle_bill

PRODUCT_CATEGORY_MAX = 32
PRODUCT_NAME_MAX = 120


def _product_row(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "category": row.category,
        "name": row.name,
        "price": int(row.price),
        "status": row.status,
        "stock_qty": int(row.stock_qty),
    }


async def list_products(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                "SELECT id, category, name, price, status, stock_qty FROM products"
                " WHERE club_id = :club_id ORDER BY category, name"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [_product_row(r) for r in rows]


async def create_product(
    session: AsyncSession,
    *,
    club_id: int,
    category: str,
    name: str,
    price: int,
    stock_qty: int = 0,
) -> dict[str, Any]:
    name = clean_name(name, limit=PRODUCT_NAME_MAX)
    if len(name) < 1:
        raise AppError("Mahsulot nomini kiriting", code="NAME_REQUIRED")
    category = clean_name(category, limit=PRODUCT_CATEGORY_MAX) or "Boshqa"
    if price <= 0:
        raise AppError("Narx musbat bo'lsin", code="PRICE_INVALID")
    # Qoldiq 0 bo'lishi MUMKIN (hali keltirilmagan mahsulot), lekin manfiy
    # kiritish — kirish xatosi. Sotuv paytida manfiyga tushishi mumkin
    # (`0028` izohi), bu boshqa holat.
    if stock_qty < 0:
        raise AppError("Miqdor manfiy bo'lmasin", code="STOCK_INVALID")

    try:
        product_id = await session.scalar(
            text(
                "INSERT INTO products (club_id, category, name, price, status, stock_qty)"
                " VALUES (:club_id, :category, :name, :price, 'active', :stock_qty) RETURNING id"
            ),
            {
                "club_id": club_id,
                "category": category,
                "name": name,
                "price": price,
                "stock_qty": stock_qty,
            },
        )
    except Exception as exc:  # noqa: BLE001
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if sqlstate == "23505":
            raise AppError("Bu nomli mahsulot allaqachon bor", code="PRODUCT_NAME_TAKEN") from exc
        raise

    await log_action(
        action="product_created",
        target=name,
        club_id=club_id,
        after={"category": category, "name": name, "price": price, "stock_qty": stock_qty},
    )

    return {
        "id": product_id,
        "category": category,
        "name": name,
        "price": price,
        "status": "active",
        "stock_qty": stock_qty,
    }


async def update_product(
    session: AsyncSession,
    *,
    club_id: int,
    product_id: int,
    category: str,
    name: str,
    price: int,
    status: str,
    stock_qty: int | None = None,
) -> dict[str, Any]:
    name = clean_name(name, limit=PRODUCT_NAME_MAX)
    if len(name) < 1:
        raise AppError("Mahsulot nomini kiriting", code="NAME_REQUIRED")
    category = clean_name(category, limit=PRODUCT_CATEGORY_MAX) or "Boshqa"
    if price <= 0:
        raise AppError("Narx musbat bo'lsin", code="PRICE_INVALID")
    if status not in ("active", "archived"):
        raise AppError("Noma'lum holat", code="STATUS_INVALID")
    if stock_qty is not None and stock_qty < 0:
        raise AppError("Miqdor manfiy bo'lmasin", code="STOCK_INVALID")

    row = (
        await session.execute(
            text(
                "UPDATE products SET category = :category, name = :name, price = :price,"
                " status = :status, stock_qty = COALESCE(:stock_qty, stock_qty)"
                " WHERE id = :id AND club_id = :club_id"
                " RETURNING id, category, name, price, status, stock_qty"
            ),
            {
                "category": category,
                "name": name,
                "price": price,
                "status": status,
                "stock_qty": stock_qty,
                "id": product_id,
                "club_id": club_id,
            },
        )
    ).first()
    if row is None:
        raise NotFound("Mahsulot topilmadi")

    await log_action(
        action="product_updated",
        target=name,
        club_id=club_id,
        after={
            "category": category,
            "name": name,
            "price": price,
            "status": status,
            "stock_qty": int(row.stock_qty),
        },
    )

    return _product_row(row)


# ── Buyurtmalar ──────────────────────────────────────────────────────────


def _order_row(row: Any, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": row.id,
        "booking_id": row.booking_id,
        "station_code": row.station_code,
        "status": row.status,
        "total": int(row.total),
        "created_at": row.created_at.isoformat(),
        "items": items,
    }


async def list_orders(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    """Faol buyurtmalar — `DELIVERED` bo'lmagan, shuningdek so'nggi soatda
    yetkazilganlar (xodim darhol yo'qolib qolmasligini ko'rsin)."""
    rows = (
        await session.execute(
            text(
                "SELECT o.id, o.booking_id, o.status, o.total, o.created_at,"
                "       s.code AS station_code"
                " FROM orders o"
                " LEFT JOIN bookings b ON b.id = o.booking_id"
                " LEFT JOIN stations s ON s.id = b.station_id"
                " WHERE o.club_id = :club_id"
                # Yakunlangan holatlar (`DELIVERED`/`CANCELLED`) faqat
                # so'nggi soat ichida ko'rinadi. `CANCELLED`siz butun
                # tarixdagi bekor qilingan buyurtmalar har so'rovda
                # tashilardi va UI'da jimgina tashlab yuborilardi.
                "   AND (o.status NOT IN ('DELIVERED', 'CANCELLED')"
                "        OR o.created_at > now() - interval '1 hour')"
                " ORDER BY o.created_at DESC"
            ),
            {"club_id": club_id},
        )
    ).all()
    if not rows:
        return []

    order_ids = [r.id for r in rows]
    item_rows = (
        await session.execute(
            text(
                "SELECT order_id, product_name, qty, price_snapshot"
                " FROM order_items WHERE order_id = ANY(:ids) ORDER BY id"
            ),
            {"ids": order_ids},
        )
    ).all()
    items_by_order: dict[int, list[dict[str, Any]]] = {}
    for item in item_rows:
        items_by_order.setdefault(item.order_id, []).append(
            {
                "product_name": item.product_name,
                "qty": item.qty,
                "price_snapshot": int(item.price_snapshot),
            }
        )

    return [_order_row(r, items_by_order.get(r.id, [])) for r in rows]


async def _record_payment(
    session: AsyncSession,
    *,
    club_id: int,
    staff_id: int,
    method: str,
    amount: int,
    booking_id: int | None = None,
    order_id: int | None = None,
    kind: str = "FINAL",
) -> int | None:
    """`payments` qatorini yozadi va `shift_id`ni qaytaradi.

    Naqd uchun ochiq smena MAJBURIY — aks holda pul kassadan tashqarida
    qolardi va smena farqi doim noto'g'ri chiqardi.
    """
    if amount <= 0:
        return None

    shift_id = await shifts.open_shift_id(session, club_id=club_id, staff_id=staff_id)
    if method == "CASH" and shift_id is None:
        raise AppError(
            "Naqd to'lovni qabul qilish uchun avval smenani oching",
            code="SHIFT_REQUIRED",
            status_code=409,
        )

    await session.execute(
        text(
            "INSERT INTO payments"
            " (club_id, shift_id, booking_id, order_id, kind, method, amount, created_by)"
            " VALUES (:club_id, :shift_id, :booking_id, :order_id, :kind, :method,"
            "         :amount, :staff)"
        ),
        {
            "club_id": club_id,
            "shift_id": shift_id,
            "booking_id": booking_id,
            "order_id": order_id,
            "kind": kind,
            "method": method,
            "amount": amount,
            "staff": staff_id,
        },
    )

    # `CLAUDE.md`, «Pul»: pulga tegadigan HAR amal audit iziga tushadi.
    # Nizoli yopishda `payments` qatori bor-u, kim qilgani yo'q bo'lsa —
    # iz aynan kerak bo'lgan joyda uzilardi.
    await log_action(
        action="payment_refunded" if kind == "REFUND" else "payment_recorded",
        target=f"booking:{booking_id}" if booking_id else f"order:{order_id}",
        club_id=club_id,
        after={"method": method, "amount": amount, "shift_id": shift_id, "kind": kind},
    )
    return shift_id


async def create_order(
    session: AsyncSession,
    *,
    club_id: int,
    created_by: int,
    booking_id: int | None,
    items: list[dict[str, Any]],
    payment_method: str | None = None,
) -> dict[str, Any]:
    if not items:
        raise AppError("Kamida bitta mahsulot tanlang", code="ORDER_EMPTY")

    # Bronsiz sotuv (o'tkinchi mijoz) — hisob yopish bosqichi yo'q, pul
    # DARHOL olinadi. Ilgari bunday buyurtmada to'lov umuman yozilmasdi:
    # summa hisobotga tushardi, kassaga esa tushmasdi va smena farqi doim
    # musbat chiqardi (`docs/audit-report.md` §2.3).
    if booking_id is None:
        if payment_method not in ("CASH", "TRANSFER"):
            raise AppError(
                "Bronsiz sotuv uchun to'lov turini tanlang",
                code="PAYMENT_METHOD_REQUIRED",
                status_code=422,
            )
    elif payment_method is not None:
        raise AppError(
            "Bronga biriktirilgan buyurtma hisob yopilganda to'lanadi",
            code="PAYMENT_METHOD_NOT_ALLOWED",
            status_code=422,
        )

    if booking_id is not None:
        booking = (
            await session.execute(
                text("SELECT id FROM bookings WHERE id = :id AND club_id = :club_id"),
                {"id": booking_id, "club_id": club_id},
            )
        ).first()
        if booking is None:
            raise NotFound("Bron topilmadi")

    product_ids = [int(item["product_id"]) for item in items]
    rows = (
        await session.execute(
            text(
                "SELECT id, name, price FROM products"
                " WHERE club_id = :club_id AND id = ANY(:ids) AND status = 'active'"
            ),
            {"club_id": club_id, "ids": product_ids},
        )
    ).all()
    by_id = {r.id: r for r in rows}

    resolved: list[dict[str, Any]] = []
    total = 0
    for item in items:
        product_id = int(item["product_id"])
        qty = int(item["qty"])
        if qty <= 0:
            raise AppError("Miqdor musbat bo'lsin", code="QTY_INVALID")
        product = by_id.get(product_id)
        if product is None:
            raise AppError("Mahsulot topilmadi yoki faol emas", code="PRODUCT_NOT_FOUND")
        line_total = int(product.price) * qty
        total += line_total
        resolved.append(
            {
                "product_id": product_id,
                "product_name": product.name,
                "qty": qty,
                "price_snapshot": int(product.price),
            }
        )

    order_id = await session.scalar(
        text(
            "INSERT INTO orders (club_id, booking_id, status, created_by, total)"
            " VALUES (:club_id, :booking_id, 'NEW', :created_by, :total) RETURNING id"
        ),
        {"club_id": club_id, "booking_id": booking_id, "created_by": created_by, "total": total},
    )

    for line in resolved:
        await session.execute(
            text(
                "INSERT INTO order_items"
                " (club_id, order_id, product_id, product_name, qty, price_snapshot)"
                " VALUES (:club_id, :order_id, :product_id, :product_name, :qty, :price)"
            ),
            {
                "club_id": club_id,
                "order_id": order_id,
                "product_id": line["product_id"],
                "product_name": line["product_name"],
                "qty": line["qty"],
                "price": line["price_snapshot"],
            },
        )
        # Qoldiq kamayadi. Yetmasa ham sotuv TO'XTAMAYDI (`0028` izohi:
        # klub qoldiqni yuritmayotgan bo'lishi mumkin) — manfiy qiymat
        # "hisobga olinmagan" degan rost belgi bo'lib qoladi.
        await session.execute(
            text("UPDATE products SET stock_qty = stock_qty - :qty WHERE id = :id"),
            {"qty": line["qty"], "id": line["product_id"]},
        )

    if booking_id is None and payment_method is not None:
        await _record_payment(
            session,
            club_id=club_id,
            staff_id=created_by,
            method=payment_method,
            amount=total,
            order_id=order_id,
        )

    row = (
        await session.execute(
            text(
                "SELECT o.id, o.booking_id, o.status, o.total, o.created_at,"
                "       s.code AS station_code"
                " FROM orders o"
                " LEFT JOIN bookings b ON b.id = o.booking_id"
                " LEFT JOIN stations s ON s.id = b.station_id"
                " WHERE o.id = :id"
            ),
            {"id": order_id},
        )
    ).first()
    if row is None:
        raise NotFound("Buyurtma topilmadi")  # amalda yuz bermaydi — hozirgina yaratildi
    return _order_row(row, resolved)


_NEXT_STATUS = {"NEW": "ACCEPTED", "ACCEPTED": "PREPARING", "PREPARING": "DELIVERED"}


async def advance_order(session: AsyncSession, *, club_id: int, order_id: int) -> str:
    row = (
        await session.execute(
            text(
                "SELECT status, booking_id, total FROM orders"
                " WHERE id = :id AND club_id = :club_id"
            ),
            {"id": order_id, "club_id": club_id},
        )
    ).first()
    if row is None:
        raise NotFound("Buyurtma topilmadi")

    nxt = _NEXT_STATUS.get(row.status)
    if nxt is None:
        raise AppError(
            "Buyurtma allaqachon yetkazilgan", code="ORDER_ALREADY_DELIVERED", status_code=409
        )

    await session.execute(
        text("UPDATE orders SET status = :status WHERE id = :id"), {"status": nxt, "id": order_id}
    )
    return nxt


async def cancel_order(
    session: AsyncSession, *, club_id: int, order_id: int, cancelled_by: int
) -> None:
    """Buyurtmani bekor qiladi — FAQAT `NEW` holatida.

    Loyiha egasi (2026-08-16): "xodim buyurtma kiritganda uni bekor
    qilishi ham mumkin, bu yangi bo'lgan qiymatida mumkin faqat". Bar
    allaqachon qabul qilgan (`ACCEPTED`+) buyurtma bekor qilinmaydi —
    mahsulot tayyorlana boshlagan bo'lishi mumkin.

    Qoldiq QAYTARILADI (`create_order()` uni kamaytirgan edi) — aks holda
    har bekor qilingan buyurtma omborni jimgina yeb ketardi.
    """
    row = (
        await session.execute(
            text(
                "SELECT status, booking_id, total FROM orders"
                " WHERE id = :id AND club_id = :club_id"
            ),
            {"id": order_id, "club_id": club_id},
        )
    ).first()
    if row is None:
        raise NotFound("Buyurtma topilmadi")

    if row.status != "NEW":
        raise AppError(
            "Faqat yangi buyurtmani bekor qilish mumkin",
            code="ORDER_NOT_CANCELLABLE",
            status_code=409,
        )

    await session.execute(
        text(
            "UPDATE products p SET stock_qty = p.stock_qty + i.qty"
            " FROM order_items i"
            " WHERE i.order_id = :id AND i.product_id = p.id"
        ),
        {"id": order_id},
    )
    await session.execute(
        text("UPDATE orders SET status = 'CANCELLED' WHERE id = :id"), {"id": order_id}
    )

    # Bronsiz sotuv YARATILGANDA pul olingan edi (`create_order()`), demak
    # bekor qilinganda u QAYTARILADI. Aks holda to'lov qatori qolib
    # ketardi: kassa o'sha summaga ko'p kutar, hisobot esa qaytarilgan
    # pulni "olingan tushum" deb sanayverardi.
    for payment in await _order_payments(session, club_id=club_id, order_id=order_id):
        await _record_payment(
            session,
            club_id=club_id,
            staff_id=cancelled_by,
            method=payment.method,
            amount=int(payment.amount),
            order_id=order_id,
            kind="REFUND",
        )

    await log_action(action="order_cancelled", target=str(order_id), club_id=club_id)


async def _order_payments(session: AsyncSession, *, club_id: int, order_id: int) -> list[Any]:
    """Buyurtmaning hali qaytarilmagan to'lovlari (FINAL − REFUND).

    Bir xil `method` bo'yicha yig'iladi: qisman qaytarim hozircha yo'q,
    lekin ikki marta qaytarib yuborilmasligi uchun ayirma olinadi.
    """
    return list(
        (
            await session.execute(
                text(
                    "SELECT method,"
                    "       SUM(CASE WHEN kind = 'REFUND' THEN -amount ELSE amount END) AS amount"
                    " FROM payments WHERE order_id = :id AND club_id = :club_id"
                    " GROUP BY method HAVING"
                    "   SUM(CASE WHEN kind = 'REFUND' THEN -amount ELSE amount END) > 0"
                ),
                {"id": order_id, "club_id": club_id},
            )
        ).all()
    )


# ── Kassa (hisob yopish) ─────────────────────────────────────────────────


async def list_open_bookings(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    """Hali yopilmagan tasdiqlangan bronlar — kassa ro'yxati."""
    rows = (
        await session.execute(
            text(
                "SELECT b.id, s.code AS station_code, b.hours, b.rate_snapshot, b.play_amount,"
                "       lower(b.period) AS starts_at, upper(b.period) AS ends_at,"
                "       COALESCE(u.display_name, u.first_name, b.guest_name) AS guest_label"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
                " LEFT JOIN users u ON u.id = b.customer_id"
                " WHERE b.club_id = :club_id AND b.status = 'CONFIRMED' AND b.closed_at IS NULL"
                " ORDER BY lower(b.period)"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [
        {
            "id": r.id,
            "station_code": r.station_code,
            "hours": r.hours,
            "rate_snapshot": int(r.rate_snapshot),
            "play_amount": int(r.play_amount),
            "starts_at": r.starts_at.isoformat(),
            "ends_at": r.ends_at.isoformat(),
            "guest_label": r.guest_label,
        }
        for r in rows
    ]


async def _load_open_booking(session: AsyncSession, club_id: int, booking_id: int) -> Any:
    row = (
        await session.execute(
            text(
                "SELECT b.id, b.hours, b.rate_snapshot, b.play_amount, b.status, b.closed_at,"
                "       b.customer_id, b.payment_proof_status, s.code AS station_code,"
                "       c.name AS club_name, c.staff_max_discount_percent"
                " FROM bookings b"
                " JOIN stations s ON s.id = b.station_id"
                " JOIN clubs c ON c.id = b.club_id"
                " WHERE b.id = :id AND b.club_id = :club_id"
            ),
            {"id": booking_id, "club_id": club_id},
        )
    ).first()
    if row is None:
        raise NotFound("Bron topilmadi")
    if row.status != "CONFIRMED":
        raise AppError("Bron tasdiqlanmagan", code="BOOKING_NOT_CONFIRMED", status_code=409)
    if row.closed_at is not None:
        raise AppError("Hisob allaqachon yopilgan", code="BILL_ALREADY_CLOSED", status_code=409)
    return row


async def _orders_total(session: AsyncSession, *, club_id: int, booking_id: int) -> int:
    """Bron bo'yicha bar buyurtmalari summasi — `CANCELLED`siz.

    `get_bill()` va `close_bill()` AYNAN bir xil summani hisoblashi shart:
    biri ko'rsatadi, ikkinchisi pul oladi. Avval ikkala joyda alohida
    so'rov turardi va `CANCELLED` filtri IKKALASIDA ham yo'q edi — xodim
    yangi buyurtmani bekor qilsa, mahsulot omborga qaytardi, LEKIN summa
    mijoz hisobida qolardi va undan pul olinardi (audit topilmasi,
    2026-08-16; `0028_stock_and_order_cancel.py` bilan kelib chiqqan
    regressiya). Yagona funksiya — filtr boshqa hech qachon ajralmasin.
    """
    total = await session.scalar(
        text(
            "SELECT COALESCE(SUM(total), 0) FROM orders"
            " WHERE booking_id = :id AND club_id = :club_id AND status <> 'CANCELLED'"
        ),
        {"id": booking_id, "club_id": club_id},
    )
    return int(total or 0)


async def get_bill(session: AsyncSession, *, club_id: int, booking_id: int) -> dict[str, Any]:
    booking = await _load_open_booking(session, club_id, booking_id)
    # Ustundan — tarif vaqtga qarab o'zgarsa bron ikki xil narxdagi
    # bo'laklardan iborat bo'ladi (`0037_rooms_tariffs.py`). `settlement.py::
    # play_amount()` (`rate_snapshot * hours`) BU YERDA ishlatilmaydi —
    # o'zgaruvchan tarifda ular teng bo'lmaydi (`CLAUDE.md` §Pul).
    play_total = int(booking.play_amount)

    orders_total = await _orders_total(session, club_id=club_id, booking_id=booking_id)

    return {
        "booking_id": booking_id,
        "play_amount": play_total,
        "orders_amount": int(orders_total),
        "total": play_total + int(orders_total),
        "awaiting_proof": booking.payment_proof_status == "PENDING",
        "payment_proof_status": booking.payment_proof_status,
    }


_PAYMENT_PROOF_TEXT = (
    "💳 {club} — {station} hisobi uchun o'tkazma kvitansiyasini (skrinshot yoki"
    " rasm) shu yerga yuboring. Xodim tekshirib, hisobni yopadi."
)


async def _request_payment_proof(session: AsyncSession, booking: Any) -> None:
    """Reja #37 (loyiha egasi, 2026-08-16) — mijozga bot orqali chek so'raladi.
    Best-effort: xato bo'lsa ham hisob yopish oqimini to'xtatmaydi."""
    from playbron.core import telegram_api
    from playbron.core.config import settings

    token = settings.bot_token.get_secret_value()
    if not token or booking.customer_id is None:
        return
    tg_id = (
        await session.execute(
            text("SELECT telegram_id FROM users WHERE id = :id"), {"id": booking.customer_id}
        )
    ).scalar_one_or_none()
    if tg_id is None:
        return
    await telegram_api.send_message(
        token,
        int(tg_id),
        _PAYMENT_PROOF_TEXT.format(club=booking.club_name, station=booking.station_code),
    )


def _assert_discount_allowed(
    *,
    actor_role: str | None,
    discount_amount: int,
    total: int,
    limit_percent: int,
) -> None:
    """Xodim chegirmasi klub chegarasidan oshmasin (`0039_discount_policy`).

    Rol auditi topilmasi (2026-08-18): `STAFF` roli `paid_amount = 0` +
    `DISCOUNT` bilan istalgan hisobni to'liq nolga yopa olardi — chegara
    ham, tasdiq ham yo'q edi.

    `OWNER`/`ADMIN` chegaradan TASHQARIDA: chegirma ularning biznes qarori.
    Rol noma'lum bo'lsa (`None`) eng qattiq yo'l tanlanadi — xodim deb
    hisoblanadi. Teskarisi yozilsa, klaymi buzilgan chaqiruv jimgina
    cheklovsiz o'tib ketardi.

    Sof funksiya — DB'siz test bilan qoplanadi (`CLAUDE.md` §Testlar).
    """
    if actor_role in ("OWNER", "ADMIN"):
        return
    if discount_amount <= 0:
        return
    # `total == 0` da har qanday chegirma 100% — foizga bo'linish emas,
    # aniq taqqoslash kerak, aks holda nolga bo'linish chiqardi.
    if total <= 0 or discount_amount * 100 > total * limit_percent:
        raise AppError(
            f"Xodim chegirmasi {limit_percent}% dan oshmasligi kerak —"
            " kattaroq chegirmani klub egasi yoki admin beradi",
            code="DISCOUNT_LIMIT_EXCEEDED",
            status_code=422,
        )


async def close_bill(
    session: AsyncSession,
    *,
    club_id: int,
    booking_id: int,
    closed_by: int,
    payment_method: str,
    paid_amount: int,
    shortfall_reason: str | None = None,
    overpay_reason: str | None = None,
    actor_role: str | None = None,
) -> dict[str, Any]:
    """O'tkazma + botga ulangan mijoz — chek talab qilinadi (reja #37):

    1-chaqiruv (`payment_proof_status IS NULL`): hisob YOPILMAYDI, mijozga
       chek so'raladi, `PENDING`.
    Mijoz botga rasm yuborsa (`bot/customer.py`): `SUBMITTED`.
    2-chaqiruv (`payment_proof_status == 'SUBMITTED'`): bu ENDI tasdiqlash —
       hisob yopiladi, `CONFIRMED`.

    Guest/staff bron (`customer_id IS NULL`) — botga murojaat qilib
    bo'lmaydi, TRANSFER ham DARHOL yopiladi (eski xatti-harakat).
    """
    if payment_method not in ("CASH", "TRANSFER"):
        raise AppError("To'lov turi noto'g'ri", code="PAYMENT_METHOD_INVALID")
    if paid_amount < 0:
        raise AppError("Summani tekshiring", code="PAID_AMOUNT_INVALID")

    booking = await _load_open_booking(session, club_id, booking_id)
    # Ustundan — tarif vaqtga qarab o'zgarsa bron ikki xil narxdagi
    # bo'laklardan iborat bo'ladi (`0037_rooms_tariffs.py`). `settlement.py::
    # play_amount()` (`rate_snapshot * hours`) BU YERDA ishlatilmaydi —
    # o'zgaruvchan tarifda ular teng bo'lmaydi (`CLAUDE.md` §Pul).
    play_total = int(booking.play_amount)

    orders_total = await _orders_total(session, club_id=club_id, booking_id=booking_id)
    total = play_total + orders_total

    requires_proof = payment_method == "TRANSFER" and booking.customer_id is not None
    if requires_proof and booking.payment_proof_status != "SUBMITTED":
        if booking.payment_proof_status is None:
            await session.execute(
                text("UPDATE bookings SET payment_proof_status = 'PENDING' WHERE id = :id"),
                {"id": booking_id},
            )
            await _request_payment_proof(session, booking)
        return {
            "booking_id": booking_id,
            "play_amount": play_total,
            "orders_amount": int(orders_total),
            "total": total,
            "awaiting_proof": True,
            "payment_proof_status": booking.payment_proof_status or "PENDING",
        }

    # Farq taqsimoti — sof funksiyada (`settlement.py`), sabablari o'sha
    # yerda hujjatlashtirilgan. Servis faqat o'qiydi, chaqiradi, yozadi.
    settlement = settle_bill(
        total=total,
        paid_amount=paid_amount,
        shortfall_reason=shortfall_reason,
        overpay_reason=overpay_reason,
    )
    if settlement.discount_amount > 0:
        # Xodim chegirmasi klub chegarasidan oshmasin (`0039_discount_policy`,
        # keyinchalik `0039` ga ko'chirildi — raqam to'qnashuvi tufayli).
        _assert_discount_allowed(
            actor_role=actor_role,
            discount_amount=settlement.discount_amount,
            total=total,
            limit_percent=int(booking.staff_max_discount_percent),
        )

    # To'lov yozuvi UPDATE'dan OLDIN — naqd uchun ochiq smena yo'q bo'lsa
    # `SHIFT_REQUIRED` chiqadi va hisob YOPILMAY qoladi.
    await _record_payment(
        session,
        club_id=club_id,
        staff_id=closed_by,
        method=payment_method,
        amount=paid_amount,
        booking_id=booking_id,
    )

    final_proof_status = "CONFIRMED" if requires_proof else None
    await session.execute(
        text(
            "UPDATE bookings SET closed_at = :now, payment_method = :method,"
            " paid_amount = :amount, closed_by = :staff, payment_proof_status = :proof,"
            " discount_amount = :discount, debt_amount = :debt, tip_amount = :tip"
            " WHERE id = :id"
        ),
        {
            "now": datetime.now(UTC),
            "method": payment_method,
            "amount": paid_amount,
            "staff": closed_by,
            "proof": final_proof_status,
            "discount": settlement.discount_amount,
            "debt": settlement.debt_amount,
            "tip": settlement.tip_amount,
            "id": booking_id,
        },
    )

    # Hisob yopilishining O'ZI audit izini qoldiradi — `_record_payment()`
    # ga tayanib bo'lmaydi: u `amount <= 0` da darhol qaytadi, ya'ni 100%
    # chegirma yoki qarz bilan yopilgan hisob (rol auditi topilmasi,
    # 2026-08-18) `payments` da ham, jurnalda ham UMUMAN ko'rinmasdi.
    # Nomlangan farq (chegirma/qarz/choychaqa) va sababi shu yerda —
    # `CLAUDE.md` §Pul.
    await log_action(
        action="bill_closed",
        target=f"booking:{booking_id}",
        club_id=club_id,
        after={
            "total": total,
            "paid_amount": paid_amount,
            "method": payment_method,
            "discount_amount": settlement.discount_amount,
            "debt_amount": settlement.debt_amount,
            "tip_amount": settlement.tip_amount,
        },
    )

    # `get_bill()` ISHLATILMAYDI — u `_load_open_booking()` orqali "hali
    # ochiqmi" deb tekshiradi; biz esa HOZIRGINA yopdik, o'ziga qarshi
    # BILL_ALREADY_CLOSED qaytarardi.
    return {
        "booking_id": booking_id,
        "play_amount": play_total,
        "orders_amount": int(orders_total),
        "total": total,
        "awaiting_proof": False,
        "payment_proof_status": final_proof_status,
        "discount_amount": settlement.discount_amount,
        "debt_amount": settlement.debt_amount,
        "tip_amount": settlement.tip_amount,
    }


async def get_payment_proof_file_id(session: AsyncSession, *, club_id: int, booking_id: int) -> str:
    """Web Kassa'da chekni ko'rsatish uchun — `router.py`da Telegram'dan
    yuklab, proxy qilinadi (token frontendga chiqmaydi)."""
    row = (
        await session.execute(
            text(
                "SELECT payment_proof_file_id FROM bookings"
                " WHERE id = :id AND club_id = :club_id"
            ),
            {"id": booking_id, "club_id": club_id},
        )
    ).first()
    if row is None or row.payment_proof_file_id is None:
        raise NotFound("Chek hali yuborilmagan")
    return str(row.payment_proof_file_id)


# ── Live board ───────────────────────────────────────────────────────────


async def list_live_stations(session: AsyncSession, club_id: int) -> list[dict[str, Any]]:
    """Xonalar + shu lahzadagi bandlik — CONFIRMED bron `now()`ni o'z ichiga
    olsa band, aks holda bo'sh (`stations.status='maintenance'` ustun turadi)."""
    rows = (
        await session.execute(
            text(
                "SELECT s.id, s.code, s.room_label,"
                # Band bo'lsa BRONning konsoli ustuvor (xona "sukut"idan farqli
                # bo'lishi mumkin, reja #38); bo'sh bo'lsa eski xonaning
                # (0023'dan oldingi) konsoli, yangi xonada ikkalasi ham NULL.
                "       COALESCE(b.console_type, s.console_type) AS console_type,"
                "       s.rate, s.status,"
                "       b.id AS booking_id, upper(b.period) AS ends_at,"
                "       COALESCE(u.display_name, u.first_name, b.guest_name) AS guest_label"
                " FROM stations s"
                " LEFT JOIN bookings b ON b.station_id = s.id AND b.status = 'CONFIRMED'"
                "   AND b.period @> now() AND b.closed_at IS NULL"
                " LEFT JOIN users u ON u.id = b.customer_id"
                " WHERE s.club_id = :club_id"
                " ORDER BY s.code"
            ),
            {"club_id": club_id},
        )
    ).all()
    return [
        {
            "id": r.id,
            "code": r.code,
            "room_label": r.room_label,
            "console_type": r.console_type,
            "rate": int(r.rate),
            "status": r.status,
            "booking_id": r.booking_id,
            "ends_at": r.ends_at.isoformat() if r.ends_at else None,
            "guest_label": r.guest_label,
        }
        for r in rows
    ]
