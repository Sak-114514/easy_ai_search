"""
认证中间件
"""

from fastapi import Request, HTTPException, Depends
from ..dependencies import get_token_service
from ..services.token_service import TokenService


def get_api_key(
    request: Request,
    token_service: TokenService = Depends(get_token_service),
) -> str:
    """
    从请求中获取 API Key

    Args:
        request: FastAPI 请求对象

    Returns:
        API Key

    Raises:
        HTTPException: API Key 无效
    """
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(status_code=401, detail="API Key required")

    auth_context = token_service.resolve_api_key(api_key)
    if not auth_context:
        raise HTTPException(status_code=403, detail="Invalid API Key")

    request.state.auth_context = auth_context
    token_service.touch_usage(api_key)
    return api_key


def require_admin(
    request: Request,
    token_service: TokenService = Depends(get_token_service),
) -> str:
    """
    需要管理员权限

    Args:
        request: FastAPI 请求对象

    Returns:
        API Key

    Raises:
        HTTPException: 权限不足
    """
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        raise HTTPException(status_code=401, detail="API Key required")

    auth_context = token_service.resolve_api_key(api_key)
    if not auth_context:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    if auth_context.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin permission required")

    request.state.auth_context = auth_context
    token_service.touch_usage(api_key)
    return api_key


def get_client_type(request: Request) -> str:
    """
    从请求中获取客户端类型（MCP 或 REST）

    Args:
        request: FastAPI 请求对象

    Returns:
        客户端类型
    """
    user_agent = request.headers.get("User-Agent", "")
    if "mcp" in user_agent.lower() or "/sse" in request.url.path:
        return "mcp"
    return "rest"
