import asyncio
import contextlib
import json
import ssl
import time
from itertools import count
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from my_ai_search.config import get_config
from my_ai_search.utils.exceptions import FetchException
from my_ai_search.utils.logger import setup_logger

logger = setup_logger("fetch")

_use_requests = False
_SSL_CONTEXT = ssl.create_default_context()
_BROWSER_POOL = None
_BROWSER_POOL_GUARD = None

MIN_CONTENT_LENGTH = 200
MAX_PREVIEW_LENGTH = 500
MAX_MAIN_TEXT_LENGTH = 12000
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


class LightPandaSessionPool:
    """Small CDP session pool that reuses one browser websocket and creates per-request targets."""

    def __init__(self, cdp_url: str, timeout: float, max_concurrent: int):
        self._configured_cdp_url = cdp_url
        self._timeout = max(float(timeout), 1.0)
        self._max_concurrent = max(int(max_concurrent), 1)
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._connect_lock = asyncio.Lock()
        self._send_lock = asyncio.Lock()
        self._target_lock = asyncio.Lock()
        self._closed = False
        self._command_ids = count(1)
        self._client_session = None
        self._ws = None
        self._reader_task = None
        self._pending: dict[int, asyncio.Future] = {}
        self._session_events: dict[str, asyncio.Queue] = {}

    async def fetch_html(self, url: str, timeout: int) -> dict[str, object]:
        async with self._semaphore:
            start_time = time.time()
            target_id = None
            session_id = None
            try:
                await self._ensure_connection()
                async with self._target_lock:
                    target_id = await self._create_target(url)
                    session_id = await self._attach_target(target_id)
                    await self._enable_page(session_id)
                    await self._navigate(session_id, url, timeout)
                    title = await self._evaluate_string(session_id, "document.title || ''")
                    html = await self._evaluate_string(
                        session_id,
                        "document.documentElement ? document.documentElement.outerHTML : ''",
                    )
                duration = time.time() - start_time
                logger.info(
                    "Successfully fetched with LightPanda CDP: %s, title: %s",
                    url,
                    title[:50],
                )
                return _build_fetch_result(
                    url=url,
                    html=html,
                    title=title,
                    success=True,
                    error=None,
                    duration=duration,
                )
            except Exception as exc:
                duration = time.time() - start_time
                logger.error("LightPanda CDP failed for %s: %s", url, exc)
                return {
                    "url": url,
                    "html": "",
                    "title": "",
                    "success": False,
                    "error": str(exc),
                    "duration": duration,
                }
            finally:
                if target_id:
                    await self._safe_close_target(target_id)
                if session_id:
                    self._session_events.pop(session_id, None)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        pending = list(self._pending.values())
        self._pending.clear()
        for future in pending:
            if not future.done():
                future.set_exception(asyncio.CancelledError())

        if self._reader_task:
            self._reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._reader_task
            self._reader_task = None

        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None

        if self._client_session is not None:
            with contextlib.suppress(Exception):
                await self._client_session.close()
            self._client_session = None

        self._session_events.clear()

    async def _ensure_connection(self) -> None:
        if self._ws is not None and not self._ws.closed:
            return

        async with self._connect_lock:
            if self._ws is not None and not self._ws.closed:
                return

            if self._client_session is None or self._client_session.closed:
                import aiohttp

                timeout = aiohttp.ClientTimeout(total=self._timeout + 5)
                self._client_session = aiohttp.ClientSession(timeout=timeout)

            resolved_cdp_url = await self._resolve_cdp_url()
            ssl_context = _SSL_CONTEXT if resolved_cdp_url.startswith("wss://") else None
            self._ws = await self._client_session.ws_connect(
                resolved_cdp_url,
                ssl=ssl_context,
                heartbeat=30,
                max_msg_size=16 * 1024 * 1024,
            )
            self._closed = False
            self._reader_task = asyncio.create_task(self._reader_loop())

    async def _resolve_cdp_url(self) -> str:
        parsed = urlparse(self._configured_cdp_url)
        if parsed.scheme not in {"ws", "wss"}:
            raise FetchException("", f"Unsupported CDP URL scheme: {self._configured_cdp_url}")
        if parsed.path not in {"", "/"}:
            return self._configured_cdp_url

        version_url = urlunparse(
            parsed._replace(
                scheme="https" if parsed.scheme == "wss" else "http",
                path="/json/version",
                params="",
                query="",
                fragment="",
            )
        )

        try:
            async with self._client_session.get(version_url, ssl=_SSL_CONTEXT) as response:
                if response.status == 200:
                    payload = await response.json()
                    candidate = payload.get("webSocketDebuggerUrl")
                    if candidate:
                        return str(candidate)
        except Exception as exc:
            logger.debug("Failed to resolve browser websocket via %s: %s", version_url, exc)

        return self._configured_cdp_url

    async def _reader_loop(self) -> None:
        import aiohttp

        try:
            async for message in self._ws:
                if message.type != aiohttp.WSMsgType.TEXT:
                    continue
                try:
                    payload = json.loads(message.data)
                except json.JSONDecodeError:
                    logger.debug("Ignoring non-JSON CDP payload")
                    continue

                response_id = payload.get("id")
                if response_id is not None:
                    future = self._pending.pop(int(response_id), None)
                    if future is not None and not future.done():
                        future.set_result(payload)
                    continue

                session_id = payload.get("sessionId")
                if session_id:
                    queue = self._session_events.setdefault(session_id, asyncio.Queue())
                    queue.put_nowait(payload)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("LightPanda reader loop stopped: %s", exc)
        finally:
            error = FetchException("", "LightPanda websocket disconnected")
            pending = list(self._pending.values())
            self._pending.clear()
            for future in pending:
                if not future.done():
                    future.set_exception(error)

    async def _send_command(
        self,
        method: str,
        params: dict[str, object] | None = None,
        *,
        session_id: str | None = None,
        timeout: float | None = None,
    ) -> dict[str, object]:
        await self._ensure_connection()
        command_id = next(self._command_ids)
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self._pending[command_id] = future
        payload: dict[str, object] = {"id": command_id, "method": method, "params": params or {}}
        if session_id:
            payload["sessionId"] = session_id

        async with self._send_lock:
            await self._ws.send_json(payload)

        response = await asyncio.wait_for(future, timeout=timeout or self._timeout + 2)
        if "error" in response:
            message = response["error"].get("message") or str(response["error"])
            raise FetchException("", f"CDP command {method} failed: {message}")
        return response.get("result", {})

    async def _wait_for_event(self, session_id: str, method: str, timeout: float) -> dict[str, object]:
        queue = self._session_events.setdefault(session_id, asyncio.Queue())
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Timed out waiting for {method}")
            payload = await asyncio.wait_for(queue.get(), timeout=remaining)
            if payload.get("method") == method:
                return payload.get("params", {})

    async def _create_target(self, url: str) -> str:
        result = await self._send_command("Target.createTarget", {"url": "about:blank"})
        target_id = result.get("targetId")
        if not target_id:
            raise FetchException(url, "LightPanda did not return targetId")
        return str(target_id)

    async def _attach_target(self, target_id: str) -> str:
        result = await self._send_command(
            "Target.attachToTarget",
            {"targetId": target_id, "flatten": True},
        )
        session_id = result.get("sessionId")
        if not session_id:
            raise FetchException("", f"Failed to attach target {target_id}")
        self._session_events.setdefault(str(session_id), asyncio.Queue())
        return str(session_id)

    async def _enable_page(self, session_id: str) -> None:
        await self._send_command("Page.enable", session_id=session_id)
        await self._send_command("Runtime.enable", session_id=session_id)

    async def _navigate(self, session_id: str, url: str, timeout: int) -> None:
        result = await self._send_command(
            "Page.navigate",
            {"url": url},
            session_id=session_id,
            timeout=timeout + 2,
        )
        error_text = result.get("errorText")
        if error_text:
            raise FetchException(url, error_text)

        try:
            await self._wait_for_event(session_id, "Page.loadEventFired", timeout=timeout)
        except TimeoutError:
            logger.debug("Page.loadEventFired timed out for %s; continuing with snapshot", url)

    async def _evaluate_string(self, session_id: str, expression: str) -> str:
        result = await self._send_command(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
            session_id=session_id,
        )
        remote = result.get("result", {})
        value = remote.get("value")
        return "" if value is None else str(value)

    async def _safe_close_target(self, target_id: str) -> None:
        with contextlib.suppress(Exception):
            await self._send_command("Target.closeTarget", {"targetId": target_id}, timeout=2)


