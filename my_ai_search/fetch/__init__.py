from .fetch import (
    close_browser,
    enable_lightpanda_mode,
    enable_requests_mode,
    fetch_page,
    fetch_page_sync,
)
from .fetch_concurrent import _calculate_stats, fetch_pages, fetch_pages_sync

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
