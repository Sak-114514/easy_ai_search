"""
缓存管理端点
"""

from fastapi import APIRouter, HTTPException, Depends
from ..services.cache_service import CacheService
from ..middleware.auth import get_api_key, require_admin
from ..middleware.errors import build_internal_http_exception

router = APIRouter()
cache_service = CacheService()


@router.get("/stats")
async def get_cache_stats(api_key: str = Depends(get_api_key)):
    """获取缓存统计信息"""
    try:
        return cache_service.get_stats()
    except Exception as e:
        raise build_internal_http_exception("Get cache stats", e)


@router.get("/entries")
async def list_cache_entries(api_key: str = Depends(require_admin)):
    """查询缓存条目"""
    try:
        # 当前缓存模块仅暴露统计信息，先返回可用元信息避免接口空实现
        stats = cache_service.get_stats()
        return {"entries": [], "total": stats.get("total", 0), "stats": stats}
    except Exception as e:
        raise build_internal_http_exception("List cache entries", e)


@router.delete("/")
async def clear_cache(api_key: str = Depends(require_admin)):
    """清空缓存"""
    try:
        cache_service.clear_cache()
        return {"success": True, "message": "Cache cleared"}
    except Exception as e:
        raise build_internal_http_exception("Clear cache", e)
