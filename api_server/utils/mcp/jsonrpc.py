"""
JSON-RPC 2.0 处理器
"""

import json
import logging
from typing import Any, AsyncGenerator, Callable, Dict, List

from .protocol import (
    create_error_response,
    create_success_response,
    is_notification,
    parse_method,
    validate_jsonrpc_request,
)

logger = logging.getLogger(__name__)


class JSONRPCErrorCodes:
    """JSON-RPC错误码"""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


class JSONRPCRequest:
    """JSON-RPC请求对象"""

    def __init__(self, request_data: str):
        """
        初始化请求

        Args:
            request_data: JSON字符串
        """
        try:
            self.raw = request_data
            self.data = json.loads(request_data)
            self.is_valid = validate_jsonrpc_request(self.data)
            self.method = self.data.get("method", "")
            self.params = self.data.get("params", {})
            self.id = self.data.get("id")
            self.is_notification = is_notification(self.data)
        except json.JSONDecodeError as e:
            self.raw = request_data
            self.data = None
            self.is_valid = False
            self.method = ""
            self.params = {}
            self.id = None
            self.is_notification = False
            self.parse_error = str(e)


class JSONRPCResponse:
    """JSON-RPC响应对象"""

    def __init__(
        self, request: JSONRPCRequest, result: Any = None, error: Dict[str, Any] = None
    ):
        """
        初始化响应

        Args:
            request: 请求对象
            result: 成功结果
            error: 错误信息
        """
        self.request = request
        self.result = result
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        Returns:
            响应字典
        """
        if self.request.is_notification:
            return {}

        if self.error:
            return create_error_response(
                self.request.id,
                self.error.get("code", JSONRPCErrorCodes.INTERNAL_ERROR),
                self.error.get("message", "Unknown error"),
                self.error.get("data"),
            )
        else:
            return create_success_response(self.request.id, self.result)

    def to_json(self) -> str:
        """
        转换为JSON字符串

        Returns:
            JSON字符串
        """
        if self.request.is_notification:
            return ""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class JSONRPCHandler:
    """JSON-RPC处理器"""

    def __init__(self):
        """初始化处理器"""
        self.method_handlers: Dict[str, Callable] = {}
        self.prefix_handlers: Dict[str, Callable] = {}

    def register_method(self, method: str, handler: Callable):
        """
        注册方法处理器

        Args:
            method: 方法名
            handler: 处理函数
        """
        self.method_handlers[method] = handler
        logger.info(f"注册方法处理器: {method}")

    def register_prefix(self, prefix: str, handler: Callable):
        """
        注册前缀处理器

        Args:
            prefix: 方法前缀(如 tools, resources)
            handler: 处理函数
        """
        self.prefix_handlers[prefix] = handler
        logger.info(f"注册前缀处理器: {prefix}")

    async def handle_request(self, request_data: str) -> JSONRPCResponse:
        """
        处理JSON-RPC请求

        Args:
            request_data: JSON字符串

        Returns:
            响应对象
        """
        try:
            request = JSONRPCRequest(request_data)

            if not request.is_valid:
                if hasattr(request, "parse_error"):
                    return JSONRPCResponse(
                        request,
                        error={
                            "code": JSONRPCErrorCodes.PARSE_ERROR,
                            "message": f"Parse error: {request.parse_error}",
                        },
                    )
                else:
                    return JSONRPCResponse(
                        request,
                        error={
                            "code": JSONRPCErrorCodes.INVALID_REQUEST,
                            "message": "Invalid Request",
                        },
                    )

            if not request.method:
                return JSONRPCResponse(
                    request,
                    error={
                        "code": JSONRPCErrorCodes.INVALID_REQUEST,
                        "message": "Missing method",
                    },
                )

            logger.info(f"处理请求: {request.method}")

            prefix, action = parse_method(request.method)

            handler = None
            if request.method in self.method_handlers:
                handler = self.method_handlers[request.method]
            elif prefix in self.prefix_handlers:
                handler = self.prefix_handlers[prefix]

            if handler is None:
                return JSONRPCResponse(
                    request,
                    error={
                        "code": JSONRPCErrorCodes.METHOD_NOT_FOUND,
                        "message": f"Method not found: {request.method}",
                    },
                )

            try:
                result = await handler(request.method, request.params)
                return JSONRPCResponse(request, result=result)
            except ValueError as e:
                return JSONRPCResponse(
                    request,
                    error={"code": JSONRPCErrorCodes.INVALID_PARAMS, "message": str(e)},
                )
            except Exception as e:
                logger.exception(f"处理请求失败: {request.method}")
                return JSONRPCResponse(
                    request,
                    error={"code": JSONRPCErrorCodes.INTERNAL_ERROR, "message": str(e)},
                )

        except Exception as e:
            logger.exception(f"处理请求失败: {request_data}")
            return JSONRPCResponse(
                JSONRPCRequest(request_data),
                error={"code": JSONRPCErrorCodes.INTERNAL_ERROR, "message": str(e)},
            )

    async def handle_batch(self, batch_data: str) -> List[JSONRPCResponse]:
        """
        处理批量请求

        Args:
            batch_data: JSON数组字符串

        Returns:
            响应列表
        """
        try:
            requests = json.loads(batch_data)
            if not isinstance(requests, list):
                raise ValueError("Batch requests must be an array")

            responses = []
            for req in requests:
                response = await self.handle_request(json.dumps(req))
                if not response.request.is_notification:
                    responses.append(response)

            return responses

        except json.JSONDecodeError:
            return [
                JSONRPCResponse(
                    JSONRPCRequest(batch_data),
                    error={
                        "code": JSONRPCErrorCodes.PARSE_ERROR,
                        "message": "Parse error",
                    },
                )
            ]