async def fetch_page(url: str, timeout: int | None = None) -> dict[str, object]:
    """
    抓取单个页面（异步版本）

    策略：aiohttp(快) → 检查内容质量 → LightPanda(JS渲染) → requests(兜底)
    """
    if not url or not url.strip():
        raise FetchException(url, "URL cannot be empty")

    config = get_config()
    actual_timeout = timeout or int(config.lightpanda.timeout)

    logger.info("Fetching page: %s", url)

    if _use_requests:
        return _ensure_fetch_result_fields(_fetch_with_requests(url, actual_timeout))

    try:
        http_result = await _fetch_with_aiohttp(url, actual_timeout)
        http_result = _ensure_fetch_result_fields(http_result)
        if http_result["success"] and _is_content_sufficient(http_result["html"]):
            logger.info("HTTP fetch sufficient for %s, skipping LightPanda", url)
            return http_result
        if http_result["success"] and _should_skip_browser_fallback(
            url=url,
            html=http_result.get("html", ""),
            title=http_result.get("title", ""),
        ):
            logger.info("Detected shell/video page for %s, skipping browser fallback", url)
            return http_result
        if http_result["success"]:
            logger.info(
                "HTTP content insufficient for %s (%s chars), trying LightPanda",
                url,
                len(http_result["html"]),
            )
    except Exception as exc:
        logger.warning("aiohttp failed for %s: %s", url, exc)

    try:
        result = await _fetch_with_lightpanda(url, actual_timeout)
        result = _ensure_fetch_result_fields(result)
        if result["success"]:
            if _should_skip_requests_fallback(
                url=url,
                html=result.get("html", ""),
                title=result.get("title", ""),
            ):
                logger.info(
                    "Detected shell/video page after LightPanda for %s, skipping requests fallback",
                    url,
                )
            return result
        logger.warning("LightPanda returned failure for %s: %s", url, result.get("error"))
        if _should_skip_requests_fallback(
            url=url,
            html=result.get("html", ""),
            title=result.get("title", ""),
            error=result.get("error"),
        ):
            return result
    except Exception as exc:
        logger.error("LightPanda CDP failed for %s: %s", url, exc)

    logger.info("Falling back to requests for %s", url)
    return _ensure_fetch_result_fields(_fetch_with_requests(url, actual_timeout))


