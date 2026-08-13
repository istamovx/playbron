"""Yagona xato formati: {"error": {"code", "message", "details"}}."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from playbron.core import context

# PostgreSQL: EXCLUDE konstreynt buzilishi (bron to'qnashuvi)
PG_EXCLUSION_VIOLATION = "23P01"
PG_UNIQUE_VIOLATION = "23505"


class AppError(Exception):
    """Barqaror `code` bilan biznes xatosi."""

    status_code = status.HTTP_400_BAD_REQUEST
    code = "BAD_REQUEST"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details or {}


class Unauthorized(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "UNAUTHORIZED"


class Forbidden(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"


class NotFound(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"


class Conflict(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"


class SlotTaken(Conflict):
    code = "SLOT_TAKEN"


class LimitReached(Forbidden):
    code = "LIMIT_REACHED"


class FeatureNotInPlan(Forbidden):
    code = "FEATURE_NOT_IN_PLAN"


def _body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    request_id = context.current().request_id
    if request_id:
        payload["request_id"] = request_id
    return {"error": payload}


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_body("VALIDATION_ERROR", "So‘rov noto‘g‘ri", {"fields": exc.errors()}),
        )

    @app.exception_handler(DBAPIError)
    async def _db_error(_: Request, exc: DBAPIError) -> JSONResponse:
        sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)

        # Bron to'qnashuvi ilova darajasida emas, DB konstreyntida ushlanadi
        if sqlstate == PG_EXCLUSION_VIOLATION:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=_body("SLOT_TAKEN", "Bu vaqt band qilindi"),
            )
        if sqlstate == PG_UNIQUE_VIOLATION:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content=_body("ALREADY_EXISTS", "Bunday yozuv allaqachon bor"),
            )
        raise exc
