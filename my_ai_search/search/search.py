import requests
from typing import List, Dict, Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config
from utils.logger import setup_logger
from utils.exceptions import SearchException

logger = setup_logger("search")


def search(query: str, max_results: Optional[int] = None) -> List[Dict]:
    """
    执行搜索查询

    Args:
        query: 搜索关键词
        max_results: 最大结果数，None则使用配置默认值

    Returns:
        搜索结果列表，每个结果包含：
        {
            'title': str,
            'url': str,
            'content': str,
            'score': float
        }

    Raises:
        SearchException: 搜索失败时抛出
    """
    if not query or not query.strip():
        raise SearchException("Query cannot be empty")

    config = get_config()
    actual_max_results = max_results or config.searxng.max_results

    logger.info(f"Starting search: query='{query}', max_results={actual_max_results}")

    try:
        params = {"q": query, "format": "json", "language": "auto", "pageno": 1}

        response_data = _retry_search(query, params, config.searxng.timeout)
        results = _parse_results(response_data, actual_max_results)

        logger.info(f"Search completed: {len(results)} results found")
        return results

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise SearchException(f"Search operation failed: {e}")


def _call_searxng_api(query: str, params: dict) -> dict:
    """
    调用SearXNG API

    Args:
        query: 搜索查询
        params: API参数

    Returns:
        API响应JSON

    Raises:
        SearchException: API调用失败
    """
    config = get_config()
    api_url = config.searxng.api_url

    try:
        logger.debug(f"Calling SearXNG API: {api_url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        proxies = {"http": None, "https": None, "socks": None}
        response = requests.post(
            api_url,
            data=params,
            headers=headers,
            proxies=proxies,
            timeout=config.searxng.timeout,
        )
        response.raise_for_status()

        data = response.json()
        return data

    except requests.exceptions.Timeout:
        raise SearchException("SearXNG API timeout")
    except requests.exceptions.ConnectionError:
        raise SearchException("Failed to connect to SearXNG")
    except requests.exceptions.HTTPError as e:
        raise SearchException(f"SearXNG API returned HTTP {e.response.status_code}")
    except Exception as e:
        raise SearchException(f"Unexpected error: {e}")


def _parse_results(response: dict, max_results: int) -> List[Dict]:
    """
    解析SearXNG响应

    Args:
        response: API响应
        max_results: 最大结果数

    Returns:
        标准化结果列表
    """
    results_list = response.get("results", [])

    parsed_results = []
    for item in results_list[:max_results]:
        result = {
            "title": item.get("title", "").strip(),
            "url": item.get("url", "").strip(),
            "content": item.get("content", "").strip(),
            "score": item.get("score", 0.0),
        }

        if not result["url"]:
            logger.warning(f"Skipping result with empty URL: {result['title']}")
            continue

        parsed_results.append(result)

    return parsed_results


def _retry_search(
    query: str, params: dict, timeout: float, max_retries: int = 2
) -> dict:
    """
    带重试的搜索

    Args:
        query: 搜索查询
        params: API参数
        timeout: 超时时间
        max_retries: 最大重试次数

    Returns:
        API响应

    Raises:
        SearchException: 重试后仍失败
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"Search attempt {attempt + 1}/{max_retries + 1}")
            return _call_searxng_api(query, params)

        except SearchException as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"Search attempt {attempt + 1} failed, retrying... Error: {e}"
                )
                continue
            else:
                logger.error(f"All search attempts failed")
                break

    raise last_exception
