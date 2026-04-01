"""
数据模型
"""

from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class SearchLog(BaseModel):
    """搜索日志模型"""

    id: int
    timestamp: datetime
    query: str
    max_results: int
    source: str
    total_time: float
    results_count: int
    client_type: str
    ip: Optional[str] = None


class APILog(BaseModel):
    """API 日志模型"""

    id: int
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    response_time: float
    client_type: str
    ip: Optional[str] = None


class Config(BaseModel):
    """配置模型"""

    key: str
    value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None


class AlgorithmParam(BaseModel):
    """算法参数模型"""

    id: int
    module: str
    param_name: str
    param_value: str
    description: Optional[str] = None
    updated_at: Optional[datetime] = None
