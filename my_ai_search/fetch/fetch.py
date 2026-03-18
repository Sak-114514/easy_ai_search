import subprocess
import asyncio
from typing import Dict, Optional
import sys
import os
import requests
from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_config
from utils.logger import setup_logger
from utils.exceptions import FetchException

logger = setup_logger("fetch")

_use_requests = False


async def fetch_page(url: str, timeout: Optional[int] = None) -> Dict:
    """
    抓取单个页面（异步版本）

    Args:
        url: 目标URL
        timeout: 超时时间（秒），None则使用配置默认值

    Returns:
        页面数据字典：
        {
            'url': str,        # 原始URL
            'html': str,       # 完整HTML
            'title': str,      # 页面标题
            'success': bool,   # 是否成功
            'error': str       # 错误信息（失败时）
        }
    """
    if not url or not url.strip():
        raise FetchException(url, "URL cannot be empty")

    config = get_config()
    actual_timeout = timeout or int(config.lightpanda.timeout)

    logger.info(f"Fetching page: {url}")

    if _use_requests:
        return _fetch_with_requests(url, actual_timeout)

    try:
        result = await _fetch_with_lightpanda_cli(url, actual_timeout)
        return result
    except Exception as e:
        logger.error(f"LightPanda CLI failed for {url}: {e}")
        logger.info("Falling back to requests...")
        return _fetch_with_requests(url, actual_timeout)


async def _fetch_with_lightpanda_cli(url: str, timeout: int) -> Dict:
    """
    使用 lightpanda fetch 命令抓取页面（推荐方式）

    Args:
        url: 目标URL
        timeout: 超时时间（秒）

    Returns:
        页面数据字典
    """
    import time

    start_time = time.time()

    try:
        # 构建命令（通过 Docker 容器执行）
        cmd = [
            "docker",
            "exec",
            "lightpanda",
            "lightpanda",
            "fetch",
            "--dump",
            "html",
            "--strip_mode",
            "js,ui",  # 去除 JS 和 UI 元素
            "--obey_robots",
            "--http_timeout",
            str(timeout * 1000),
            "--http_connect_timeout",
            str(timeout * 1000),
            "--http_max_concurrent",
            str(get_config().lightpanda.max_concurrent),
            "--log_format",
            "logfmt",
            "--log_level",
            "error",
            url,
        ]

        logger.debug(f"Running command: {' '.join(cmd)}")

        # 执行命令
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout + 5, check=False
        )

        if result.returncode == 0:
            html = result.stdout

            # 提取标题
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.string if soup.title else ""

            duration = time.time() - start_time
            logger.info(
                f"Successfully fetched with LightPanda: {url}, title: {title[:50]}"
            )

            return {
                "url": url,
                "html": html,
                "title": title,
                "success": True,
                "error": None,
                "duration": duration,
            }
        else:
            error_msg = result.stderr.strip() or "Unknown error"
            duration = time.time() - start_time
            logger.error(f"LightPanda CLI error for {url}: {error_msg}")

            return {
                "url": url,
                "html": "",
                "title": "",
                "success": False,
                "error": error_msg,
                "duration": duration,
            }

    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        logger.error(f"LightPanda CLI timeout for {url}")
        return {
            "url": url,
            "html": "",
            "title": "",
            "success": False,
            "error": "Timeout",
            "duration": duration,
        }
    except FileNotFoundError:
        logger.error("lightpanda command not found")
        raise FetchException(
            url,
            "lightpanda command not found. Please install LightPanda or use requests mode",
        )
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Unexpected error with LightPanda CLI for {url}: {e}")
        return {
            "url": url,
            "html": "",
            "title": "",
            "success": False,
            "error": str(e),
            "duration": duration,
        }


def _fetch_with_requests(url: str, timeout: int) -> Dict:
    """
    使用 requests 抓取页面（备用方案）

    Args:
        url: 目标URL
        timeout: 超时时间（秒）

    Returns:
        页面数据字典
    """
    import time

    start_time = time.time()

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.title.string if soup.title else ""

        html = response.text

        duration = time.time() - start_time
        logger.info(f"Successfully fetched with requests: {url}, title: {title[:50]}")

        result = {
            "url": url,
            "html": html,
            "title": title,
            "success": True,
            "error": None,
            "duration": duration,
        }
        return result

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Failed to fetch {url} with requests: {e}")
        return {
            "url": url,
            "html": "",
            "title": "",
            "success": False,
            "error": str(e),
            "duration": duration,
        }


def close_browser():
    """
    关闭浏览器连接（不适用，保留为兼容性）
    """
    pass


def fetch_page_sync(url: str, timeout: Optional[int] = None) -> Dict:
    """
    同步包装函数，便于调用

    Args:
        url: 目标URL
        timeout: 超时时间（秒）

    Returns:
        页面数据字典
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fetch_page(url, timeout))


def enable_requests_mode():
    """
    启用 requests 模式（不使用 LightPanda）
    """
    global _use_requests
    _use_requests = True
    logger.info("Requests mode enabled")


def enable_lightpanda_mode():
    """
    启用 LightPanda CLI 模式（推荐）
    """
    global _use_requests
    _use_requests = False
    logger.info("LightPanda CLI mode enabled")
