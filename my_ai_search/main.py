import sys
import os
import time
import json
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from my_ai_search.config import get_config, validate_config
from my_ai_search.utils.logger import setup_logger
from my_ai_search.search.search import search
from my_ai_search.fetch.fetch_concurrent import fetch_pages_sync
from my_ai_search.process.process import process_content
from my_ai_search.deep_process.deep_process import deep_process_content
from my_ai_search.vector.vector import init_vector_db, store_documents
from my_ai_search.vector.vector_query import hybrid_search

try:
    from my_ai_search.cache.cache import (
        set_cache,
        get_cached,
        is_cached,
        get_cache_stats,
    )

    CACHE_AVAILABLE = True
    logger = setup_logger("main")
    logger.info("Cache module available")
except ImportError as e:
    CACHE_AVAILABLE = False
    logger = setup_logger("main")
    logger.warning(f"Cache module not available: {e}")

logger = setup_logger("main")


def search_ai(
    query: str, max_results: Optional[int] = None, use_cache: bool = True
) -> Dict:
    """
    主搜索函数（同步版本）

    Args:
        query: 用户查询
        max_results: 最大结果数
        use_cache: 是否使用缓存

    Returns:
        标准化结果字典
    """
    start_time = time.time()

    config = get_config()
    if not validate_config(config):
        raise Exception("Configuration validation failed")

    logger.info(f"Starting AI search: query='{query}', max_results={max_results}")

    try:
        logger.info("Initializing vector database...")
        init_vector_db()

        logger.info("Step 1: Searching URLs...")
        step1_start = time.time()
        search_results = search(query, max_results=max_results)
        step1_time = time.time() - step1_start

        if not search_results:
            logger.warning("No search results found")
            return {
                "query": query,
                "results": [],
                "total_time": time.time() - start_time,
                "cache_stats": {},
                "search_stats": {"urls_found": 0, "time": step1_time},
                "vector_stats": {},
            }

        logger.info(f"Found {len(search_results)} URLs")

        logger.info("Step 2: Fetching pages...")
        step2_start = time.time()
        urls = [result["url"] for result in search_results]

        fetch_results = []
        cache_hits = 0

        if use_cache and CACHE_AVAILABLE:
            for url in urls:
                if is_cached(url):
                    logger.info(f"Cache hit: {url}")
                    cached = get_cached(url)
                    fetch_results.append(
                        {
                            "url": url,
                            "html": cached["html"],
                            "title": cached["title"],
                            "success": True,
                            "error": None,
                            "from_cache": True,
                        }
                    )
                    cache_hits += 1
                else:
                    fetch_results.append({"url": url, "success": False})

            uncached_urls = [r["url"] for r in fetch_results if not r.get("from_cache")]
            if uncached_urls:
                uncached_results = fetch_pages_sync(uncached_urls)

                for i, result in enumerate(uncached_results):
                    url = uncached_urls[i]
                    if result["success"]:
                        for r in fetch_results:
                            if r["url"] == url:
                                r.update(result)
                                break
                        set_cache(url, result["html"], result["title"])
        else:
            fetch_results = fetch_pages_sync(urls)

        step2_time = time.time() - step2_start

        successful_fetches = sum(1 for r in fetch_results if r["success"])
        logger.info(f"Fetched {successful_fetches}/{len(urls)} pages")

        logger.info("Step 3: Processing content...")
        step3_start = time.time()

        all_chunks = []
        for fetch_result in fetch_results:
            if not fetch_result["success"]:
                continue

            chunks = process_content(fetch_result["html"], url=fetch_result["url"])
            all_chunks.extend(chunks)

        step3_time = time.time() - step3_start

        logger.info(
            f"Generated {len(all_chunks)} chunks from {successful_fetches} pages"
        )

        if not all_chunks:
            logger.warning("No content chunks generated")
            return {
                "query": query,
                "results": search_results,
                "total_time": time.time() - start_time,
                "cache_stats": get_cache_stats() if CACHE_AVAILABLE else {},
                "search_stats": {"urls_found": len(search_results), "time": step1_time},
                "fetch_stats": {
                    "total": len(urls),
                    "success": successful_fetches,
                    "failed": len(urls) - successful_fetches,
                    "cache_hits": cache_hits,
                    "time": step2_time,
                },
                "process_stats": {"chunks": 0, "time": step3_time},
                "deep_process_stats": {
                    "chunks": 0,
                    "removed_duplicates": 0,
                    "filtered_low_quality": 0,
                    "time": 0.0,
                },
                "vector_stats": {},
            }

        logger.info("Step 4: Deep processing content...")
        step4_start = time.time()

        config = get_config()
        deep_processed_chunks = deep_process_content(
            all_chunks,
            enable_summary=config.deep_process.enable_summary,
            enable_dedup=config.deep_process.enable_dedup,
            enable_quality_check=config.deep_process.enable_quality_check,
        )

        step4_time = time.time() - step4_start

        removed_duplicates = len(all_chunks) - len(deep_processed_chunks)
        filtered_low_quality = 0
        if config.deep_process.enable_quality_check:
            low_quality_count = sum(
                1
                for chunk in all_chunks
                if chunk.get("quality_score", 1.0)
                < config.deep_process.min_quality_score
            )
            filtered_low_quality = low_quality_count

        logger.info(
            f"Deep processing: {len(all_chunks)} -> {len(deep_processed_chunks)} chunks"
        )
        logger.info(f"  - Removed duplicates: {removed_duplicates}")
        logger.info(f"  - Filtered low quality: {filtered_low_quality}")

        logger.info("Step 5: Storing documents...")
        step5_start = time.time()

        document_ids = store_documents(deep_processed_chunks)

        step5_time = time.time() - step5_start
        logger.info(f"Stored {len(document_ids)} documents")

        logger.info("Step 6: Searching vectors...")
        step6_start = time.time()

        vector_results = hybrid_search(query, top_k=max_results)

        step6_time = time.time() - step6_start

        logger.info(f"Found {len(vector_results)} vector results")

        final_results = []
        for vector_result in vector_results:
            source_url = vector_result["metadata"].get("source_url", "")
            chunk_id = vector_result["metadata"].get("chunk_id", 0)

            original_result = next(
                (r for r in search_results if r["url"] == source_url), None
            )

            final_results.append(
                {
                    "title": original_result["title"]
                    if original_result
                    else vector_result["text"][:50],
                    "url": source_url,
                    "cleaned_content": vector_result["text"],
                    "similarity_score": vector_result.get(
                        "score", vector_result["similarity"]
                    ),
                    "metadata": {
                        "chunk_id": chunk_id,
                        "vector_similarity": vector_result["similarity"],
                        "hybrid_score": vector_result.get("score", 0),
                    },
                }
            )

        total_time = time.time() - start_time

        result = {
            "query": query,
            "results": final_results,
            "total_time": total_time,
            "cache_stats": get_cache_stats() if CACHE_AVAILABLE else {},
            "search_stats": {"urls_found": len(search_results), "time": step1_time},
            "fetch_stats": {
                "total": len(urls),
                "success": successful_fetches,
                "failed": len(urls) - successful_fetches,
                "cache_hits": cache_hits,
                "time": step2_time,
            },
            "process_stats": {"chunks": len(all_chunks), "time": step3_time},
            "deep_process_stats": {
                "chunks": len(deep_processed_chunks),
                "removed_duplicates": removed_duplicates,
                "filtered_low_quality": filtered_low_quality,
                "time": step4_time,
            },
            "vector_stats": {
                "stored_documents": len(document_ids),
                "retrieved_results": len(vector_results),
                "time": step5_time + step6_time,
            },
        }

        logger.info(f"AI search completed in {total_time:.2f}s")
        return result

    except Exception as e:
        logger.error(f"AI search failed: {e}")
        raise


async def search_ai_async(
    query: str, max_results: Optional[int] = None, use_cache: bool = True
) -> Dict:
    """
    异步版本的主搜索函数
    """
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_ai, query, max_results, use_cache)


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

    logger.info(f"Starting AI search CLI")
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
            print(f"\nStatistics:")
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
            print(f"Top Results:")
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
