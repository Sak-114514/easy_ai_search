import asyncio
import json
import sys
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from my_ai_search.config import get_config, validate_config
from my_ai_search.deep_process.deep_process import (
    dedup_chunks,
    deep_process_page,
    select_deep_process_candidates,
)
from my_ai_search.fetch.fetch import fetch_page
from my_ai_search.process.process import process_content
from my_ai_search.search.intent_provider import get_search_intent
from my_ai_search.search.search import search
from my_ai_search.utils.logger import setup_logger
from my_ai_search.utils.text import canonical_path_key, extract_query_terms, looks_non_article_page, normalize_domain
from my_ai_search.vector.vector import init_vector_db, store_documents
from my_ai_search.vector.vector_query import hybrid_search

try:
    from my_ai_search.cache.cache import (
        get_cache_stats,
        get_cached,
        is_cached,
        set_cache,
    )

    CACHE_AVAILABLE = True
    logger = setup_logger("main")
    logger.info("Cache module available")
except ImportError as e:
    CACHE_AVAILABLE = False
    logger = setup_logger("main")
    logger.warning(f"Cache module not available: {e}")

logger = setup_logger("main")

MIN_DEEP_PROCESS_CANDIDATES = 4
MAX_DEEP_PROCESS_CANDIDATES = 12
DEEP_PROCESS_CANDIDATE_MULTIPLIER = 2
MAX_RESULTS_PER_DOMAIN = 2
SEARCH_MODES = frozenset({"fast", "balanced", "deep"})


async def _pipeline_fetch_and_process(
    urls: list[str],
    use_cache: bool,
    config,
    disable_deep_process: bool = False,
    fetch_timeout: int | None = None,
    max_useful_pages: int | None = None,
) -> dict:
    """
    Pipeline: fetch pages and process them concurrently as they arrive.
    Overlaps fetch (I/O) with process + deep_process (CPU) via ThreadPoolExecutor.

    Returns:
        {
            'fetch_results': list,
            'all_processed_chunks': list,
            'cache_hits': int,
            'pipeline_time': float,
            'total_chunks_before_dedup': int,
        }
    """
    pipeline_start = time.time()
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=3)
    semaphore = asyncio.Semaphore(config.lightpanda.max_concurrent)

    all_processed_chunks = []
    fetch_results_map = {}
    cache_hits = 0
    total_raw_chunks = 0
    total_chunks_before_dedup = 0
    useful_pages = 0
    stop_fetching = asyncio.Event()

    def _process_page_sync(result: dict) -> dict:
        if not result.get("success", False):
            return {"chunks": [], "raw_count": 0}
        try:
            chunks = process_content(result["html"], url=result["url"])
            if not chunks:
                return {"chunks": [], "raw_count": 0}
            raw_count = len(chunks)
            return {"chunks": chunks, "raw_count": raw_count}
        except Exception as e:
            logger.error(f"Pipeline process failed for {result.get('url')}: {e}")
            return {"chunks": [], "raw_count": 0}

    async def _fetch_and_process(url: str):
        nonlocal cache_hits, total_raw_chunks, useful_pages

        if stop_fetching.is_set():
            fetch_results_map[url] = {
                "url": url,
                "html": "",
                "title": "",
                "success": False,
                "error": "Skipped after enough useful pages",
            }
            return

        if use_cache and CACHE_AVAILABLE and is_cached(url):
            cache_hits += 1
            cached = get_cached(url)
            result = {
                "url": url,
                "html": cached["html"],
                "title": cached["title"],
                "success": True,
                "from_cache": True,
            }
            fetch_results_map[url] = result
            proc_result = await loop.run_in_executor(
                executor, _process_page_sync, result
            )
            all_processed_chunks.extend(proc_result["chunks"])
            total_raw_chunks += proc_result["raw_count"]
            if proc_result["chunks"]:
                useful_pages += 1
                if max_useful_pages and useful_pages >= max_useful_pages:
                    stop_fetching.set()
        else:
            async with semaphore:
                if stop_fetching.is_set():
                    fetch_results_map[url] = {
                        "url": url,
                        "html": "",
                        "title": "",
                        "success": False,
                        "error": "Skipped after enough useful pages",
                    }
                    return
                try:
                    result = await fetch_page(url, timeout=fetch_timeout)
                except Exception as e:
                    result = {
                        "url": url,
                        "html": "",
                        "title": "",
                        "success": False,
                        "error": str(e),
                    }
            fetch_results_map[url] = result

            if result["success"] and CACHE_AVAILABLE:
                try:
                    set_cache(url, result["html"], result["title"])
                except Exception as e:
                    logger.warning(f"Failed to cache {url}: {e}")

            proc_result = await loop.run_in_executor(
                executor, _process_page_sync, result
            )
            all_processed_chunks.extend(proc_result["chunks"])
            total_raw_chunks += proc_result["raw_count"]
            if proc_result["chunks"]:
                useful_pages += 1
                if max_useful_pages and useful_pages >= max_useful_pages:
                    stop_fetching.set()

    tasks = [asyncio.create_task(_fetch_and_process(url)) for url in urls]
    await asyncio.gather(*tasks)
    executor.shutdown(wait=True)

    if config.deep_process.enable_dedup and not disable_deep_process:
        total_chunks_before_dedup = len(all_processed_chunks)
        all_processed_chunks = dedup_chunks(
            all_processed_chunks,
            similarity_threshold=config.deep_process.dedup_threshold,
        )
    else:
        total_chunks_before_dedup = len(all_processed_chunks)

    fetch_results = [
        fetch_results_map.get(url, {"url": url, "success": False}) for url in urls
    ]

    return {
        "fetch_results": fetch_results,
        "all_processed_chunks": all_processed_chunks,
        "cache_hits": cache_hits,
        "pipeline_time": time.time() - pipeline_start,
        "total_raw_chunks": total_raw_chunks,
        "total_chunks_before_dedup": total_chunks_before_dedup,
    }


