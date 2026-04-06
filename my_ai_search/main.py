import asyncio
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import my_ai_search.main_support as _support
from my_ai_search.deep_process.deep_process import dedup_chunks
from my_ai_search.fetch.fetch import fetch_page
from my_ai_search.process.process import process_content
from my_ai_search.utils.logger import setup_logger

try:
    from my_ai_search.cache.cache import get_cache_stats, get_cached, is_cached, set_cache

    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

logger = setup_logger("main")
_ORIGINAL_SUPPORT_ENRICH_CANDIDATES = _support._enrich_candidate_chunks


def _process_page_from_result(result: dict[str, Any]) -> dict[str, Any]:
    if not result.get("success", False):
        return {"chunks": [], "raw_count": 0}
    try:
        chunks = process_content(result.get("html", ""), url=result.get("url", ""))
        return {"chunks": chunks, "raw_count": len(chunks)}
    except Exception as exc:
        logger.error("Pipeline process failed for %s: %s", result.get("url"), exc)
        return {"chunks": [], "raw_count": 0}


async def _pipeline_fetch_and_process(
    urls: list[str],
    use_cache: bool,
    config,
    disable_deep_process: bool = False,
    fetch_timeout: int | None = None,
    max_useful_pages: int | None = None,
) -> dict[str, Any]:
    pipeline_start = time.time()
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=3)
    semaphore = asyncio.Semaphore(config.lightpanda.max_concurrent)

    all_processed_chunks: list[dict[str, Any]] = []
    fetch_results_map: dict[str, dict[str, Any]] = {}
    cache_hits = 0
    total_raw_chunks = 0
    useful_pages = 0
    stop_fetching = asyncio.Event()
    tasks: list[asyncio.Task] = []

    async def _fetch_and_process(url: str) -> None:
        nonlocal cache_hits, total_raw_chunks, useful_pages
        if stop_fetching.is_set():
            fetch_results_map[url] = {"url": url, "html": "", "title": "", "success": False, "error": "Skipped"}
            return

        try:
            if use_cache and CACHE_AVAILABLE and is_cached(url):
                cached = get_cached(url)
                cache_hits += 1
                result = {
                    "url": url,
                    "html": cached["html"],
                    "title": cached["title"],
                    "success": True,
                    "from_cache": True,
                }
            else:
                async with semaphore:
                    result = await fetch_page(url, timeout=fetch_timeout)
                if result.get("success") and CACHE_AVAILABLE:
                    try:
                        set_cache(url, result.get("html", ""), result.get("title", ""))
                    except Exception as exc:
                        logger.warning("Failed to cache %s: %s", url, exc)

            fetch_results_map[url] = result
            proc_result = await loop.run_in_executor(executor, _process_page_from_result, result)
            all_processed_chunks.extend(proc_result["chunks"])
            total_raw_chunks += proc_result["raw_count"]
            if proc_result["chunks"]:
                useful_pages += 1
                if max_useful_pages and useful_pages >= max_useful_pages:
                    stop_fetching.set()
        except asyncio.CancelledError:
            stop_fetching.set()
            fetch_results_map.setdefault(
                url,
                {"url": url, "html": "", "title": "", "success": False, "error": "Cancelled"},
            )
            raise
        except Exception as exc:
            fetch_results_map[url] = {
                "url": url,
                "html": "",
                "title": "",
                "success": False,
                "error": str(exc),
            }

    try:
        tasks = [asyncio.create_task(_fetch_and_process(url)) for url in urls]
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        stop_fetching.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)

    total_chunks_before_dedup = len(all_processed_chunks)
    if config.deep_process.enable_dedup and not disable_deep_process:
        all_processed_chunks = dedup_chunks(
            all_processed_chunks,
            similarity_threshold=config.deep_process.dedup_threshold,
        )

    fetch_results = [fetch_results_map.get(url, {"url": url, "success": False}) for url in urls]
    return {
        "fetch_results": fetch_results,
        "all_processed_chunks": all_processed_chunks,
        "cache_hits": cache_hits,
        "pipeline_time": time.time() - pipeline_start,
        "total_raw_chunks": total_raw_chunks,
        "total_chunks_before_dedup": total_chunks_before_dedup,
    }


def _build_result_from_local(builder, local_phase: dict[str, Any]) -> dict[str, Any]:
    builder.source = "local"
    builder.results = _support._build_local_results(local_phase["high_quality_results"])
    builder.search_stats = {"urls_found": 0, "time": 0.0}
    builder.fetch_stats = {"total": 0, "success": 0, "failed": 0, "cache_hits": 0, "time": 0.0}
    builder.process_stats = {"chunks": 0, "time": 0.0}
    builder.deep_process_stats = {"chunks": 0, "removed_duplicates": 0, "filtered_low_quality": 0, "time": 0.0}
    builder.vector_stats = {
        "stored_documents": 0,
        "retrieved_results": len(builder.results),
        "time": local_phase["time"],
    }
    return builder.build()


