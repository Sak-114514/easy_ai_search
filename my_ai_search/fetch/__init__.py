from .fetch import (
    fetch_page,
    fetch_page_sync,
    close_browser,
    enable_requests_mode,
    enable_lightpanda_mode,
)
from .fetch_concurrent import fetch_pages, fetch_pages_sync, _calculate_stats

__all__ = [
    "fetch_page",
    "fetch_page_sync",
    "close_browser",
    "enable_requests_mode",
    "enable_lightpanda_mode",
    "fetch_pages",
    "fetch_pages_sync",
    "_calculate_stats",
]
