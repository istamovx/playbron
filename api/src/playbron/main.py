"""PlayBron API — ASGI kirish nuqtasi."""

import logging
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from playbron.core import context, db, errors, redis
from playbron.core.config import settings
from playbron.core.super_admin_bootstrap import sync_super_admin_password
from playbron.modules.auth import botlogin
from playbron.modules.auth.router import router as auth_router
from playbron.modules.bookings import reminders
from playbron.modules.bookings.router import router as bookings_router
from playbron.modules.bot import router as bot_router_setup
from playbron.modules.bot.router import router as bot_router
from playbron.modules.finance.router import router as finance_router
from playbron.modules.platform.router import router as platform_router
from playbron.modules.pos.router import router as pos_router
from playbron.modules.staff.router import router as staff_router
from playbron.modules.users.router import router as me_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("playbron")

# httpx INFO darajasida to'liq URL yozadi — Bot API URL'ida esa TOKEN bor.
# Token log'ga tushmasligi uchun faqat ogohlantirishlar qoldiriladi.
logging.getLogger("httpx").setLevel(logging.WARNING)

API_PREFIX = "/api/v1"


async def register_webhooks(public_url: str) -> None:
    """Ikkala botning webhook'ini ro'yxatdan o'tkazadi.

    Telegram'da webhook BOTGA tegishli va bitta bot uchun BITTA URL bo'ladi:
    ikkala yuza bir xil tokenni ishlatsa, ikkinchi `setWebhook` birinchisini
    JIMGINA bosib ketadi. Telegram xato bermaydi, log'da ham hech nima
    qolmaydi — tashqaridan bu shunchaki «bot javob bermayapti» bo'lib
    ko'rinadi (`docs/HOLAT.md`, «Nima ishlamayapti — Telegram botlari»).

    Shu holatda ikkinchi ro'yxatdan o'tkazish BAJARILMAYDI: qaysi yuza tirik
    qolgani tasodifga (chaqiruvlar tartibi, tarmoq xatosi) qoldirilmaydi.
    Mijoz boti saqlanadi — konsolga parol bilan ham kirish mumkin, mijozda
    esa botdan boshqa yo'l yo'q. Sabab `log.error` bilan aniq yoziladi.
    """
    admin_token = botlogin.admin_token()
    customer_token = settings.bot_token.get_secret_value()

    if admin_token and admin_token == customer_token:
        log.error(
            "BOT_TOKEN va ADMIN_BOT_TOKEN bitta botni ko‘rsatyapti — admin "
            "webhook'i ro‘yxatdan O‘TKAZILMADI (aks holda mijoz botini bosib "
            "ketardi). @BotFather'dan ALOHIDA bot oching va ADMIN_BOT_TOKEN'ni "
            "o‘shanga qo‘ying, so‘ng servisni qayta ishga tushiring."
        )
        await bot_router_setup.register_customer_webhook(public_url)
        return

    await botlogin.register_webhook(public_url)
    # Mijoz boti — ro'yxatdan o'tish oqimi shu webhook orqali yuradi
    await bot_router_setup.register_customer_webhook(public_url)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    log.info("PlayBron API ishga tushdi (env=%s)", settings.env)

    # `SUPER_ADMIN_PASSWORD` bo'sh bo'lsa darhol qaytadi — sukut holatda
    # no-op. Bitta noto'g'ri sozlangan o'zgaruvchi butun API'ni ishga
    # tushirilmay qoldirmasin (`core/super_admin_bootstrap.py`).
    try:
        await sync_super_admin_password()
    except Exception:
        log.exception("SUPER_ADMIN_PASSWORD sinxronizatsiyasi muvaffaqiyatsiz")

    # Bot orqali kirish uchun webhook — bepul rejada Shell yo'q, shuning uchun
    # `setWebhook` qo'lda emas, har start'da shu yerda (idempotent, xato start'ni
    # to'xtatmaydi). `RENDER_EXTERNAL_URL` ni Render o'zi beradi.
    if settings.env not in {"local", "test"}:
        public_url = settings.public_url or os.environ.get("RENDER_EXTERNAL_URL", "")
        await register_webhooks(public_url)

    # Fon vazifasi — bron eslatmasi. Ishga tushmaslik shartlari
    # `reminders.start()` ichida (test muhiti, token yo'qligi).
    reminder_task = reminders.start()

    yield

    await reminders.stop(reminder_task)
    await db.dispose()
    await redis.close()


app = FastAPI(
    title="PlayBron API",
    version="0.1.0",
    description="PlayStation klublari uchun multi-tenant bron SaaS",
    lifespan=lifespan,
    docs_url="/docs" if settings.env == "local" else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.env == "local" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

errors.install(app)


@app.middleware("http")
async def request_context(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Har bir so'rovga izlanadigan `request_id` beradi va kontekstni tozalaydi."""
    request_id = request.headers.get("x-request-id") or secrets.token_urlsafe(8)
    context.set_context(context.RequestContext(request_id=request_id))

    try:
        response: Response = await call_next(request)
    finally:
        context.reset()

    response.headers["x-request-id"] = request_id
    return response


@app.get("/healthz", tags=["ops"])
async def healthz() -> dict[str, str]:
    """Konteyner tirikmi — tashqi bog'liqliksiz."""
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
async def readyz(response: Response) -> dict[str, object]:
    """Trafik qabul qilishga tayyormi — DB va Redis tekshiriladi.

    Tayyor bo'lmasa HTTP **503** qaytaradi. Avval har doim 200 edi va
    tayyorlik faqat javob TANASIDAGI `ready: false` da ko'rinardi — ya'ni
    holat kodiga qaraydigan har qanday kuzatuvchi (yuk balanslagich,
    Docker healthcheck, tashqi monitoring) bazasi o'lgan API'ni ham
    "sog'lom" deb hisoblardi va trafik yuboraverardi.
    """
    checks: dict[str, object] = {}
    try:
        await db.ping()
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["postgres"] = f"error: {exc.__class__.__name__}"
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc.__class__.__name__}"

    ready = all(value == "ok" for key, value in checks.items() if key != "ready")
    checks["ready"] = ready
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return checks


app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(bot_router, prefix=API_PREFIX)
app.include_router(staff_router, prefix=API_PREFIX)
app.include_router(bookings_router, prefix=API_PREFIX)
app.include_router(pos_router, prefix=API_PREFIX)
app.include_router(finance_router, prefix=API_PREFIX)
app.include_router(platform_router, prefix=API_PREFIX)
app.include_router(me_router, prefix=API_PREFIX)
