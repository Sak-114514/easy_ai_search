"""统一导出 API app，避免 `api_server` 与 `api_server.main` 双入口分叉。"""

from .main import app

__all__ = ["app"]
