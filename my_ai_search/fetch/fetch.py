import subprocess
import asyncio
import time
import ssl
from typing import Dict, Optional
import requests
from bs4 import BeautifulSoup

from my_ai_search.config import get_config
from my_ai_search.utils.logger import setup_logger
from my_ai_search.utils.exceptions import FetchException

logger = setup_logger("fetch")

_use_requests = False
_SSL_CONTEXT = ssl.create_default_context()

MIN_CONTENT_LENGTH = 200
SHELL_TITLE_PATTERNS = [
    "just a moment",
    "browser not supported",
    "scheduled maintenance",
    "access denied",
    "security verification",
    "please wait",
]
SHELL_TEXT_PATTERNS = [
    "just a moment",
    "browser not supported",
    "security verification required",
    "please enable cookies",
    "scheduled maintenance",
    "access denied",
    "verify you are human",
]
VIDEO_URL_HINTS = [
    "bilibili.com/video/",
    "haokan.baidu.com/v",
    "quanmin.baidu.com/sv",
    "/video/",
    "/shorts/",
]
LISTING_URL_HINTS = [
    "/tag/",
    "/category/",
    "/topics/",
    "/search",
    "/archives",
]
LISTING_TITLE_HINTS = [
    "search results",
    "相关文章",
    "相关推荐",
    "最新文章",
    "分类",
    "标签",
]


