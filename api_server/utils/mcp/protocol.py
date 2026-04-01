"""
MCP协议工具
"""

from typing import Any, Dict, List


def create_error_response(
    id: Any, code: int, message: str, data: Any = None
) -> Dict[str, Any]:
    """
    创建JSON-RPC错误响应

    Args:
        id: 请求ID
        code: 错误码
        message: 错误消息
        data: 额外数据

    Returns:
        JSON-RPC错误响应
    """
    response = {"jsonrpc": "2.0", "id": id, "error": {"code": code, "message": message}}
    if data is not None:
        response["error"]["data"] = data
    return response


def create_success_response(id: Any, result: Any) -> Dict[str, Any]:
    """
    创建JSON-RPC成功响应

    Args:
        id: 请求ID
        result: 结果数据

    Returns:
        JSON-RPC成功响应
    """
    return {"jsonrpc": "2.0", "id": id, "result": result}


def validate_jsonrpc_request(request: Dict[str, Any]) -> bool:
    """
    验证JSON-RPC请求格式

    Args:
        request: JSON-RPC请求

    Returns:
        是否有效
    """
    return (
        isinstance(request, dict)
        and "jsonrpc" in request
        and request["jsonrpc"] == "2.0"
        and "method" in request
        and isinstance(request["method"], str)
    )


def parse_method(method: str) -> tuple[str, str]:
    """
    解析方法名

    Args:
        method: 方法名(如 tools/list, resources/read)

    Returns:
        (类别, 操作) 元组
    """
    if "/" not in method:
        return method, ""
    parts = method.split("/", 1)
    return parts[0], parts[1]


def is_notification(request: Dict[str, Any]) -> bool:
    """
    判断是否为通知(无id的请求)

    Args:
        request: JSON-RPC请求

    Returns:
        是否为通知
    """
    return "id" not in request
