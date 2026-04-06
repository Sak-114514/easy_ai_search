import asyncio
import time

from my_ai_search.config import get_config
from my_ai_search.utils.exceptions import FetchException
from my_ai_search.utils.logger import setup_logger

from .fetch import fetch_page

logger = setup_logger("fetch_concurrent")


async def fetch_pages(urls: list[str], max_concurrent: int = None) -> list[dict]:
    """
    并发抓取多个页面（异步版本）

    Args:
        urls: URL列表
        max_concurrent: 最大并发数，None则使用配置默认值

    Returns:
        抓取结果列表：
        [
            {
                'url': str,
                'html': str,
                'title': str,
                'success': bool,
                'error': str,
                'duration': float  # 抓取耗时（秒）
            },
            ...
        ]
    """
    if not urls:
        logger.warning("Empty URL list")
        return []

    config = get_config()
    actual_max_concurrent = max_concurrent or config.lightpanda.max_concurrent

    logger.info(
        f"Starting concurrent fetch: {len(urls)} URLs, max_concurrent={actual_max_concurrent}"
    )

    start_time = time.time()
    results = []

    try:
        semaphore = asyncio.Semaphore(actual_max_concurrent)

        tasks = [_fetch_single(url, semaphore) for url in urls]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for url, result in zip(urls, results, strict=False):
            if isinstance(result, Exception):
                processed_results.append(
                    {
                        "url": url,
                        "html": "",
                        "title": "",
                        "success": False,
                        "error": str(result),
                        "duration": 0,
                    }
                )
            else:
                if "duration" not in result:
                    result["duration"] = getattr(result, "duration", 0)
                processed_results.append(result)

        total_time = time.time() - start_time
        logger.info(
            f"Concurrent fetch completed: {len(processed_results)} pages in {total_time:.2f}s"
        )

        stats = _calculate_stats(processed_results)
        logger.info(f"Stats: {stats}")

        return processed_results

    except Exception as e:
        logger.error(f"Concurrent fetch failed: {e}")
        raise FetchException("", f"Concurrent fetch error: {e}") from e


async def _fetch_single(url: str, semaphore: asyncio.Semaphore) -> dict:
    """
    抓取单个页面（带信号量控制）

    Args:
        url: 目标URL
        semaphore: 并发控制信号量

    Returns:
        抓取结果字典
    """
    async with semaphore:
        start_time = time.time()
        try:
            result = await fetch_page(url)
            if "duration" not in result:
                result["duration"] = time.time() - start_time
            return result
        except Exception as e:
            return {
                "url": url,
                "html": "",
                "title": "",
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time,
            }


def fetch_pages_sync(urls: list[str], max_concurrent: int = None) -> list[dict]:
    """
    同步包装函数，便于调用

    Args:
        urls: URL列表
        max_concurrent: 最大并发数

    Returns:
        抓取结果列表
    """
    return asyncio.run(fetch_pages(urls, max_concurrent))


def _calculate_stats(results: list[dict]) -> dict:
    """
    计算抓取统计信息

    Args:
        results: 抓取结果列表

    Returns:
        统计信息：
        {
            'total': int,           # 总数
            'success': int,         # 成功数
            'failed': int,          # 失败数
            'success_rate': float,   # 成功率
            'total_time': float,    # 总耗时
            'avg_time': float       # 平均耗时
        }
    """
    total = len(results)
    success = sum(1 for r in results if r["success"])
    failed = total - success
    total_time = sum(r.get("duration", 0) for r in results)
    avg_time = total_time / total if total > 0 else 0
    success_rate = success / total if total > 0 else 0

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "success_rate": success_rate,
        "total_time": total_time,
        "avg_time": avg_time,
    }
