"""
API Server 主入口
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_api_config
from .middleware.logging import LoggingMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.errors import setup_exception_handlers
from .endpoints import (
    health,
    search,
    algorithms,
    logs,
    cache,
    vector,
    mcp,
    tokens,
)
from .endpoints import config as config_endpoint

__version__ = "2.0.0"

config = get_api_config()

app = FastAPI(
    title="OpenSearch API Server",
    description="本地AI搜索系统API服务",
    version=__version__,
)
setup_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials="*" not in config.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(LoggingMiddleware)

app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(search.router, prefix="/api/v1/search", tags=["search"])
app.include_router(algorithms.router, prefix="/api/v1/algorithms", tags=["algorithms"])
app.include_router(config_endpoint.router, prefix="/api/v1/config", tags=["config"])
app.include_router(logs.router, prefix="/api/v1/logs", tags=["logs"])
app.include_router(cache.router, prefix="/api/v1/cache", tags=["cache"])
app.include_router(vector.router, prefix="/api/v1/vector", tags=["vector"])
app.include_router(tokens.router, prefix="/api/v1/tokens", tags=["tokens"])
# 兼容旧版 admin 路径，避免调用方和测试因路径迁移中断
app.include_router(algorithms.router, prefix="/api/v1/admin/algorithms", tags=["algorithms"])
app.include_router(config_endpoint.router, prefix="/api/v1/admin/config", tags=["config"])
app.include_router(logs.router, prefix="/api/v1/admin/logs", tags=["logs"])
app.include_router(cache.router, prefix="/api/v1/admin/cache", tags=["cache"])
app.include_router(vector.router, prefix="/api/v1/admin/vector", tags=["vector"])
app.include_router(tokens.router, prefix="/api/v1/admin/tokens", tags=["tokens"])
app.include_router(mcp.router, prefix="/mcp", tags=["mcp"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "OpenSearch API",
        "name": "OpenSearch API Server",
        "version": __version__,
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "OpenSearch API",
        "version": __version__,
        "protocols": ["MCP", "REST"],
    }


# 静态文件服务 — 管理控制台
_admin_dir = Path(__file__).resolve().parent.parent / "admin_ui"
if _admin_dir.is_dir():
    app.mount("/admin", StaticFiles(directory=str(_admin_dir), html=True), name="admin")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api_server.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level=config.log_level.lower(),
    )