async def _fetch_with_aiohttp(url: str, timeout: int) -> dict[str, object]:
    start_time = time.time()

    try:
        import aiohttp

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        timeout_obj = aiohttp.ClientTimeout(total=timeout)
        async with aiohttp.ClientSession(
            timeout=timeout_obj,
            headers=headers,
        ) as session, session.get(url, ssl=_SSL_CONTEXT) as response:
                raw = await response.read()
                encoding = response.charset
                if not encoding or encoding.lower() in {"iso-8859-1"}:
                    head = raw[:2048].decode("ascii", errors="ignore").lower()
                    for pattern in ['charset="', "charset=", 'encoding="', "encoding="]:
                        pos = head.find(pattern)
                        if pos == -1:
                            continue
                        start_pos = pos + len(pattern)
                        end_pos = start_pos
                        while end_pos < len(head) and head[end_pos] not in {'"', "'", ';', ' ', '>'}:
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

                duration = time.time() - start_time
                if response.status != 200:
                    return {
                        "url": url,
                        "html": "",
                        "title": "",
                        "success": False,
                        "error": f"HTTP {response.status}",
                        "duration": duration,
                    }

                title = _extract_title(html)
                logger.info("Successfully fetched with aiohttp: %s, title: %s", url, title[:50])
                return _build_fetch_result(
                    url=url,
                    html=html,
                    title=title,
                    success=True,
                    error=None,
                    duration=duration,
                )
    except TimeoutError:
        duration = time.time() - start_time
        logger.warning("aiohttp timeout for %s", url)
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
    except Exception as exc:
        duration = time.time() - start_time
        logger.warning("aiohttp failed for %s: %s", url, exc)
        return {
            "url": url,
            "html": "",
            "title": "",
            "success": False,
            "error": str(exc),
            "duration": duration,
        }


def _is_content_sufficient(html: str) -> bool:
    if not html or not html.strip():
        return False

    try:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "svg"]):
            tag.decompose()

        main_content = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                "div",
                class_=lambda value: value and ("content" in value.lower() or "post" in value.lower()),
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
        return _extract_text_preview_from_soup(soup)
    except Exception:
        return html[:MAX_PREVIEW_LENGTH].lower()


def _extract_text_preview_from_soup(soup: BeautifulSoup) -> str:
    return soup.get_text(separator=" ", strip=True)[:MAX_PREVIEW_LENGTH].lower()


def _extract_title(html: str) -> str:
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        return soup.title.string.strip() if soup.title and soup.title.string else ""
    except Exception:
        return ""