def _chunk_doc_id(chunk: dict) -> str:
    return f"{chunk.get('url', 'unknown')}#chunk_{chunk.get('chunk_id', 0)}"


def _build_fallback_results_from_chunks(
    search_results: list[dict],
    chunk_lookup: dict[str, dict],
    max_results: int,
) -> list[dict]:
    """请求级向量召回为空时，回退到当前请求抓取出的正文块，避免因隔离而返回空结果。"""
    final_results = []

    for search_result in search_results:
        if len(final_results) >= max_results:
            break

        source_url = search_result.get("url", "")
        matching_chunk = next(
            (chunk for chunk in chunk_lookup.values() if chunk.get("url") == source_url),
            None,
        )
        if not matching_chunk:
            continue

        metadata = matching_chunk.get("metadata", {})
        content = metadata.get(
            "summary",
            matching_chunk.get("summary")
            or matching_chunk.get("snippet")
            or matching_chunk.get("text", ""),
        )

        final_results.append(
            {
                "title": search_result.get("title") or matching_chunk.get("text", "")[:50],
                "url": source_url,
                "cleaned_content": content,
                "similarity_score": 0.0,
                "metadata": {
                    "chunk_id": matching_chunk.get("chunk_id", 0),
                    "vector_similarity": 0.0,
                    "hybrid_score": 0.0,
                    "deep_processed": False,
                    "source": "online_fallback",
                },
            }
        )

    return final_results


def _normalize_search_mode(mode: str | None) -> str:
    normalized = (mode or "balanced").strip().lower()
    return normalized if normalized in SEARCH_MODES else "balanced"


def _build_search_execution_plan(
    mode: str | None,
    actual_max_results: int,
    disable_deep_process: bool,
    client_type: str = "rest",
) -> dict[str, Any]:
    normalized_mode = _normalize_search_mode(mode)
    fetch_multiplier = 2
    fetch_timeout = None
    store_online_vectors = True
    effective_disable_deep_process = disable_deep_process

    if normalized_mode == "fast":
        fetch_multiplier = 1
        fetch_timeout = 6
        store_online_vectors = False
        effective_disable_deep_process = True
    elif normalized_mode == "deep":
        fetch_multiplier = 3
    elif client_type == "mcp":
        fetch_multiplier = 1
        fetch_timeout = 8

    return {
        "mode": normalized_mode,
        "fetch_target": max(actual_max_results, actual_max_results * fetch_multiplier),
        "fetch_timeout": fetch_timeout,
        "store_online_vectors": store_online_vectors,
        "disable_deep_process": effective_disable_deep_process,
    }


@dataclass
class SearchResultBuilder:
    query: str
    start_time: float
    source: str = "online"
    results: list[dict[str, Any]] = field(default_factory=list)
    cache_stats: dict[str, Any] = field(default_factory=dict)
    search_stats: dict[str, Any] = field(default_factory=dict)
    fetch_stats: dict[str, Any] = field(default_factory=dict)
    process_stats: dict[str, Any] = field(default_factory=dict)
    deep_process_stats: dict[str, Any] = field(default_factory=dict)
    vector_stats: dict[str, Any] = field(default_factory=dict)

    def build(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "results": self.results,
            "total_time": time.time() - self.start_time,
            "source": self.source,
            "cache_stats": self.cache_stats,
            "search_stats": self.search_stats,
            "fetch_stats": self.fetch_stats,
            "process_stats": self.process_stats,
            "deep_process_stats": self.deep_process_stats,
            "vector_stats": self.vector_stats,
        }


def _score_chunk_for_query(query: str, chunk: dict, search_rank: int = 0) -> float:
    terms = _extract_query_terms(query)
    fields = [
        chunk.get("text", "").lower(),
        chunk.get("snippet", "").lower(),
        chunk.get("url", "").lower(),
        str(chunk.get("metadata", {}).get("title", "")).lower(),
    ]
    score = 0.0
    for index, field_text in enumerate(fields):
        weight = 2.0 if index == 0 else 1.0
        for term in terms:
            if term and term in field_text:
                score += weight
    score += max(0.0, 1.0 - search_rank * 0.05)
    score += min(len(chunk.get("text", "")) / 800.0, 1.0)
    return score


def _rank_chunks_in_memory(
    query: str,
    chunks: list[dict],
    search_results: list[dict],
    top_k: int,
) -> list[dict]:
    search_rank_by_url = {
        result.get("url", ""): index for index, result in enumerate(search_results)
    }
    ranked = []
    for chunk in chunks:
        url = chunk.get("url", "")
        score = _score_chunk_for_query(query, chunk, search_rank_by_url.get(url, 99))
        ranked.append(
            {
                "id": _chunk_doc_id(chunk),
                "text": chunk.get("text", ""),
                "metadata": {
                    "source_url": url,
                    "chunk_id": chunk.get("chunk_id", 0),
                },
                "similarity": score,
                "score": score,
            }
        )
    ranked.sort(key=lambda item: item.get("score", 0), reverse=True)
    return ranked[:top_k]


