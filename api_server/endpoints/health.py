"""
健康检查端点
"""

from fastapi import APIRouter
from ..services.search_service import SearchService

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查"""
    # TODO: 实现依赖服务检查
    return {"status": "healthy", "service": "OpenSearch API", "version": "2.0.0"}


@router.get("/stats")
async def get_stats():
    """获取服务统计"""
    # TODO: 实现统计
    return {"total_searches": 0, "total_requests": 0}
