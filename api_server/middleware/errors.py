"""
全局异常处理器
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from typing import Any
import logging

logger = logging.getLogger(__name__)


def build_internal_http_exception(action: str, exc: Exception = None) -> HTTPException:
    """构建不泄露内部细节的 500 响应。"""
    if exc is not None:
        logger.exception("%s failed: %s", action, exc)
    else:
        logger.error("%s failed", action)
    return HTTPException(status_code=500, detail=f"{action} failed")


class APIError(Exception):
    """API基础异常类"""

    def __init__(
        self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(APIError):
    """验证错误"""

    def __init__(self, message: str, details: Any = None):
        super().__init__(message, code="VALIDATION_ERROR", status_code=400)
        self.details = details


class AuthenticationError(APIError):
    """认证错误"""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code="AUTHENTICATION_ERROR", status_code=401)


class AuthorizationError(APIError):
    """授权错误"""

    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, code="AUTHORIZATION_ERROR", status_code=403)


class NotFoundError(APIError):
    """资源未找到错误"""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="NOT_FOUND", status_code=404)


class ConflictError(APIError):
    """冲突错误"""

    def __init__(self, message: str = "Resource conflict"):
        super().__init__(message, code="CONFLICT", status_code=409)


class RateLimitError(APIError):
    """限流错误"""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, code="RATE_LIMIT_EXCEEDED", status_code=429)


async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    """处理API异常"""
    logger.error(
        f"API Error: {exc.code} - {exc.message}", extra={"path": request.url.path}
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": getattr(exc, "details", None),
            },
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """处理HTTP异常"""
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail}",
        extra={"path": request.url.path},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
            },
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """处理请求验证错误"""
    logger.warning(
        f"Validation Error: {exc.errors()}",
        extra={"path": request.url.path},
    )

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        },
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """处理通用异常"""
    logger.error(
        f"Unhandled Exception: {type(exc).__name__} - {str(exc)}",
        extra={"path": request.url.path},
        exc_info=True,
    )

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal server error occurred",
            },
        },
    )


def setup_exception_handlers(app):
    """设置异常处理器"""
    app.add_exception_handler(APIError, api_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, general_exception_handler)
