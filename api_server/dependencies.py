from functools import lru_cache

from .services.log_service import LogService
from .services.search_service import SearchService
from .services.token_service import TokenService


@lru_cache(maxsize=1)
def get_log_service() -> LogService:
    return LogService()


@lru_cache(maxsize=1)
def get_search_service() -> SearchService:
    return SearchService(log_service=get_log_service())


@lru_cache(maxsize=1)
def get_token_service() -> TokenService:
    return TokenService()