def _build_result_empty(
    builder,
    search_results: list[dict[str, Any]],
    step1_time: float,
    pipeline_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    builder.cache_stats = get_cache_stats() if CACHE_AVAILABLE else {}
    builder.search_stats = {"urls_found": len(search_results), "time": step1_time}
    if pipeline_result:
        urls = len(pipeline_result["fetch_results"])
        successful_fetches = sum(1 for item in pipeline_result["fetch_results"] if item.get("success"))
        builder.fetch_stats = {
            "total": urls,
            "success": successful_fetches,
            "failed": urls - successful_fetches,
            "cache_hits": pipeline_result["cache_hits"],
            "time": pipeline_result["pipeline_time"],
        }
    builder.process_stats = {"chunks": 0, "time": 0.0}
    builder.deep_process_stats = {"chunks": 0, "removed_duplicates": 0, "filtered_low_quality": 0, "time": 0.0}
    return builder.build()


def _build_result_from_pipeline(
    builder,
    search_results: list[dict[str, Any]],
    step1_time: float,
    pipeline_result: dict[str, Any],
    vector_phase: dict[str, Any],
    vector_results: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    filtered_candidate_low_quality: int = 0,
) -> dict[str, Any]:
    removed_duplicates = pipeline_result["total_chunks_before_dedup"] - len(pipeline_result["all_processed_chunks"])
    filtered_low_quality = pipeline_result["total_raw_chunks"] - pipeline_result["total_chunks_before_dedup"]
    successful_fetches = sum(1 for item in pipeline_result["fetch_results"] if item.get("success"))
    builder.results = results
    builder.cache_stats = get_cache_stats() if CACHE_AVAILABLE else {}
    builder.search_stats = {"urls_found": len(search_results), "time": step1_time}
    builder.fetch_stats = {
        "total": len(pipeline_result["fetch_results"]),
        "success": successful_fetches,
        "failed": len(pipeline_result["fetch_results"]) - successful_fetches,
        "cache_hits": pipeline_result["cache_hits"],
        "time": pipeline_result["pipeline_time"],
    }
    builder.process_stats = {"chunks": pipeline_result["total_raw_chunks"], "time": 0.0}
    builder.deep_process_stats = {
        "chunks": len(vector_results),
        "removed_duplicates": removed_duplicates,
        "filtered_low_quality": filtered_low_quality + filtered_candidate_low_quality,
        "time": 0.0,
    }
    builder.vector_stats = {
        "stored_documents": len(vector_phase["document_ids"]),
        "retrieved_results": len(vector_results),
        "time": vector_phase["time"],
        "mode": vector_phase.get("mode"),
    }
    return builder.build()


def _sync_support_runtime() -> None:
    _support.fetch_page = fetch_page
    _support.ThreadPoolExecutor = ThreadPoolExecutor
    _support._pipeline_fetch_and_process = _pipeline_fetch_and_process
    main_module = sys.modules[__name__]
    for name in (
        "asyncio",
        "get_config",
        "validate_config",
        "init_vector_db",
        "hybrid_search",
        "search",
        "store_documents",
        "get_cache_stats",
        "deep_process_page",
    ):
        if hasattr(main_module, name):
            setattr(_support, name, getattr(main_module, name))


async def _search_ai_impl(
    query: str,
    max_results: int | None = None,
    use_cache: bool = True,
    skip_local: bool = False,
    disable_deep_process: bool = False,
    engines: str | None = None,
    mode: str = "balanced",
    client_type: str = "rest",
    tool_context: dict | None = None,
) -> dict[str, Any]:
    _sync_support_runtime()
    return await _support._search_ai_impl(
        query=query,
        max_results=max_results,
        use_cache=use_cache,
        skip_local=skip_local,
        disable_deep_process=disable_deep_process,
        engines=engines,
        mode=mode,
        client_type=client_type,
        tool_context=tool_context,
    )


def search_ai(
    query: str,
    max_results: int | None = None,
    use_cache: bool = True,
    skip_local: bool = False,
    disable_deep_process: bool = False,
    engines: str | None = None,
    mode: str = "balanced",
    client_type: str = "rest",
    tool_context: dict | None = None,
) -> dict[str, Any]:
    _sync_support_runtime()
    return _support.search_ai(
        query=query,
        max_results=max_results,
        use_cache=use_cache,
        skip_local=skip_local,
        disable_deep_process=disable_deep_process,
        engines=engines,
        mode=mode,
        client_type=client_type,
        tool_context=tool_context,
    )


async def search_ai_async(
    query: str,
    max_results: int | None = None,
    use_cache: bool = True,
    skip_local: bool = False,
    disable_deep_process: bool = False,
    engines: str | None = None,
    mode: str = "balanced",
    client_type: str = "rest",
    tool_context: dict | None = None,
) -> dict[str, Any]:
    _sync_support_runtime()
    return await _support.search_ai_async(
        query=query,
        max_results=max_results,
        use_cache=use_cache,
        skip_local=skip_local,
        disable_deep_process=disable_deep_process,
        engines=engines,
        mode=mode,
        client_type=client_type,
        tool_context=tool_context,
    )


def _enrich_candidate_chunks(*args, **kwargs):
    _sync_support_runtime()
    return _ORIGINAL_SUPPORT_ENRICH_CANDIDATES(*args, **kwargs)


def main() -> None:
    _sync_support_runtime()
    _support.main()


def __getattr__(name: str):
    return getattr(_support, name)


if __name__ == "__main__":
    main()