def _normalize_domain(url: str) -> str:
    return normalize_domain(url)


def _canonical_path_key(url: str) -> str:
    return canonical_path_key(url)


def _looks_non_article_page(url: str, title: str, query: str) -> bool:
    return looks_non_article_page(url, title, query)


def _extract_query_terms(query: str) -> list[str]:
    return extract_query_terms(query)


def _prefilter_search_results(
    search_results: list[dict],
    query: str,
    max_results: int,
    intent_plan: dict | None = None,
    fetch_target: int | None = None,
    tool_context: dict | None = None,
) -> list[dict]:
    """抓取前先做站点去重和非正文页过滤，避免浪费抓取预算。"""
    filtered: list[dict] = []
    domain_counts: dict[str, int] = defaultdict(int)
    seen_domain_path: set[tuple[str, str]] = set()
    target_count = fetch_target or max(max_results * 2, max_results)
    source_profile = str((tool_context or {}).get("source_profile") or "general").strip().lower()
    max_results_per_domain = (intent_plan or {}).get("max_results_per_domain", MAX_RESULTS_PER_DOMAIN)
    if source_profile in {"tech_community", "social_realtime"}:
        max_results_per_domain = 1

    for result in search_results:
        url = result.get("url", "")
        title = result.get("title", "")
        domain = _normalize_domain(url)
        path_key = _canonical_path_key(url)

        if _looks_non_article_page(url, title, query):
            logger.debug(f"Skipping non-article search result before fetch: {url}")
            continue

        intent = (intent_plan or {}).get("intent", "general")
        if intent == "news" and any(marker in url.lower() for marker in ("wikipedia.org", "baike.baidu.com")):
            logger.debug(f"Skipping reference page for news query before fetch: {url}")
            continue
        if intent == "technical" and "stackoverflow.com/questions" in url.lower():
            logger.debug(f"Skipping QA page for technical comparison query before fetch: {url}")
            continue

        domain_path = (domain, path_key)
        if domain_path in seen_domain_path:
            logger.debug(f"Skipping duplicate template path before fetch: {url}")
            continue

        if domain_counts[domain] >= max_results_per_domain:
            logger.debug(f"Skipping domain-overflow result before fetch: {url}")
            continue

        seen_domain_path.add(domain_path)
        domain_counts[domain] += 1
        filtered.append(result)

        if len(filtered) >= target_count:
            break

    if len(filtered) < max_results:
        for result in search_results:
            if result in filtered:
                continue
            if result.get("url") in {item.get("url") for item in filtered}:
                continue
            filtered.append(result)
            if len(filtered) >= max_results:
                break

    return filtered


def _select_candidate_budget(max_results: int) -> int:
    budget = max(max_results * DEEP_PROCESS_CANDIDATE_MULTIPLIER, MIN_DEEP_PROCESS_CANDIDATES)
    return min(budget, MAX_DEEP_PROCESS_CANDIDATES)


def _enrich_candidate_chunks(
    query: str,
    vector_results: list[dict],
    chunk_lookup: dict[str, dict],
    config,
    max_results: int,
    disable_deep_process: bool,
) -> dict:
    if disable_deep_process:
        return {"processed_map": {}, "candidate_ids": set(), "filtered_low_quality": 0}

    candidate_budget = _select_candidate_budget(max_results)
    candidate_pool = []
    seen_ids = set()
    for vector_result in vector_results:
        chunk_id = vector_result.get("id", "")
        if not chunk_id or chunk_id in seen_ids or chunk_id not in chunk_lookup:
            continue
        candidate_pool.append(chunk_lookup[chunk_id])
        seen_ids.add(chunk_id)
        if len(candidate_pool) >= candidate_budget:
            break

    selected_chunks = select_deep_process_candidates(
        candidate_pool,
        query=query,
        max_candidates=min(candidate_budget, len(candidate_pool)),
    )
    candidate_ids = {_chunk_doc_id(chunk) for chunk in selected_chunks}

    grouped_chunks = defaultdict(list)
    for chunk in selected_chunks:
        grouped_chunks[chunk.get("url", "unknown")].append(chunk)

    processed_map = {}
    filtered_low_quality = 0
    for page_chunks in grouped_chunks.values():
        processed_chunks = deep_process_page(
            page_chunks,
            enable_summary=config.deep_process.enable_summary,
            enable_quality_check=config.deep_process.enable_quality_check,
            min_quality_score=config.deep_process.min_quality_score,
        )
        filtered_low_quality += len(page_chunks) - len(processed_chunks)
        for chunk in processed_chunks:
            processed_map[_chunk_doc_id(chunk)] = chunk

    return {
        "processed_map": processed_map,
        "candidate_ids": candidate_ids,
        "filtered_low_quality": filtered_low_quality,
    }


