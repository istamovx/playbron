"""PlayBron API — ASGI kirish nuqtasi."""

import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from playbron.core import context, db, errors, redis
from playbron.core.config import settings
from playbron.modules.auth.router import router as auth_router
from playbron.modules.users.router import router as me_router

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","level":"%(levelname)s","msg":"%(message)s"}',
)
log = logging.getLogger("playbron")

API_PREFIX = "/api/v1"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    log.info("PlayBron API ishga tushdi (env=%s)", settings.env)
    yield
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
async def readyz() -> dict[str, object]:
    """Trafik qabul qilishga tayyormi — DB va Redis tekshiriladi."""
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

    checks["ready"] = all(value == "ok" for key, value in checks.items() if key != "ready")
    return checks


app.include_router(auth_router, prefix=API_PREFIX)
app.include_router(me_router, prefix=API_PREFIX)
