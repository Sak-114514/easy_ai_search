"""
日志中间件
"""

import time
from fastapi import Request
from ..services.log_service import LogService


class LoggingMiddleware:
    """日志中间件"""

    def __init__(self, app):
        self.app = app
        self.log_service = LogService()

    async def __call__(self, scope, receive, send):
        """处理请求"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        start_time = time.time()
        status_code = 200

        # 捕获响应状态码
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        # 处理请求
        await self.app(scope, receive, send_wrapper)

        # 记录日志
        response_time = time.time() - start_time
        await self.log_service.log_api(
            endpoint=request.url.path,
            method=request.method,
            status_code=status_code,
            response_time=response_time,
            client_type=getattr(request.state, "client_type", "rest"),
            ip=request.client.host if request.client else None,
            token_name=(getattr(request.state, "auth_context", {}) or {}).get("name"),
        )
