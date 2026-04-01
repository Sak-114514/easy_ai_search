"""
验证器
"""

from pydantic import validator
from typing import Optional


def validate_url(url: str) -> bool:
    """
    验证 URL 格式

    Args:
        url: URL 字符串

    Returns:
        是否有效
    """
    return url.startswith(("http://", "https://"))


def validate_api_key(api_key: str) -> bool:
    """
    验证 API Key 格式

    Args:
        api_key: API Key 字符串

    Returns:
        是否有效
    """
    return len(api_key) >= 16
