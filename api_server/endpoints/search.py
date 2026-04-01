"""
REST API 搜索端点

提供同步和异步搜索功能
"""

from fastapi import APIRouter, HTTPException, Depends, status, Request
from typing import Optional
from ..dependencies import get_search_service
from ..models.requests import SearchRequest
from ..models.responses import SearchResponse, AsyncSearchResponse
from ..services.search_service import SearchService
from ..middleware.auth import get_api_key
from ..middleware.errors import build_internal_http_exception

router = APIRouter()
search_service = get_search_service()


def get_search_service_dependency() -> SearchService:
    return search_service


@router.post("", response_model=SearchResponse)
async def search(
    request: Request,
    payload: SearchRequest,
    api_key: str = Depends(get_api_key),
    search_service: SearchService = Depends(get_search_service_dependency),
):
    """
    执行同步搜索

    Args:
        request: 搜索请求参数
        api_key: API密钥

    Returns:
        搜索结果

    Raises:
        HTTPException: 搜索失败时抛出异常
    """
    # 先在端点层验证查询
    if not payload.query or not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty"
        )

    try:
        result = await search_service.search(
            query=payload.query,
            max_results=payload.max_results,
            use_cache=payload.use_cache,
            skip_local=payload.skip_local,
            disable_deep_process=payload.disable_deep_process,
            client_type="rest",
            engines=payload.engines,
            mode=payload.mode or "balanced",
            tool_context={
                "preferred_domains": payload.preferred_domains or [],
                "blocked_domains": payload.blocked_domains or [],
                "domain_preference_mode": payload.domain_preference_mode or "prefer",
                "source_profile": payload.source_profile or "general",
            },
            token_name=(getattr(request.state, "auth_context", {}) or {}).get("name"),
        )

        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise build_internal_http_exception("Search", e)


@router.post("/async", response_model=AsyncSearchResponse)
async def search_async(
    payload: SearchRequest,
    api_key: str = Depends(get_api_key),
    search_service: SearchService = Depends(get_search_service_dependency),
):
    """
    提交异步搜索任务

    Args:
        request: 搜索请求参数
        api_key: API密钥

    Returns:
        包含任务ID的响应
    """
    # 先在端点层验证查询
    if not payload.query or not payload.query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Query cannot be empty"
        )

    try:
        task_id = await search_service.submit_async_search(
            query=payload.query,
            max_results=payload.max_results,
            use_cache=payload.use_cache,
            skip_local=payload.skip_local,
            disable_deep_process=payload.disable_deep_process,
            mode=payload.mode or "balanced",
        )

        return {"task_id": task_id, "status": "pending", "progress": 0}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise build_internal_http_exception("Submit async search", e)


@router.get("/async/{task_id}", response_model=AsyncSearchResponse)
async def get_async_search_status(
    task_id: str,
    api_key: str = Depends(get_api_key),
    search_service: SearchService = Depends(get_search_service_dependency),
):
    """
    查询异步搜索任务状态

    Args:
        task_id: 任务ID
        api_key: API密钥

    Returns:
        任务状态信息

    Raises:
        HTTPException: 任务不存在时抛出异常
    """
    try:
        status = await search_service.get_async_search_status(task_id)
        return status
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise build_internal_http_exception("Get async search status", e)
