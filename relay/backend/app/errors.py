"""One error shape for the whole API: {"code": "...", "message": "..."}."""

from enum import StrEnum

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    NOT_FOUND = "NOT_FOUND"
    INVALID_IDENTITY = "INVALID_IDENTITY"
    NAME_TAKEN = "NAME_TAKEN"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    RATE_LIMITED = "RATE_LIMITED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


DEFAULT_STATUS_BY_CODE = {
    ErrorCode.INVALID_ARGUMENT: 400,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.INVALID_IDENTITY: 401,
    ErrorCode.NAME_TAKEN: 409,
    ErrorCode.LIMIT_EXCEEDED: 422,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.PERMISSION_DENIED: 403,
}


class ApiError(Exception):
    """Raise anywhere in a request to send a clean error response."""

    def __init__(self, code: ErrorCode, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code or DEFAULT_STATUS_BY_CODE[code]


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(_request: Request, error: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={"code": error.code, "message": error.message},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in problem['loc'])}: {problem['msg']}"
            for problem in error.errors()
        )
        return JSONResponse(
            status_code=400,
            content={"code": ErrorCode.INVALID_ARGUMENT, "message": problems},
        )
