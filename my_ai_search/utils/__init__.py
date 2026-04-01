"""
工具模块
提供日志和异常处理功能
"""

from .exceptions import (
    AISearchException,
    ConfigException,
    SearchException,
    FetchException,
    ProcessException,
    VectorException,
    CacheException,
)

__all__ = [
    "setup_logger",
    "get_logger",
    "AISearchException",
    "ConfigException",
    "SearchException",
    "FetchException",
    "ProcessException",
    "VectorException",
    "CacheException",
]


def setup_logger(name: str = "app"):
    from .logger import setup_logger as _setup_logger

    return _setup_logger(name)


def get_logger(name: str = "app"):
    from .logger import get_logger as _get_logger

    return _get_logger(name)