def _extract_fetch_artifacts(html: str, title: str) -> dict[str, str]:
    if not html:
        return {}

    try:
        soup = BeautifulSoup(html, "lxml")
        parsed_title = title or (soup.title.string.strip() if soup.title and soup.title.string else "")
        preview_text = _extract_text_preview_from_soup(soup)
        main_node = (
            soup.find("article")
            or soup.find("main")
            or soup.find(
                "div",
                class_=lambda value: value
                and (
                    "content" in value.lower()
                    or "article" in value.lower()
                    or "post" in value.lower()
                ),
            )
            or soup.body
        )
        main_text = ""
        if main_node is not None:
            main_text = " ".join(main_node.get_text(separator=" ", strip=True).split())
        if not main_text:
            main_text = " ".join(preview_text.split())
        return {
            "parsed_title": parsed_title,
            "preview_text": preview_text,
            "main_text_candidate": main_text[:MAX_MAIN_TEXT_LENGTH],
        }
    except Exception:
        preview_text = html[:MAX_PREVIEW_LENGTH].lower()
        return {
            "parsed_title": title or "",
            "preview_text": preview_text,
            "main_text_candidate": html[:MAX_MAIN_TEXT_LENGTH],
        }


def _build_fetch_result(
    *,
    url: str,
    html: str,
    title: str,
    success: bool,
    error: str | None,
    duration: float,
) -> dict[str, object]:
    result: dict[str, object] = {
        "url": url,
        "html": html,
        "title": title,
        "success": success,
        "error": error,
        "duration": duration,
    }
    if success and html:
        result.update(_extract_fetch_artifacts(html, title))
    return result


def _ensure_fetch_result_fields(result: dict[str, object]) -> dict[str, object]:
    if not result:
        return {}
    if result.get("success") and result.get("html"):
        enriched = dict(result)
        enriched.update(_extract_fetch_artifacts(enriched.get("html", ""), enriched.get("title", "")))
        return enriched
    return result


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
    return len(preview) < MIN_CONTENT_LENGTH // 2


def _should_skip_browser_fallback(url: str, html: str, title: str) -> bool:
    return (
        _looks_like_shell_page(title, html)
        or _looks_like_video_page(url, title, html)
        or _looks_like_listing_or_sparse_page(url, title, html)
    )


def _should_skip_requests_fallback(
    url: str,
    html: str,
    title: str,
    error: str | None = None,
) -> bool:
    lowered_error = (error or "").lower()
    if (
        _looks_like_shell_page(title, html)
        or _looks_like_video_page(url, title, html)
        or _looks_like_listing_or_sparse_page(url, title, html)
    ):
        return True
    return any(token in lowered_error for token in ["robotsblocked", "scheduled maintenance"])


async def _get_lightpanda_session_pool() -> LightPandaSessionPool:
    global _BROWSER_POOL, _BROWSER_POOL_GUARD

    if _BROWSER_POOL is not None and not getattr(_BROWSER_POOL, "_closed", False):
        return _BROWSER_POOL

    if _BROWSER_POOL_GUARD is None:
        _BROWSER_POOL_GUARD = asyncio.Lock()

    async with _BROWSER_POOL_GUARD:
        if _BROWSER_POOL is not None and not getattr(_BROWSER_POOL, "_closed", False):
            return _BROWSER_POOL
        config = get_config().lightpanda
        _BROWSER_POOL = LightPandaSessionPool(
            cdp_url=config.cdp_url,
            timeout=config.timeout,
            max_concurrent=config.max_concurrent,
        )
        return _BROWSER_POOL


async def _fetch_with_lightpanda(url: str, timeout: int) -> dict[str, object]:
    pool = await _get_lightpanda_session_pool()
    return await pool.fetch_html(url, timeout)


def _fetch_with_requests(url: str, timeout: int) -> dict[str, object]:
    start_time = time.time()

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        if response.apparent_encoding:
            response.encoding = response.apparent_encoding

        html = response.text
        title = _extract_title(html)
        duration = time.time() - start_time
        logger.info("Successfully fetched with requests: %s, title: %s", url, title[:50])
        return _build_fetch_result(
            url=url,
            html=html,
            title=title,
            success=True,
            error=None,
            duration=duration,
        )
    except Exception as exc:
        duration = time.time() - start_time
        logger.error("Failed to fetch %s with requests: %s", url, exc)
        return {
            "url": url,
            "html": "",
            "title": "",
            "success": False,
            "error": str(exc),
            "duration": duration,
        }


def close_browser():
    """Idempotently release the shared LightPanda session pool."""
    global _BROWSER_POOL

    pool = _BROWSER_POOL
    _BROWSER_POOL = None
    if pool is None:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(pool.close())
        return

    loop.create_task(pool.close())


def fetch_page_sync(url: str, timeout: int | None = None) -> dict[str, object]:
    return asyncio.run(fetch_page(url, timeout))


def enable_requests_mode():
    global _use_requests
    _use_requests = True
    logger.info("Requests mode enabled")


def enable_lightpanda_mode():
    global _use_requests
    _use_requests = False
    logger.info("LightPanda CDP mode enabled")