async def fetch_page(url: str, timeout: Optional[int] = None) -> Dict:
    """
    抓取单个页面（异步版本）

    策略：aiohttp(快) → 检查内容质量 → LightPanda(JS渲染) → requests(兜底)

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

    # Step 1: 先尝试 aiohttp 异步 HTTP 抓取
    try:
        http_result = await _fetch_with_aiohttp(url, actual_timeout)
        if http_result["success"] and _is_content_sufficient(http_result["html"]):
            logger.info(f"HTTP fetch sufficient for {url}, skipping LightPanda")
            return http_result
        if http_result["success"] and _should_skip_browser_fallback(
            url=url,
            html=http_result.get("html", ""),
            title=http_result.get("title", ""),
        ):
            logger.info(f"Detected shell/video page for {url}, skipping browser fallback")
            return http_result
        elif http_result["success"]:
            logger.info(
                f"HTTP content insufficient for {url} ({len(http_result['html'])} chars), trying LightPanda"
            )
    except Exception as e:
        logger.warning(f"aiohttp failed for {url}: {e}")

    # Step 2: HTTP 内容不足，尝试 LightPanda（支持 JS 渲染）
    try:
        result = await _fetch_with_lightpanda_cli(url, actual_timeout)
        if result["success"]:
            if _should_skip_requests_fallback(
                url=url,
                html=result.get("html", ""),
                title=result.get("title", ""),
            ):
                logger.info(f"Detected shell/video page after LightPanda for {url}, skipping requests fallback")
            return result
        logger.warning(f"LightPanda returned failure for {url}: {result.get('error')}")
        if _should_skip_requests_fallback(
            url=url,
            html=result.get("html", ""),
            title=result.get("title", ""),
            error=result.get("error"),
        ):
            return result
    except Exception as e:
        logger.error(f"LightPanda CLI failed for {url}: {e}")

    # Step 3: 最终回退到 requests
    logger.info(f"Falling back to requests for {url}")
    return _fetch_with_requests(url, actual_timeout)


async def _fetch_with_aiohttp(url: str, timeout: int) -> Dict:
    """
    使用 aiohttp 异步 HTTP 抓取（快速，不支持 JS 渲染）

    Args:
        url: 目标URL
        timeout: 超时时间（秒）

    Returns:
        页面数据字典
    """
    start_time = time.time()

    try:
        import aiohttp

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(
            timeout=timeout_obj, headers=headers
        ) as session:
            async with session.get(url, ssl=_SSL_CONTEXT) as response:
                # 先读 bytes，再智能检测编码
                raw = await response.read()
                # 优先用 Content-Type 中的 charset
                content_type = response.headers.get("Content-Type", "")
                encoding = response.charset
                if not encoding or encoding.lower() in ("iso-8859-1",):
                    # 尝试从 HTML meta charset 检测
                    head = raw[:2048].decode("ascii", errors="ignore").lower()
                    for pattern in [
                        'charset="', "charset=", 'encoding="', "encoding=",
                    ]:
                        pos = head.find(pattern)
                        if pos != -1:
                            start_pos = pos + len(pattern)
                            end_pos = start_pos
                            while end_pos < len(head) and head[end_pos] not in ('"', "'", ';', ' ', '>'):
                                end_pos += 1
                            detected = head[start_pos:end_pos].strip()
                            if detected:
                                encoding = detected
                                break
                if not encoding:
                    encoding = "utf-8"
                try:
                    html = raw.decode(encoding, errors="replace")
                except (UnicodeDecodeError, LookupError):
                    html = raw.decode("utf-8", errors="replace")

                if response.status != 200:
                    duration = time.time() - start_time
                    return {
                        "url": url,
                        "html": "",
                        "title": "",
                        "success": False,
                        "error": f"HTTP {response.status}",
                        "duration": duration,
                    }

                soup = BeautifulSoup(html, "html.parser")
                title = soup.title.string if soup.title else ""

                duration = time.time() - start_time
                logger.info(
                    f"Successfully fetched with aiohttp: {url}, title: {title[:50]}"
                )

                return {
                    "url": url,
                    "html": html,
                    "title": title,
                    "success": True,
                    "error": None,
                    "duration": duration,
                }

    except asyncio.TimeoutError:
        duration = time.time() - start_time
        logger.warning(f"aiohttp timeout for {url}")
        return {
            "url": url,
            "html": "",
            "title": "",
            "success": False,
            "error": "Timeout",
            "duration": duration,
        }
    except ImportError:
        logger.warning("aiohttp not available")
        return {
            "url": url,
            "html": "",
            "title": "",
            "success": False,
            "error": "aiohttp not installed",
            "duration": 0,
        }
    except Exception as e:
        duration = time.time() - start_time
        logger.warning(f"aiohttp failed for {url}: {e}")
        return {
            "url": url,
            "html": "",
            "title": "",
            "success": False,
            "error": str(e),
            "duration": duration,
        }


def _is_content_sufficient(html: str) -> bool:
    """
    检查 HTTP 获取的内容是否足够丰富

    Args:
        html: 原始HTML

    Returns:
        True if 内容质量足够（不需要 LightPanda 渲染）
    """
    if not html or not html.strip():
        return False

    try:
        soup = BeautifulSoup(html, "lxml")

        for tag in soup.find_all(
            [
                "script",
                "style",
                "nav",
                "footer",
                "header",
                "aside",
                "iframe",
                "noscript",
                "svg",
            ]
        ):
            tag.decompose()

        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                "div",
                class_=lambda x: x and ("content" in x.lower() or "post" in x.lower()),
            )
            or soup.body
        )

        if not main_content:
            return len(html) > 1000

        text = main_content.get_text(separator=" ", strip=True)
        return len(text) >= MIN_CONTENT_LENGTH

    except Exception:
        return len(html) > 1000


def _extract_preview_text(html: str) -> str:
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "lxml")
        return soup.get_text(separator=" ", strip=True)[:500].lower()
    except Exception:
        return html[:500].lower()


def _looks_like_shell_page(title: str, html: str) -> bool:
    lowered_title = (title or "").strip().lower()
    preview = _extract_preview_text(html)
    if any(pattern in lowered_title for pattern in SHELL_TITLE_PATTERNS):
        return True
    return any(pattern in preview for pattern in SHELL_TEXT_PATTERNS)


def _looks_like_video_page(url: str, title: str, html: str) -> bool:
    lowered_url = (url or "").lower()
    if any(hint in lowered_url for hint in VIDEO_URL_HINTS):
        preview = _extract_preview_text(html)
        video_signals = ["播放", "视频", "弹幕", "watch later", "up主", "订阅"]
        if any(signal in preview for signal in video_signals) or len(preview) < MIN_CONTENT_LENGTH:
            return True
    return False


def _looks_like_listing_or_sparse_page(url: str, title: str, html: str) -> bool:
    lowered_url = (url or "").lower()
    lowered_title = (title or "").lower()
    if any(hint in lowered_url for hint in LISTING_URL_HINTS):
        return True
    if any(hint in lowered_title for hint in LISTING_TITLE_HINTS):
        return True
    preview = _extract_preview_text(html)
    if len(preview) < MIN_CONTENT_LENGTH // 2:
        return True
    return False


def _should_skip_browser_fallback(url: str, html: str, title: str) -> bool:
    return (
        _looks_like_shell_page(title, html)
        or _looks_like_video_page(url, title, html)
        or _looks_like_listing_or_sparse_page(url, title, html)
    )


def _should_skip_requests_fallback(
    url: str, html: str, title: str, error: Optional[str] = None
) -> bool:
    lowered_error = (error or "").lower()
    if (
        _looks_like_shell_page(title, html)
        or _looks_like_video_page(url, title, html)
        or _looks_like_listing_or_sparse_page(url, title, html)
    ):
        return True
    return any(token in lowered_error for token in ["robotsblocked", "scheduled maintenance"])


async def _fetch_with_lightpanda_cli(url: str, timeout: int) -> Dict:
    """
    使用 lightpanda fetch 命令抓取页面（支持 JS 渲染）

    Args:
        url: 目标URL
        timeout: 超时时间（秒）

    Returns:
        页面数据字典
    """
    start_time = time.time()

    try:
        cmd = [
            "docker",
            "exec",
            "lightpanda",
            "lightpanda",
            "fetch",
            "--dump",
            "html",
            "--strip_mode",
            "js,ui",
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

        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout + 5, check=False
            ),
        )

        if result.returncode == 0:
            html = result.stdout

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
    使用 requests 抓取页面（最终兜底方案）

    Args:
        url: 目标URL
        timeout: 超时时间（秒）

    Returns:
        页面数据字典
    """
    start_time = time.time()

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        # 用 apparent_encoding 修正编码（解决 GB2312 等非 UTF-8 页面乱码）
        if response.apparent_encoding:
            response.encoding = response.apparent_encoding

        soup = BeautifulSoup(response.content, "html.parser")
        title = soup.title.string if soup.title else ""

        html = response.text

        duration = time.time() - start_time
        logger.info(f"Successfully fetched with requests: {url}, title: {title[:50]}")

        return {
            "url": url,
            "html": html,
            "title": title,
            "success": True,
            "error": None,
            "duration": duration,
        }

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
    return asyncio.run(fetch_page(url, timeout))


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
