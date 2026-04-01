"""
日志管理端点
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional
from datetime import datetime
from ..services.log_service import LogService
from ..middleware.auth import require_admin
from ..middleware.errors import build_internal_http_exception

router = APIRouter()
log_service = LogService()


@router.get("/search")
async def list_search_logs(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    query: Optional[str] = None,
    token_name: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    api_key: str = Depends(require_admin),
):
    """查询搜索日志"""
    try:
        return log_service.list_search_logs(start_time, end_time, query, token_name, page, size)
    except Exception as e:
        raise build_internal_http_exception("List search logs", e)


@router.get("/api")
async def list_api_logs(
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    endpoint: Optional[str] = None,
    token_name: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    api_key: str = Depends(require_admin),
):
    """查询 API 日志"""
    try:
        return log_service.list_api_logs(start_time, end_time, endpoint, token_name, page, size)
    except Exception as e:
        raise build_internal_http_exception("List API logs", e)


@router.get("/stats")
async def get_log_stats(api_key: str = Depends(require_admin)):
    """获取日志统计"""
    try:
        return log_service.get_stats()
    except Exception as e:
        raise build_internal_http_exception("Get log stats", e)
