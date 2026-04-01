"""
响应模型
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional


class SearchResponse(BaseModel):
    """搜索响应模型"""

    query: str
    results: List[Dict[str, Any]]
    total_time: float
    source: str


class AsyncSearchResponse(BaseModel):
    """异步搜索响应模型"""

    task_id: str
    status: str
    message: Optional[str] = None
    progress: Optional[int] = None
    result: Optional[SearchResponse] = None
    error: Optional[str] = None


class DocumentResponse(BaseModel):
    """文档响应模型"""

    id: str
    text: str
    url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class PaginationResponse(BaseModel):
    """分页响应模型"""

    total: int
    page: int
    size: int
    items: List[Any]


class ErrorResponse(BaseModel):
    """错误响应模型"""

    error: Dict[str, Any]
