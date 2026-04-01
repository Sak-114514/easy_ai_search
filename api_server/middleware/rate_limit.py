"""
限流中间件
"""

from fastapi import Request, HTTPException
from collections import defaultdict
from time import time
import threading
from ..config import get_api_config


class RateLimitMiddleware:
    """限流中间件"""

    def __init__(self, app):
        self.app = app
        self.config = get_api_config()
        self._requests = defaultdict(list)
        self._lock = threading.Lock()

    async def __call__(self, scope, receive, send):
        """处理请求"""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if not self.config.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)
        client_id = request.client.host if request.client else "unknown"

        # 检查限流
        now = time()
        window = self.config.rate_limit_window
        limit = self.config.rate_limit_requests

        with self._lock:
            # 清理过期记录
            self._requests[client_id] = [
                t for t in self._requests[client_id] if now - t < window
            ]

            # 检查是否超过限制
            if len(self._requests[client_id]) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Max {limit} requests per {window} seconds.",
                )

            # 记录请求
            self._requests[client_id].append(now)

        await self.app(scope, receive, send)
