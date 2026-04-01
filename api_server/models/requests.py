"""
请求模型
"""

from pydantic import BaseModel, Field
from typing import Optional


class SearchRequest(BaseModel):
    """搜索请求模型"""

    query: str = Field(..., description="搜索查询")
    max_results: Optional[int] = Field(5, ge=1, le=20, description="最大结果数")
    use_cache: Optional[bool] = Field(True, description="是否使用缓存")
    skip_local: Optional[bool] = Field(False, description="是否跳过本地搜索")
    disable_deep_process: Optional[bool] = Field(
        False, description="是否禁用深度处理（摘要/质量过滤/去重）"
    )
    engines: Optional[str] = Field(None, description="指定搜索引擎，逗号分隔，如 'bing,baidu'")
    mode: Optional[str] = Field(
        "balanced",
        description="搜索模式：fast(更快)、balanced(默认平衡)、deep(更完整)",
        pattern="^(fast|balanced|deep)$",
    )
    preferred_domains: Optional[list[str]] = Field(
        None, description="优先域名列表，如 ['openai.com', 'redis.io']"
    )
    blocked_domains: Optional[list[str]] = Field(
        None, description="屏蔽域名列表，如 ['help.openai.com']"
    )
    domain_preference_mode: Optional[str] = Field(
        "prefer",
        description="域名偏好强度：prefer/strong_prefer/only",
        pattern="^(prefer|strong_prefer|only)$",
    )
    source_profile: Optional[str] = Field(
        "general",
        description="来源策略：general/official_news/social_realtime/official_plus_social/tech_community",
        pattern="^(general|official_news|social_realtime|official_plus_social|tech_community)$",
    )


class DocumentRequest(BaseModel):
    """文档请求模型"""

    text: str = Field(..., description="文档文本")
    url: Optional[str] = Field(None, description="文档 URL")
    metadata: Optional[dict] = Field(None, description="文档元数据")