def _validate_and_prepare(
    query: str,
    max_results: int | None,
    disable_deep_process: bool,
    mode: str,
    client_type: str,
) -> dict[str, Any]:
    config = get_config()
    if not validate_config(config):
        raise ValueError("Configuration validation failed")

    init_vector_db()
    actual_max_results = max_results or config.searxng.max_results
    execution_plan = _build_search_execution_plan(
        mode=mode,
        actual_max_results=actual_max_results,
        disable_deep_process=disable_deep_process,
        client_type=client_type,
    )
    return {
        "config": config,
        "actual_max_results": actual_max_results,
        "execution_plan": execution_plan,
        "min_similarity": 0.75,
        "query": query,
    }


def _build_local_results(vector_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    final_results = []
    seen_urls = set()
    for vector_result in vector_results:
        source_url = vector_result["metadata"].get("source_url", "")
        chunk_id = vector_result["metadata"].get("chunk_id", 0)
        if source_url in seen_urls:
            continue
        seen_urls.add(source_url)
        final_results.append(
            {
                "title": vector_result["text"][:50],
                "url": source_url,
                "cleaned_content": vector_result.get("metadata", {}).get(
                    "summary", vector_result.get("metadata", {}).get("snippet", vector_result["text"])
                ),
                "similarity_score": vector_result.get("score", vector_result["similarity"]),
                "metadata": {
                    "chunk_id": chunk_id,
                    "vector_similarity": vector_result["similarity"],
                    "hybrid_score": vector_result.get("score", 0),
                    "source": "local",
                },
            }
        )
    return final_results


async def _run_local_search_phase(query: str, actual_max_results: int, min_similarity: float) -> dict[str, Any]:
    step0_start = time.time()
    local_results = await asyncio.to_thread(hybrid_search, query, actual_max_results)
    step0_time = time.time() - step0_start
    high_quality_results = [r for r in local_results if r.get("similarity", 0) >= min_similarity]
    return {
        "all_results": local_results,
        "high_quality_results": high_quality_results,
        "time": step0_time,
    }


async def _run_online_search_phase(
    query: str,
    max_results: int | None,
    actual_max_results: int,
    engines: str | None,
    tool_context: dict[str, Any] | None,
    execution_plan: dict[str, Any],
) -> dict[str, Any]:
    step1_start = time.time()
    intent_plan = await asyncio.to_thread(get_search_intent, query)
    search_results = await asyncio.to_thread(
        search,
        query=query,
        max_results=max_results,
        engines=engines,
        intent_plan=intent_plan,
        tool_context=tool_context,
    )
    search_results = _prefilter_search_results(
        search_results=search_results,
        query=query,
        max_results=actual_max_results,
        intent_plan=intent_plan,
        fetch_target=execution_plan["fetch_target"],
        tool_context=tool_context,
    )
    return {
        "intent_plan": intent_plan,
        "search_results": search_results,
        "time": time.time() - step1_start,
    }


async def _run_vector_phase(
    query: str,
    actual_max_results: int,
    execution_plan: dict[str, Any],
    all_processed_chunks: list[dict[str, Any]],
    search_results: list[dict[str, Any]],
) -> dict[str, Any]:
    search_request_id = str(uuid.uuid4())
    document_ids: list[str] = []
    step5_time = 0.0
    step6_time = 0.0

    if execution_plan["store_online_vectors"]:
        step5_start = time.time()
        document_ids = await asyncio.to_thread(
            store_documents,
            all_processed_chunks,
            {
                "search_request_id": search_request_id,
                "content_scope": "online_temp",
            },
        )
        step5_time = time.time() - step5_start

        step6_start = time.time()
        vector_results = await asyncio.to_thread(
            hybrid_search,
            query,
            actual_max_results * 3,
            {"search_request_id": search_request_id},
        )
        step6_time = time.time() - step6_start
    else:
        vector_results = _rank_chunks_in_memory(
            query=query,
            chunks=all_processed_chunks,
            search_results=search_results,
            top_k=actual_max_results * 3,
        )

    return {
        "vector_results": vector_results,
        "document_ids": document_ids,
        "time": step5_time + step6_time,
        "search_request_id": search_request_id,
    }


def _build_online_results(
    vector_results: list[dict[str, Any]],
    search_results: list[dict[str, Any]],
    chunk_lookup: dict[str, dict[str, Any]],
    deep_processed_map: dict[str, dict[str, Any]],
    candidate_ids: set[str],
) -> list[dict[str, Any]]:
    final_results: list[dict[str, Any]] = []
    seen_urls = set()

    for vector_result in vector_results:
        source_url = vector_result["metadata"].get("source_url", "")
        chunk_id = vector_result["metadata"].get("chunk_id", 0)
        doc_id = vector_result.get("id") or f"{source_url}#chunk_{chunk_id}"

        if doc_id in candidate_ids and doc_id not in deep_processed_map:
            logger.debug(f"Skipping low-quality candidate result: {doc_id}")
            continue
        if source_url in seen_urls:
            continue
        seen_urls.add(source_url)

        original_result = next((r for r in search_results if r["url"] == source_url), None)
        display_chunk = deep_processed_map.get(doc_id, chunk_lookup.get(doc_id, {}))
        display_metadata = display_chunk.get("metadata", {})
        display_text = display_chunk.get("text", vector_result["text"])

        final_results.append(
            {
                "title": original_result["title"] if original_result else vector_result["text"][:50],
                "url": source_url,
                "cleaned_content": display_metadata.get(
                    "summary",
                    display_chunk.get(
                        "summary",
                        display_chunk.get(
                            "snippet",
                            vector_result.get("metadata", {}).get(
                                "summary",
                                vector_result.get("metadata", {}).get("snippet", display_text),
                            ),
                        ),
                    ),
                ),
                "similarity_score": vector_result.get("score", vector_result["similarity"]),
                "metadata": {
                    "chunk_id": chunk_id,
                    "vector_similarity": vector_result["similarity"],
                    "hybrid_score": vector_result.get("score", 0),
                    "deep_processed": doc_id in deep_processed_map,
                    "source": "online",
                },
            }
        )

    return final_results


def _run_local_search_phase_sync(query: str, actual_max_results: int, min_similarity: float) -> dict[str, Any]:
    step0_start = time.time()
    local_results = hybrid_search(query, top_k=actual_max_results)
    step0_time = time.time() - step0_start
    high_quality_results = [r for r in local_results if r.get("similarity", 0) >= min_similarity]
    return {
        "all_results": local_results,
        "high_quality_results": high_quality_results,
        "time": step0_time,
    }


def _run_online_search_phase_sync(
    query: str,
    max_results: int | None,
    actual_max_results: int,
    engines: str | None,
    tool_context: dict[str, Any] | None,
    execution_plan: dict[str, Any],
) -> dict[str, Any]:
    step1_start = time.time()
    intent_plan = get_search_intent(query)
    search_results = search(
        query=query,
        max_results=max_results,
        engines=engines,
        intent_plan=intent_plan,
        tool_context=tool_context,
    )
    search_results = _prefilter_search_results(
        search_results=search_results,
        query=query,
        max_results=actual_max_results,
        intent_plan=intent_plan,
        fetch_target=execution_plan["fetch_target"],
        tool_context=tool_context,
    )
    return {
        "intent_plan": intent_plan,
        "search_results": search_results,
        "time": time.time() - step1_start,
    }


def _run_vector_phase_sync(
    query: str,
    actual_max_results: int,
    execution_plan: dict[str, Any],
    all_processed_chunks: list[dict[str, Any]],
    search_results: list[dict[str, Any]],
) -> dict[str, Any]:
    search_request_id = str(uuid.uuid4())
    document_ids: list[str] = []
    step5_time = 0.0
    step6_time = 0.0

    if execution_plan["store_online_vectors"]:
        step5_start = time.time()
        document_ids = store_documents(
            all_processed_chunks,
            metadata={
                "search_request_id": search_request_id,
                "content_scope": "online_temp",
            },
        )
        step5_time = time.time() - step5_start

        step6_start = time.time()
        vector_results = hybrid_search(
            query,
            top_k=actual_max_results * 3,
            filter_metadata={"search_request_id": search_request_id},
        )
        step6_time = time.time() - step6_start
    else:
        vector_results = _rank_chunks_in_memory(
            query=query,
            chunks=all_processed_chunks,
            search_results=search_results,
            top_k=actual_max_results * 3,
        )

    return {
        "vector_results": vector_results,
        "document_ids": document_ids,
        "time": step5_time + step6_time,
        "search_request_id": search_request_id,
    }


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
    start_time = time.time()
    logger.info(f"Starting AI search: query='{query}', max_results={max_results}")

    try:
        prepared = await asyncio.to_thread(
            _validate_and_prepare,
            query,
            max_results,
            disable_deep_process,
            mode=mode,
            client_type=client_type,
        )
        config = prepared["config"]
        actual_max_results = prepared["actual_max_results"]
        execution_plan = prepared["execution_plan"]
        effective_disable_deep_process = execution_plan["disable_deep_process"]
        min_similarity = prepared["min_similarity"]
        builder = SearchResultBuilder(query=query, start_time=start_time)

        if not skip_local:
            logger.info("Step 0: Searching local vector database...")
            local_phase = await _run_local_search_phase(query, actual_max_results, min_similarity)
            high_quality_local_results = local_phase["high_quality_results"]

            if len(high_quality_local_results) >= actual_max_results:
                logger.info(
                    f"Found {len(high_quality_local_results)} high-quality results in local DB, skipping online search"
                )
                builder.source = "local"
                builder.results = _build_local_results(high_quality_local_results)
                builder.search_stats = {"urls_found": 0, "time": 0.0}
                builder.fetch_stats = {"total": 0, "success": 0, "failed": 0, "cache_hits": 0, "time": 0.0}
                builder.process_stats = {"chunks": 0, "time": 0.0}
                builder.deep_process_stats = {
                    "chunks": 0,
                    "removed_duplicates": 0,
                    "filtered_low_quality": 0,
                    "time": 0.0,
                }
                builder.vector_stats = {
                    "stored_documents": 0,
                    "retrieved_results": len(builder.results),
                    "time": local_phase["time"],
                }
                return builder.build()
            else:
                logger.info(
                    "Found only %s high-quality results in local DB, proceeding to online search",
                    len(high_quality_local_results),
                )

        logger.info("Step 1: Searching URLs...")
        online_phase = await _run_online_search_phase(
            query=query,
            max_results=max_results,
            actual_max_results=actual_max_results,
            engines=engines,
            tool_context=tool_context,
            execution_plan=execution_plan,
        )
        search_results = online_phase["search_results"]
        step1_time = online_phase["time"]

        if not search_results:
            logger.warning("No search results found")
            builder.search_stats = {"urls_found": 0, "time": step1_time}
            return builder.build()

        logger.info(f"Found {len(search_results)} URLs")
        logger.info("Step 2-4: Pipeline fetch → process → deep_process...")
        urls = [result["url"] for result in search_results]
        pipeline_result = await _pipeline_fetch_and_process(
            urls,
            use_cache,
            config,
            disable_deep_process=effective_disable_deep_process,
            fetch_timeout=execution_plan["fetch_timeout"],
            max_useful_pages=actual_max_results if execution_plan["mode"] == "fast" else None,
        )

        fetch_results = pipeline_result["fetch_results"]
        all_processed_chunks = pipeline_result["all_processed_chunks"]
        cache_hits = pipeline_result["cache_hits"]
        pipeline_time = pipeline_result["pipeline_time"]
        total_raw_chunks = pipeline_result["total_raw_chunks"]
        total_chunks_before_dedup = pipeline_result["total_chunks_before_dedup"]

        successful_fetches = sum(1 for r in fetch_results if r["success"])
        logger.info(f"Pipeline completed in {pipeline_time:.2f}s")
        logger.info(f"Fetched {successful_fetches}/{len(urls)} pages")

        if not all_processed_chunks:
            logger.warning("No content chunks generated after pipeline")
            builder.cache_stats = get_cache_stats() if CACHE_AVAILABLE else {}
            builder.search_stats = {"urls_found": len(search_results), "time": step1_time}
            builder.fetch_stats = {
                "total": len(urls),
                "success": successful_fetches,
                "failed": len(urls) - successful_fetches,
                "cache_hits": cache_hits,
                "time": pipeline_time,
            }
            builder.process_stats = {"chunks": 0, "time": 0.0}
            builder.deep_process_stats = {
                "chunks": 0,
                "removed_duplicates": 0,
                "filtered_low_quality": 0,
                "time": 0.0,
            }
            return builder.build()

        removed_duplicates = total_chunks_before_dedup - len(all_processed_chunks)
        filtered_low_quality = total_raw_chunks - total_chunks_before_dedup
        logger.info(
            f"Pipeline result: {total_chunks_before_dedup} -> {len(all_processed_chunks)} chunks"
        )
        logger.info(f"  - Removed duplicates: {removed_duplicates}")

        vector_phase = await _run_vector_phase(
            query=query,
            actual_max_results=actual_max_results,
            execution_plan=execution_plan,
            all_processed_chunks=all_processed_chunks,
            search_results=search_results,
        )
        vector_results = vector_phase["vector_results"]
        document_ids = vector_phase["document_ids"]
        chunk_lookup = {_chunk_doc_id(chunk): chunk for chunk in all_processed_chunks}
        logger.info(f"Found {len(vector_results)} vector results")

        if not vector_results:
            logger.warning(
                "No request-scoped vector results found, falling back to current request chunks"
            )
            builder.results = _build_fallback_results_from_chunks(
                search_results=search_results,
                chunk_lookup=chunk_lookup,
                max_results=actual_max_results,
            )
            builder.cache_stats = get_cache_stats() if CACHE_AVAILABLE else {}
            builder.search_stats = {"urls_found": len(search_results), "time": step1_time}
            builder.fetch_stats = {
                "total": len(urls),
                "success": successful_fetches,
                "failed": len(urls) - successful_fetches,
                "cache_hits": cache_hits,
                "time": pipeline_time,
            }
            builder.process_stats = {"chunks": total_raw_chunks, "time": 0.0}
            builder.deep_process_stats = {
                "chunks": 0,
                "removed_duplicates": removed_duplicates,
                "filtered_low_quality": filtered_low_quality,
                "time": 0.0,
            }
            builder.vector_stats = {
                "stored_documents": len(document_ids),
                "retrieved_results": 0,
                "time": vector_phase["time"],
                "mode": execution_plan["mode"],
            }
            result = builder.build()
            logger.info(f"AI search completed in {result['total_time']:.2f}s")
            return result

        candidate_result = _enrich_candidate_chunks(
            query=query,
            vector_results=vector_results,
            chunk_lookup=chunk_lookup,
            config=config,
            max_results=actual_max_results,
            disable_deep_process=effective_disable_deep_process,
        )
        deep_processed_map = candidate_result["processed_map"]
        candidate_ids = candidate_result["candidate_ids"]
        filtered_candidate_low_quality = candidate_result["filtered_low_quality"]

        builder.results = _build_online_results(
            vector_results=vector_results,
            search_results=search_results,
            chunk_lookup=chunk_lookup,
            deep_processed_map=deep_processed_map,
            candidate_ids=candidate_ids,
        )
        builder.cache_stats = get_cache_stats() if CACHE_AVAILABLE else {}
        builder.search_stats = {"urls_found": len(search_results), "time": step1_time}
        builder.fetch_stats = {
            "total": len(urls),
            "success": successful_fetches,
            "failed": len(urls) - successful_fetches,
            "cache_hits": cache_hits,
            "time": pipeline_time,
        }
        builder.process_stats = {"chunks": total_raw_chunks, "time": 0.0}
        builder.deep_process_stats = {
            "chunks": len(deep_processed_map),
            "removed_duplicates": removed_duplicates,
            "filtered_low_quality": filtered_low_quality + filtered_candidate_low_quality,
            "time": 0.0,
        }
        builder.vector_stats = {
            "stored_documents": len(document_ids),
            "retrieved_results": len(vector_results),
            "time": vector_phase["time"],
            "mode": execution_plan["mode"],
        }
        result = builder.build()
        logger.info(f"AI search completed in {result['total_time']:.2f}s")
        return result

    except Exception as e:
        logger.error(f"AI search failed: {e}")
        raise


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
    start_time = time.time()
    logger.info(f"Starting AI search: query='{query}', max_results={max_results}")

    try:
        prepared = _validate_and_prepare(
            query=query,
            max_results=max_results,
            disable_deep_process=disable_deep_process,
            mode=mode,
            client_type=client_type,
        )
        config = prepared["config"]
        actual_max_results = prepared["actual_max_results"]
        execution_plan = prepared["execution_plan"]
        effective_disable_deep_process = execution_plan["disable_deep_process"]
        min_similarity = prepared["min_similarity"]
        builder = SearchResultBuilder(query=query, start_time=start_time)

        if not skip_local:
            logger.info("Step 0: Searching local vector database...")
            local_phase = _run_local_search_phase_sync(query, actual_max_results, min_similarity)
            high_quality_local_results = local_phase["high_quality_results"]

            if len(high_quality_local_results) >= actual_max_results:
                logger.info(
                    f"Found {len(high_quality_local_results)} high-quality results in local DB, skipping online search"
                )
                builder.source = "local"
                builder.results = _build_local_results(high_quality_local_results)
                builder.search_stats = {"urls_found": 0, "time": 0.0}
                builder.fetch_stats = {"total": 0, "success": 0, "failed": 0, "cache_hits": 0, "time": 0.0}
                builder.process_stats = {"chunks": 0, "time": 0.0}
                builder.deep_process_stats = {
                    "chunks": 0,
                    "removed_duplicates": 0,
                    "filtered_low_quality": 0,
                    "time": 0.0,
                }
                builder.vector_stats = {
                    "stored_documents": 0,
                    "retrieved_results": len(builder.results),
                    "time": local_phase["time"],
                }
                result = builder.build()
                logger.info(f"AI search completed in {result['total_time']:.2f}s")
                return result

            logger.info(
                "Found only %s high-quality results in local DB, proceeding to online search",
                len(high_quality_local_results),
            )

        logger.info("Step 1: Searching URLs...")
        online_phase = _run_online_search_phase_sync(
            query=query,
            max_results=max_results,
            actual_max_results=actual_max_results,
            engines=engines,
            tool_context=tool_context,
            execution_plan=execution_plan,
        )
        search_results = online_phase["search_results"]
        step1_time = online_phase["time"]

        if not search_results:
            logger.warning("No search results found")
            builder.search_stats = {"urls_found": 0, "time": step1_time}
            result = builder.build()
            logger.info(f"AI search completed in {result['total_time']:.2f}s")
            return result

        logger.info(f"Found {len(search_results)} URLs")
        logger.info("Step 2-4: Pipeline fetch → process → deep_process...")
        urls = [result["url"] for result in search_results]
        pipeline_coro = _pipeline_fetch_and_process(
            urls,
            use_cache,
            config,
            disable_deep_process=effective_disable_deep_process,
            fetch_timeout=execution_plan["fetch_timeout"],
            max_useful_pages=actual_max_results if execution_plan["mode"] == "fast" else None,
        )
        pipeline_result = asyncio.run(pipeline_coro)

        fetch_results = pipeline_result["fetch_results"]
        all_processed_chunks = pipeline_result["all_processed_chunks"]
        cache_hits = pipeline_result["cache_hits"]
        pipeline_time = pipeline_result["pipeline_time"]
        total_raw_chunks = pipeline_result["total_raw_chunks"]
        total_chunks_before_dedup = pipeline_result["total_chunks_before_dedup"]

        successful_fetches = sum(1 for r in fetch_results if r["success"])
        if not all_processed_chunks:
            builder.cache_stats = get_cache_stats() if CACHE_AVAILABLE else {}
            builder.search_stats = {"urls_found": len(search_results), "time": step1_time}
            builder.fetch_stats = {
                "total": len(urls),
                "success": successful_fetches,
                "failed": len(urls) - successful_fetches,
                "cache_hits": cache_hits,
                "time": pipeline_time,
            }
            builder.process_stats = {"chunks": 0, "time": 0.0}
            builder.deep_process_stats = {
                "chunks": 0,
                "removed_duplicates": 0,
                "filtered_low_quality": 0,
                "time": 0.0,
            }
            result = builder.build()
            logger.info(f"AI search completed in {result['total_time']:.2f}s")
            return result

        removed_duplicates = total_chunks_before_dedup - len(all_processed_chunks)
        filtered_low_quality = total_raw_chunks - total_chunks_before_dedup
        vector_phase = _run_vector_phase_sync(
            query=query,
            actual_max_results=actual_max_results,
            execution_plan=execution_plan,
            all_processed_chunks=all_processed_chunks,
            search_results=search_results,
        )
        vector_results = vector_phase["vector_results"]
        document_ids = vector_phase["document_ids"]
        chunk_lookup = {_chunk_doc_id(chunk): chunk for chunk in all_processed_chunks}

        if not vector_results:
            builder.results = _build_fallback_results_from_chunks(
                search_results=search_results,
                chunk_lookup=chunk_lookup,
                max_results=actual_max_results,
            )
            builder.cache_stats = get_cache_stats() if CACHE_AVAILABLE else {}
            builder.search_stats = {"urls_found": len(search_results), "time": step1_time}
            builder.fetch_stats = {
                "total": len(urls),
                "success": successful_fetches,
                "failed": len(urls) - successful_fetches,
                "cache_hits": cache_hits,
                "time": pipeline_time,
            }
            builder.process_stats = {"chunks": total_raw_chunks, "time": 0.0}
            builder.deep_process_stats = {
                "chunks": 0,
                "removed_duplicates": removed_duplicates,
                "filtered_low_quality": filtered_low_quality,
                "time": 0.0,
            }
            builder.vector_stats = {
                "stored_documents": len(document_ids),
                "retrieved_results": 0,
                "time": vector_phase["time"],
                "mode": execution_plan["mode"],
            }
            result = builder.build()
            logger.info(f"AI search completed in {result['total_time']:.2f}s")
            return result

        candidate_result = _enrich_candidate_chunks(
            query=query,
            vector_results=vector_results,
            chunk_lookup=chunk_lookup,
            config=config,
            max_results=actual_max_results,
            disable_deep_process=effective_disable_deep_process,
        )
        deep_processed_map = candidate_result["processed_map"]
        candidate_ids = candidate_result["candidate_ids"]
        filtered_candidate_low_quality = candidate_result["filtered_low_quality"]

        builder.results = _build_online_results(
            vector_results=vector_results,
            search_results=search_results,
            chunk_lookup=chunk_lookup,
            deep_processed_map=deep_processed_map,
            candidate_ids=candidate_ids,
        )
        builder.cache_stats = get_cache_stats() if CACHE_AVAILABLE else {}
        builder.search_stats = {"urls_found": len(search_results), "time": step1_time}
        builder.fetch_stats = {
            "total": len(urls),
            "success": successful_fetches,
            "failed": len(urls) - successful_fetches,
            "cache_hits": cache_hits,
            "time": pipeline_time,
        }
        builder.process_stats = {"chunks": total_raw_chunks, "time": 0.0}
        builder.deep_process_stats = {
            "chunks": len(deep_processed_map),
            "removed_duplicates": removed_duplicates,
            "filtered_low_quality": filtered_low_quality + filtered_candidate_low_quality,
            "time": 0.0,
        }
        builder.vector_stats = {
            "stored_documents": len(document_ids),
            "retrieved_results": len(vector_results),
            "time": vector_phase["time"],
            "mode": execution_plan["mode"],
        }
        result = builder.build()
        logger.info(f"AI search completed in {result['total_time']:.2f}s")
        return result
    except Exception as e:
        logger.error(f"AI search failed: {e}")
        raise


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
    return await _search_ai_impl(
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


def main():
    """
    命令行入口
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="AI Search - Local AI-powered search engine"
    )
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument(
        "--max-results", type=int, default=5, help="Maximum number of results"
    )
    parser.add_argument("--no-cache", action="store_true", help="Disable cache")
    parser.add_argument(
        "--format", choices=["json", "pretty"], default="pretty", help="Output format"
    )

    args = parser.parse_args()

    logger.info("Starting AI search CLI")
    logger.info(f"Query: {args.query}")
    logger.info(f"Max results: {args.max_results}")
    logger.info(f"Cache: {'disabled' if args.no_cache else 'enabled'}")

    try:
        result = search_ai(
            query=args.query, max_results=args.max_results, use_cache=not args.no_cache
        )

        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\n{'=' * 60}")
            print(f"AI Search Results for: {args.query}")
            print(f"{'=' * 60}")
            print(f"\nTotal Results: {len(result['results'])}")
            print(f"Total Time: {result['total_time']:.2f}s")
            print(f"Source: {result.get('source', 'unknown').upper()}")
            print("\nStatistics:")
            print(f"  - URLs found: {result['search_stats']['urls_found']}")
            print(
                f"  - Pages fetched: {result['fetch_stats']['success']}/{result['fetch_stats']['total']}"
            )
            print(f"  - Cache hits: {result['fetch_stats']['cache_hits']}")
            print(f"  - Chunks generated: {result['process_stats']['chunks']}")
            print(
                f"  - Chunks after deep process: {result['deep_process_stats']['chunks']}"
            )
            print(
                f"  - Removed duplicates: {result['deep_process_stats']['removed_duplicates']}"
            )
            print(
                f"  - Filtered low quality: {result['deep_process_stats']['filtered_low_quality']}"
            )
            print(f"  - Documents stored: {result['vector_stats']['stored_documents']}")

            if CACHE_AVAILABLE:
                cache_stats = result["cache_stats"]
                print(f"  - Cache hit rate: {cache_stats.get('hit_rate', 0):.2%}")

            print(f"\n{'-' * 60}")
            print("Top Results:")
            print(f"{'-' * 60}")

            for i, r in enumerate(result["results"], 1):
                print(f"\n{i}. {r['title']}")
                print(f"   URL: {r['url']}")
                print(f"   Score: {r['similarity_score']:.3f}")
                print(f"   Content: {r['cleaned_content'][:150]}...")

            print(f"\n{'=' * 60}\n")

        sys.exit(0)

    except Exception as e:
        logger.error(f"Search failed: {e}")
        print(f"\nError: {e}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
